"""
Unified Agent Core - Refactored with Dependency Injection
==========================================================

This is the heart of Portal - truly modular and production-ready.

Key Improvements:
1. ✅ Dependency Injection - All dependencies passed in, easily testable
2. ✅ Structured Errors - Custom exceptions instead of string returns
3. ✅ Context Management - Shared history across interfaces
4. ✅ Event Bus - Real-time feedback to interfaces
5. ✅ Structured Logging - JSON logs with trace IDs
6. ✅ Externalized Prompts - No hardcoded strings
7. ✅ Security Middleware - No data reaches core without validation

Architecture:
    Interface → SecurityMiddleware → AgentCore → Router → LLM
                                       ↓
                                  ContextManager
                                  EventBus
                                  PromptManager
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

from portal.memory import MemoryManager
from portal.middleware.hitl_approval import HITLApprovalMiddleware
from portal.observability.runtime_metrics import MCP_TOOL_USAGE

# Import existing routing system
from portal.routing import ExecutionEngine, IntelligentRouter, ModelRegistry

# Import new unified components
from .context_manager import ContextManager
from .event_bus import EventBus, EventEmitter, EventType
from .exceptions import ModelNotAvailableError, PortalError, ToolExecutionError
from .prompt_manager import PromptManager
from .structured_logger import TraceContext, get_logger
from .types import IncomingMessage, InterfaceType, ProcessingResult

if TYPE_CHECKING:
    from portal.middleware.tool_confirmation_middleware import ToolConfirmationMiddleware
    from portal.tools import ToolRegistry

logger = get_logger('AgentCore')


class AgentCore:
    """
    Unified Agent Core - The Brain

    This class orchestrates all AI operations regardless of which interface
    the user is using. Telegram, Web, Slack, or API - all call this same core.

    Key Features:
    - Interface-agnostic processing
    - Dependency injection for testability
    - Event emission for real-time feedback
    - Context-aware conversation handling
    - Structured logging with trace IDs
    """

    def __init__(
        self,
        model_registry: ModelRegistry,
        router: IntelligentRouter,
        execution_engine: ExecutionEngine,
        context_manager: ContextManager,
        event_bus: EventBus,
        prompt_manager: PromptManager,
        tool_registry: ToolRegistry,
        config: dict[str, Any],
        confirmation_middleware: ToolConfirmationMiddleware | None = None,
        mcp_registry: Any | None = None,
        memory_manager: MemoryManager | None = None,
    ):
        """
        Initialize the unified core with dependency injection

        Args:
            model_registry: Registry of available models
            router: Intelligent routing system
            execution_engine: Execution engine with backends
            context_manager: Conversation context manager
            event_bus: Event bus for async feedback
            prompt_manager: System prompt manager
            tool_registry: Registry of available tools
            config: Configuration dictionary
            confirmation_middleware: Optional middleware for human-in-the-loop confirmations
        """
        self.config = config
        self.start_time = datetime.now()

        # Injected dependencies (makes testing easy!)
        self.model_registry = model_registry
        self.router = router
        self.execution_engine = execution_engine
        self.context_manager = context_manager
        self.event_bus = event_bus
        self.prompt_manager = prompt_manager
        self.tool_registry = tool_registry
        self.confirmation_middleware = confirmation_middleware
        self.mcp_registry = mcp_registry
        self.memory_manager = memory_manager or MemoryManager()
        self._stats_lock = asyncio.Lock()
        self.hitl_middleware = None
        if config.get('redis_url') or os.getenv('REDIS_URL'):
            try:
                self.hitl_middleware = HITLApprovalMiddleware()
            except Exception:
                logger.warning("HITL approval middleware unavailable (Redis not reachable)")

        # Event emitter helper
        self.events = EventEmitter(self.event_bus)

        # Load tools from registry
        loaded, failed = self.tool_registry.discover_and_load()

        # Statistics tracking
        self.stats = {
            'messages_processed': 0,
            'total_execution_time': 0.0,
            'tools_executed': 0,
            'by_interface': {},
            'errors': 0
        }

        logger.info(
            "AgentCore initialized successfully",
            routing_strategy=router.strategy.value if hasattr(router, 'strategy') else 'unknown',
            tools_loaded=loaded,
            tools_failed=failed,
            models_available=len(model_registry.models),
            confirmation_middleware_enabled=confirmation_middleware is not None
        )

    async def process_message(
        self,
        chat_id: str,
        message: str,
        interface: InterfaceType = InterfaceType.UNKNOWN,
        user_context: dict | None = None,
        files: list[Any] | None = None,
    ) -> ProcessingResult:
        """
        Process a message from ANY interface (Telegram, Web, Slack).

        Args:
            chat_id: Unique identifier for this conversation
            message: The user's message text (already sanitized by SecurityMiddleware)
            interface: Source interface (InterfaceType enum)
            user_context: Optional context about the user/session
            files: Optional list of attached files

        Returns:
            ProcessingResult with response and metadata

        Raises:
            PortalError: On processing failures
        """
        start_time = time.perf_counter()
        user_context = user_context or {}
        interface = self._normalize_interface(interface)

        with TraceContext() as trace_id:
            try:
                await self._record_message_start(chat_id, message, interface, trace_id)
                message = await self._persist_user_context(chat_id, message, interface, user_context, trace_id)
                system_prompt, available_tools, context_history = await self._build_execution_context(
                    chat_id, interface, user_context
                )
                result, tool_results = await self._run_execution_with_mcp_loop(
                    query=message,
                    system_prompt=system_prompt,
                    available_tools=available_tools,
                    chat_id=chat_id,
                    trace_id=trace_id,
                    messages=context_history or None,
                )
                await self._save_assistant_response(chat_id, result.response, interface.value)
                return await self._finalize_result(
                    result, tool_results, chat_id, interface, start_time, trace_id
                )

            except PortalError as e:
                await self._handle_processing_error(e, chat_id, trace_id, start_time, known=True)
                raise

            except Exception as e:
                await self._handle_processing_error(e, chat_id, trace_id, start_time, known=False)
                raise PortalError(
                    f"Unexpected error: {str(e)}",
                    details={'original_error': str(e)}
                )

    def _normalize_interface(self, interface: InterfaceType | str) -> InterfaceType:
        """Coerce plain strings to InterfaceType."""
        if isinstance(interface, str) and not isinstance(interface, InterfaceType):
            try:
                return InterfaceType(interface)
            except ValueError:
                return InterfaceType.UNKNOWN
        return interface

    async def _record_message_start(
        self, chat_id: str, message: str, interface: InterfaceType, trace_id: str
    ) -> None:
        """Update stats, log, and emit processing-started event."""
        async with self._stats_lock:
            self.stats['messages_processed'] += 1
            key = interface.value
            self.stats['by_interface'][key] = self.stats['by_interface'].get(key, 0) + 1

        logger.info("Processing message", chat_id=chat_id, interface=interface.value, message_length=len(message))
        await self.events.emit_processing_started(chat_id, message, trace_id)

    async def _persist_user_context(
        self,
        chat_id: str,
        message: str,
        interface: InterfaceType,
        user_context: dict,
        trace_id: str,
    ) -> str:
        """Load context, persist user message, enrich with memory. Returns enriched message."""
        await self._load_context(chat_id, trace_id)
        await self._save_user_message(chat_id, message, interface.value)

        user_id = str(user_context.get("user_id") or chat_id)
        await self.memory_manager.add_message(user_id=user_id, content=message)
        memory_context = await self.memory_manager.build_context_block(user_id=user_id, query=message)
        if memory_context:
            message = f"{memory_context}\n\nUser message:\n{message}"
        return message

    async def _build_execution_context(
        self, chat_id: str, interface: InterfaceType, user_context: dict
    ) -> tuple[str, list[str], list[dict]]:
        """Build system prompt, tool list, and conversation history."""
        system_prompt = self._build_system_prompt(interface.value, user_context)
        available_tools = [t.metadata.name for t in self.tool_registry.get_all_tools()]
        context_history = await self.context_manager.get_formatted_history(chat_id, format='openai')
        return system_prompt, available_tools, context_history

    async def _finalize_result(
        self,
        result: Any,
        tool_results: list,
        chat_id: str,
        interface: InterfaceType,
        start_time: float,
        trace_id: str,
    ) -> ProcessingResult:
        """Update stats, log completion, emit event, and return ProcessingResult."""
        execution_time = time.perf_counter() - start_time
        tools_used = getattr(result, 'tools_used', [])
        async with self._stats_lock:
            self.stats['total_execution_time'] += execution_time
            self.stats['tools_executed'] += len(tools_used)

        logger.info("Completed processing", model=result.model_used, execution_time=execution_time, tools_count=len(tools_used))
        await self.event_bus.publish(
            EventType.PROCESSING_COMPLETED,
            chat_id,
            {'model': result.model_used, 'execution_time': execution_time, 'tools_used': tools_used},
            trace_id,
        )
        return ProcessingResult(
            success=result.success,
            response=result.response,
            model_used=result.model_used,
            execution_time=execution_time,
            tools_used=tools_used,
            warnings=[],
            completion_tokens=result.tokens_generated or None,
            metadata={
                'chat_id': chat_id,
                'interface': interface.value,
                'timestamp': datetime.now().isoformat(),
                'routing_strategy': (
                    self.router.strategy.value if hasattr(self.router, 'strategy') else 'auto'
                ),
                'tool_results': tool_results,
            },
            trace_id=trace_id,
        )

    async def _handle_processing_error(
        self, exc: Exception, chat_id: str, trace_id: str, start_time: float, known: bool
    ) -> None:
        """Increment error stats, log, and emit PROCESSING_FAILED event."""
        async with self._stats_lock:
            self.stats['errors'] += 1

        if known:
            portal_exc: Any = exc
            logger.error("Processing failed", error_type=type(exc).__name__, error_message=str(exc), details=portal_exc.details)
            error_payload = {'error': portal_exc.to_dict()}
        else:
            logger.error("Unexpected error", error=str(exc), exc_info=True)
            error_payload = {'error': str(exc)}

        await self.event_bus.publish(EventType.PROCESSING_FAILED, chat_id, error_payload, trace_id)

    async def _load_context(self, chat_id: str, trace_id: str):
        """Load conversation context"""
        history = await self.context_manager.get_history(chat_id, limit=10)

        await self.event_bus.publish(
            EventType.CONTEXT_LOADED,
            chat_id,
            {'messages_loaded': len(history)},
            trace_id
        )

        logger.debug("Context loaded", chat_id=chat_id, message_count=len(history))

    async def _save_user_message(self, chat_id: str, message: str, interface: str):
        """
        Save user message to context immediately upon receipt

        This ensures we don't lose the user's message if processing crashes.
        """
        await self.context_manager.add_message(
            chat_id=chat_id,
            role='user',
            content=message,
            interface=interface
        )
        logger.debug("User message saved", chat_id=chat_id)

    async def _save_assistant_response(self, chat_id: str, response: str, interface: str):
        """
        Save assistant response to context after generation

        Called after successful response generation.
        """
        await self.context_manager.add_message(
            chat_id=chat_id,
            role='assistant',
            content=response,
            interface=interface
        )
        logger.debug("Assistant response saved", chat_id=chat_id)

    def _build_system_prompt(self, interface: str, user_context: dict | None) -> str:
        """
        Build system prompt from external templates

        No more hardcoded strings!
        """
        user_prefs = user_context.get('preferences', {}) if user_context else {}

        return self.prompt_manager.build_system_prompt(
            interface=interface,
            user_preferences=user_prefs
        )

    async def _execute_with_routing(
        self,
        query: str,
        system_prompt: str,
        available_tools: list[str],
        chat_id: str,
        trace_id: str,
        messages: list[dict[str, Any]] | None = None,
    ):
        """Execute with intelligent routing"""
        # Get routing decision
        decision = self.router.route(query)

        # Emit routing decision event
        await self.event_bus.publish(
            EventType.ROUTING_DECISION,
            chat_id,
            {
                'model': decision.model_id,
                'reasoning': decision.reasoning,
                'complexity': decision.classification.complexity.value
            },
            trace_id
        )

        logger.info(
            "Routing decision",
            model=decision.model_id,
            complexity=decision.classification.complexity.value
        )

        # Execute with execution engine
        await self.event_bus.publish(
            EventType.MODEL_GENERATING,
            chat_id,
            {'model': decision.model_id},
            trace_id
        )

        result = await self.execution_engine.execute(
            query=query,
            system_prompt=system_prompt,
            messages=messages,
        )

        if not result.success:
            raise ModelNotAvailableError(
                f"Model execution failed: {result.error}",
                details={'model': decision.model_id, 'error': result.error}
            )

        return result

    async def get_stats(self) -> dict[str, Any]:
        """Get processing statistics"""
        async with self._stats_lock:
            uptime = (datetime.now() - self.start_time).total_seconds()
            stats = self.stats.copy()
        stats['uptime_seconds'] = uptime
        if stats['messages_processed'] > 0:
            stats['avg_execution_time'] = (
                stats['total_execution_time'] / stats['messages_processed']
            )
        else:
            stats['avg_execution_time'] = 0
        return stats

    def get_tool_list(self) -> list[dict[str, Any]]:
        """Get list of available tools"""
        return self.tool_registry.get_tool_list()

    async def _resolve_preflight_tools(
        self,
        query: str,
        system_prompt: str,
        messages: list[dict[str, Any]] | None,
        chat_id: str,
        trace_id: str,
        max_rounds: int,
    ) -> list[dict[str, str]]:
        """
        Run the preflight MCP tool loop and return accumulated tool-result messages.

        Executes up to *max_rounds* of model → tool-call → result iterations so
        that `stream_response` receives a resolved context before it begins
        token streaming.  Returns an empty list when no MCP registry is attached
        or when the model produces no tool-call requests.
        """
        tool_messages: list[dict[str, str]] = []
        if not self.mcp_registry:
            return tool_messages

        for _ in range(max_rounds):
            loop_messages = messages if not tool_messages else (messages or []) + tool_messages
            preflight = await self.execution_engine.execute(
                query=query,
                system_prompt=system_prompt,
                messages=loop_messages,
            )
            if not preflight.success:
                break
            tool_calls = preflight.tool_calls or []
            if not tool_calls:
                break
            results = await self._dispatch_mcp_tools(tool_calls, chat_id, trace_id)
            tool_messages.extend(self._format_tool_results_as_messages(results))

        return tool_messages

    async def stream_response(self, incoming: IncomingMessage) -> AsyncIterator[str]:
        """
        Yield response tokens for streaming interfaces (WebInterface, SlackInterface).

        If the model requests MCP tools, run the full tool loop first and then
        stream the final answer token-by-token.
        """
        try:
            interface = InterfaceType(incoming.source) if incoming.source else InterfaceType.WEB
        except ValueError:
            interface = InterfaceType.WEB

        system_prompt = self._build_system_prompt(interface.value, {})
        query = incoming.text
        max_tool_rounds = int(self.config.get("mcp_tool_max_rounds", 3))
        messages = incoming.history if incoming.history else None

        tool_messages = await self._resolve_preflight_tools(
            query=query,
            system_prompt=system_prompt,
            messages=messages,
            chat_id=incoming.id,
            trace_id=f"stream-{incoming.id}",
            max_rounds=max_tool_rounds,
        )

        collected_response = []
        final_messages = (messages or []) + tool_messages if tool_messages else messages

        async for token in self.execution_engine.generate_stream(
            query=query,
            system_prompt=system_prompt,
            messages=final_messages,
        ):
            collected_response.append(token)
            yield token

        # Save completed response to context
        full_response = "".join(collected_response)
        if full_response and incoming.id:
            try:
                await self._save_assistant_response(
                    incoming.id, full_response, incoming.source or "web"
                )
            except Exception as e:
                logger.warning(f"Failed to save streamed response to context: {e}")


    async def _run_execution_with_mcp_loop(
        self,
        query: str,
        system_prompt: str,
        available_tools: list[str],
        chat_id: str,
        trace_id: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> tuple[Any, list[dict[str, Any]]]:
        """Execute model calls and iterate tool calls until a final answer is produced."""
        current_query = query
        collected_tool_results: list[dict[str, Any]] = []
        max_tool_rounds = int(self.config.get("mcp_tool_max_rounds", 3))
        current_messages = messages  # Use caller-provided history on first pass only

        for _ in range(max_tool_rounds):
            result = await self._execute_with_routing(
                query=current_query,
                system_prompt=system_prompt,
                available_tools=available_tools,
                chat_id=chat_id,
                trace_id=trace_id,
                messages=current_messages,
            )

            tool_calls = result.tool_calls or []
            if not (tool_calls and self.mcp_registry):
                return result, collected_tool_results

            mcp_results = await self._dispatch_mcp_tools(tool_calls, chat_id, trace_id)
            collected_tool_results.extend(mcp_results)
            tool_msgs = self._format_tool_results_as_messages(mcp_results)
            current_messages = (current_messages or []) + tool_msgs

        final_result = await self._execute_with_routing(
            query=current_query,
            system_prompt=system_prompt,
            available_tools=available_tools,
            chat_id=chat_id,
            trace_id=trace_id,
            messages=None,
        )
        return final_result, collected_tool_results

    def _format_tool_results_as_messages(self, tool_results: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Format MCP tool outputs as structured messages for the model."""
        messages = []
        for result in tool_results:
            tool_name = result.get('tool', 'unknown')
            tool_output = json.dumps(result.get('result', {}), ensure_ascii=False, default=str)
            messages.append({
                "role": "tool",
                "content": f"[{tool_name}] {tool_output}",
            })
        return messages

    async def health_check(self) -> bool:
        """
        Return True if AgentCore is operational.

        Checks that the execution engine has at least one reachable backend.
        Falls back to True if the engine does not expose a health method.
        """
        try:
            if hasattr(self.execution_engine, 'health_check'):
                return await self.execution_engine.health_check()
            # Minimal liveness: just check that start_time is set
            return self.start_time is not None
        except Exception:
            return False

    async def _dispatch_mcp_tools(
        self,
        tool_calls: list[dict[str, Any]],
        chat_id: str,
        trace_id: str,
    ) -> list[dict[str, Any]]:
        """
        Dispatch a list of tool-call requests to the MCP registry.

        Called from process_message after the LLM returns tool_call entries.
        Returns a list of tool results that can be fed back into the context.

        ARCH-3 NOTE: Full tool-use loop requires ExecutionEngine to surface
        tool_call entries from the LLM response.  This method is wired and
        ready; the ExecutionEngine integration is Phase 2 work.
        """
        if not self.mcp_registry:
            return []

        results = []
        for call in tool_calls:
            server_name = call.get('server', 'core')
            tool_name = call.get('tool') or call.get('name', '')
            arguments = call.get('arguments', {})

            if not tool_name:
                continue

            logger.info(
                "Dispatching MCP tool",
                server=server_name,
                tool=tool_name,
                chat_id=chat_id,
            )

            if self.hitl_middleware and tool_name in {"bash", "filesystem_write", "web_fetch"}:
                user_id = str(arguments.get("user_id", chat_id))
                approval_token = str(arguments.get("approval_token", "")).strip()
                if not approval_token:
                    approval_token = await self.hitl_middleware.request(
                        user_id=user_id,
                        channel="telegram",
                        tool_name=tool_name,
                        args=arguments,
                    )
                    results.append(
                        {
                            'tool': tool_name,
                            'result': {
                                'status': 'pending_approval',
                                'approval_token': approval_token,
                                'message': 'Tool execution deferred until approval token is granted.',
                            },
                        }
                    )
                    continue

                if not self.hitl_middleware.check_approved(user_id=user_id, token=approval_token):
                    results.append(
                        {
                            'tool': tool_name,
                            'result': {
                                'status': 'pending_approval',
                                'approval_token': approval_token,
                                'message': 'Approval token is still pending or denied.',
                            },
                        }
                    )
                    continue

            result = await self.mcp_registry.call_tool(server_name, tool_name, arguments)
            MCP_TOOL_USAGE.labels(tool_name=tool_name).inc()
            results.append({'tool': tool_name, 'result': result})

        return results

    async def execute_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        chat_id: str | None = None,
        user_id: str | None = None,
        trace_id: str | None = None
    ) -> dict[str, Any]:
        """
        Execute a specific tool directly

        This is useful for direct tool execution without LLM reasoning.
        If the tool requires confirmation and confirmation middleware is enabled,
        this method will request approval before executing.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            chat_id: Optional chat ID for confirmation context
            user_id: Optional user ID for confirmation context
            trace_id: Optional trace ID for logging

        Returns:
            Tool execution result

        Raises:
            ToolExecutionError: If tool not found, confirmation denied, or execution fails
        """
        tool = self.tool_registry.get_tool(tool_name)

        if not tool:
            raise ToolExecutionError(
                tool_name,
                f'Tool not found: {tool_name}'
            )

        # Check if tool requires confirmation
        requires_confirmation = getattr(tool.metadata, 'requires_confirmation', False)

        if requires_confirmation and self.confirmation_middleware:
            logger.info(
                f"Tool {tool_name} requires confirmation, requesting approval...",
                tool=tool_name,
                chat_id=chat_id
            )

            # Request confirmation (this will block until approved/denied/timeout)
            approved = await self.confirmation_middleware.request_confirmation(
                tool_name=tool_name,
                parameters=parameters,
                chat_id=chat_id or "unknown",
                user_id=user_id,
                trace_id=trace_id
            )

            if not approved:
                logger.warning(
                    f"Tool execution denied: {tool_name}",
                    tool=tool_name,
                    chat_id=chat_id
                )
                raise ToolExecutionError(
                    tool_name,
                    "Tool execution denied by administrator",
                    details={'parameters': parameters, 'requires_confirmation': True}
                )

            logger.info(
                f"Tool execution approved: {tool_name}",
                tool=tool_name,
                chat_id=chat_id
            )

        try:
            result = await tool.execute(parameters)
            return result
        except Exception as e:
            logger.error("Tool execution error", tool=tool_name, error=str(e))
            raise ToolExecutionError(
                tool_name,
                str(e),
                details={'parameters': parameters}
            )

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up AgentCore...")
        if self.mcp_registry and hasattr(self.mcp_registry, 'close'):
            await self.mcp_registry.close()
        await self.execution_engine.cleanup()
        logger.info("AgentCore cleanup complete")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_agent_core(config) -> AgentCore:
    """
    Factory function to create AgentCore with all dependencies.

    This is the recommended way to instantiate AgentCore.

    Args:
        config: Configuration dict OR a Settings object.  When a Settings
                object is passed (e.g. from lifecycle.py) it is converted to a
                plain dict via Settings.to_agent_config() before use.

    Returns:
        Initialized AgentCore instance
    """
    from .factories import create_dependencies

    # Allow callers to pass a Settings object (lifecycle.py) or a plain dict
    if not isinstance(config, dict):
        if hasattr(config, 'to_agent_config'):
            config = config.to_agent_config()
        else:
            config = {}

    deps = create_dependencies(config)
    return AgentCore(**deps.get_all())
