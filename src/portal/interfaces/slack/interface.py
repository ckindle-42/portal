"""
Portal SlackInterface

Receives events from Slack via webhook (Events API).
Responds via Slack Web API (chat.postMessage).

Requires:
  SLACK_BOT_TOKEN    — Bot User OAuth Token (xoxb-...)
  SLACK_SIGNING_SECRET — For request signature verification

Setup:
  1. Create Slack App at api.slack.com
  2. Enable Events API, set Request URL to:
     https://your-domain/slack/events  (or use ngrok for local dev)
  3. Subscribe to: app_mention, message.channels
  4. Install app to workspace, copy Bot Token
  5. Copy Signing Secret from Basic Information
"""

import hashlib
import hmac
import time
import logging
from typing import AsyncIterator

from fastapi import Request, HTTPException
from slack_sdk.web.async_client import AsyncWebClient

from portal.agent.dispatcher import CentralDispatcher
from portal.core.types import IncomingMessage
from portal.interfaces.base import BaseInterface

logger = logging.getLogger(__name__)


@CentralDispatcher.register("slack")
class SlackInterface(BaseInterface):
    """
    Slack Events API interface.

    Shares AgentCore with all other Portal interfaces.
    Registers /slack/events on Portal's existing FastAPI app.
    """

    def __init__(self, agent_core, config, web_app):
        """
        Args:
            agent_core: Portal AgentCore instance (shared)
            config: Portal Settings
            web_app: The FastAPI app from WebInterface — we register routes on it
        """
        self.agent_core = agent_core
        self.config = config
        self.web_app = web_app
        self.slack_config = config.interfaces.slack
        self.client = AsyncWebClient(token=self.slack_config.bot_token)
        self._register_routes()

    def _verify_slack_signature(self, body: bytes, timestamp: str, signature: str) -> bool:
        """Verify Slack request signature to prevent spoofing."""
        if not signature:
            return False

        try:
            parsed_timestamp = int(timestamp)
        except (TypeError, ValueError):
            logger.warning("Invalid Slack signature timestamp", extra={"timestamp": timestamp})
            return False

        if abs(time.time() - parsed_timestamp) > 300:
            return False  # Reject requests older than 5 minutes

        sig_basestring = f"v0:{parsed_timestamp}:{body.decode('utf-8')}"
        my_signature = (
            "v0="
            + hmac.new(
                self.slack_config.signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )
        return hmac.compare_digest(my_signature, signature)

    def _register_routes(self):
        """Register Slack webhook endpoints on the shared FastAPI app."""

        @self.web_app.post("/slack/events")
        async def slack_events(request: Request):
            body = await request.body()

            # Verify signature
            timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
            signature = request.headers.get("X-Slack-Signature", "")

            if not self._verify_slack_signature(body, timestamp, signature):
                raise HTTPException(status_code=403, detail="Invalid Slack signature")

            payload = await request.json()

            # Slack URL verification challenge
            if payload.get("type") == "url_verification":
                return {"challenge": payload["challenge"]}

            # Handle events
            event = payload.get("event", {})
            event_type = event.get("type", "")

            if event_type in ("app_mention", "message") and "bot_id" not in event:
                await self._handle_message(event)

            return {"ok": True}

    async def _handle_message(self, event: dict):
        """Process incoming Slack message through AgentCore."""
        channel = event.get("channel", "")
        user = event.get("user", "")
        text = event.get("text", "").strip()
        thread_ts = event.get("thread_ts") or event.get("ts")

        # Channel whitelist check
        if (
            self.slack_config.channel_whitelist
            and channel not in self.slack_config.channel_whitelist
        ):
            logger.debug(f"Ignoring message from non-whitelisted channel {channel}")
            return

        # Remove bot mention from text (@Portal message text)
        if text.startswith("<@"):
            text = text.split(">", 1)[-1].strip()

        if not text:
            return

        incoming = IncomingMessage(
            id=f"slack-{thread_ts}",
            text=text,
            model="auto",
            source="slack",
            metadata={"channel": channel, "user": user, "thread_ts": thread_ts},
        )

        try:
            # Stream response back to Slack
            # Slack doesn't support true streaming, so we collect then post
            response_text = ""
            async for token in self.agent_core.stream_response(incoming):
                response_text += token

            await self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=response_text,
            )
        except Exception as e:
            logger.error(f"Slack response failed: {e}")
            await self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text="Sorry, I encountered an error processing your request. Please try again.",
            )

    async def start(self) -> None:
        """SlackInterface routes are registered in __init__. Nothing to start."""
        logger.info("SlackInterface routes registered on /slack/events")

    async def stop(self) -> None:
        """Nothing to tear down — routes live on the shared FastAPI app."""
        pass

    async def send_message(self, chat_id: str, message: str, **kwargs) -> None:
        """Send a message to a Slack channel."""
        await self.client.chat_postMessage(channel=chat_id, text=message)

    async def receive_message(self) -> AsyncIterator[IncomingMessage]:
        """Slack is push-based via webhook. This is not used."""
        raise NotImplementedError("SlackInterface is event-driven, not polling.")

    async def handle_message(self, message):
        """Handled via webhook routes registered in __init__."""
        pass
