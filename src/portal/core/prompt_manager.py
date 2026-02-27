"""
Prompt Manager - Loads and composes system prompts from templates
===============================================================

Allows hot-reloading of prompts without restart.
Supports composable prompt templates.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "You are Portal, a helpful AI assistant running locally on the user's hardware. "
    "You are honest, precise, and concise. You have access to tools when they are "
    "available. Always prioritize the user's privacy and data sovereignty."
)


class PromptManager:
    """
    Manages system prompts loaded from external files

    Features:
    - Hot-reloading: No restart needed to update prompts
    - Composable: Combine base + interface + preference prompts
    - Cacheable: Reduce file I/O with smart caching
    """

    def __init__(self, prompts_dir: Path | None = None, cache_ttl_seconds: int = 300) -> None:
        """
        Initialize prompt manager

        Args:
            prompts_dir: Directory containing prompt templates
            cache_ttl_seconds: Cache time-to-live (default: 5 minutes)
        """
        self.prompts_dir = prompts_dir or Path(__file__).parent.parent / "prompts"
        self.cache_ttl_seconds = cache_ttl_seconds

        # Cache: {template_name: (timestamp, content)}
        self._cache: dict[str, tuple[float, str]] = {}

        logger.info("PromptManager initialized: %s", self.prompts_dir)

    def load_template(self, template_name: str, use_cache: bool = True) -> str:
        """
        Load a prompt template

        Args:
            template_name: Template name (e.g., 'base_system', 'telegram_interface')
            use_cache: Use cached version if available

        Returns:
            Template content
        """
        # Check cache
        if use_cache and template_name in self._cache:
            timestamp, content = self._cache[template_name]
            age = datetime.now(tz=UTC).timestamp() - timestamp

            if age < self.cache_ttl_seconds:
                logger.debug("Using cached template: %s", template_name)
                return content

        # Load from file
        template_path = self.prompts_dir / f"{template_name}.md"

        try:
            with open(template_path, encoding="utf-8") as f:
                content = f.read()

            # Update cache
            self._cache[template_name] = (datetime.now(tz=UTC).timestamp(), content)

            logger.debug("Loaded template: %s", template_name)
            return content

        except FileNotFoundError:
            logger.warning("Template not found: %s", template_name)
            return ""
        except Exception as e:
            logger.error("Error loading template %s: %s", template_name, e)
            return ""

    def build_system_prompt(
        self, interface: str = "unknown", user_preferences: dict | None = None
    ) -> str:
        """
        Build a complete system prompt

        Args:
            interface: Interface name ('telegram', 'web', 'slack', etc.)
            user_preferences: User preference dictionary

        Returns:
            Composed system prompt
        """
        user_preferences = user_preferences or {}

        # Start with base prompt — fall back to hardcoded default
        base = self.load_template("base_system")
        if not base.strip():
            logger.warning("Base system prompt template missing or empty, using built-in fallback")
            base = _DEFAULT_SYSTEM_PROMPT
        parts = [base]

        # Add interface-specific prompt
        interface_template = f"{interface}_interface"
        interface_prompt = self.load_template(interface_template)
        if interface_prompt:
            parts.append(interface_prompt)

        # Add preference-specific prompts
        if user_preferences.get("verbose"):
            parts.append(self.load_template("preferences/verbose"))
        elif user_preferences.get("terse"):
            parts.append(self.load_template("preferences/terse"))

        # Add custom context if provided
        if user_preferences.get("custom_context"):
            parts.append(user_preferences["custom_context"])

        # Combine all parts
        prompt = "\n\n".join(part for part in parts if part)

        return prompt
