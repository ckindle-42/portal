"""
Prompt Manager - Loads and composes system prompts from templates
===============================================================

Allows hot-reloading of prompts without restart.
Supports composable prompt templates.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Manages system prompts loaded from external files

    Features:
    - Hot-reloading: No restart needed to update prompts
    - Composable: Combine base + interface + preference prompts
    - Cacheable: Reduce file I/O with smart caching
    """

    def __init__(self, prompts_dir: Optional[Path] = None, cache_ttl_seconds: int = 300):
        """
        Initialize prompt manager

        Args:
            prompts_dir: Directory containing prompt templates
            cache_ttl_seconds: Cache time-to-live (default: 5 minutes)
        """
        self.prompts_dir = prompts_dir or Path(__file__).parent.parent / "prompts"
        self.cache_ttl_seconds = cache_ttl_seconds

        # Cache: {template_name: (timestamp, content)}
        self._cache: Dict[str, tuple[float, str]] = {}

        logger.info(f"PromptManager initialized: {self.prompts_dir}")

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
            age = datetime.now().timestamp() - timestamp

            if age < self.cache_ttl_seconds:
                logger.debug(f"Using cached template: {template_name}")
                return content

        # Load from file
        template_path = self.prompts_dir / f"{template_name}.md"

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Update cache
            self._cache[template_name] = (datetime.now().timestamp(), content)

            logger.debug(f"Loaded template: {template_name}")
            return content

        except FileNotFoundError:
            logger.warning(f"Template not found: {template_name}")
            return ""
        except Exception as e:
            logger.error(f"Error loading template {template_name}: {e}")
            return ""

    def build_system_prompt(
        self,
        interface: str = "unknown",
        user_preferences: Optional[Dict] = None
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

        # Start with base prompt
        parts = [self.load_template('base_system')]

        # Add interface-specific prompt
        interface_template = f"{interface}_interface"
        interface_prompt = self.load_template(interface_template)
        if interface_prompt:
            parts.append(interface_prompt)

        # Add preference-specific prompts
        if user_preferences.get('verbose'):
            parts.append(self.load_template('preferences/verbose'))
        elif user_preferences.get('terse'):
            parts.append(self.load_template('preferences/terse'))

        # Add custom context if provided
        if user_preferences.get('custom_context'):
            parts.append(user_preferences['custom_context'])

        # Combine all parts
        prompt = "\n\n".join(part for part in parts if part)

        return prompt

    def clear_cache(self):
        """Clear the template cache"""
        self._cache.clear()
        logger.info("Prompt cache cleared")

    def reload_template(self, template_name: str) -> str:
        """
        Force reload a template (bypass cache)

        Args:
            template_name: Template to reload

        Returns:
            Template content
        """
        return self.load_template(template_name, use_cache=False)

    def list_templates(self) -> List[str]:
        """List all available templates"""
        if not self.prompts_dir.exists():
            return []

        templates = []
        for file_path in self.prompts_dir.rglob("*.md"):
            # Get relative path and remove .md extension
            rel_path = file_path.relative_to(self.prompts_dir)
            template_name = str(rel_path.with_suffix('')).replace('\\', '/')
            templates.append(template_name)

        return sorted(templates)

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        current_time = datetime.now().timestamp()
        valid_entries = sum(
            1 for timestamp, _ in self._cache.values()
            if current_time - timestamp < self.cache_ttl_seconds
        )

        return {
            'total_cached': len(self._cache),
            'valid_entries': valid_entries,
            'expired_entries': len(self._cache) - valid_entries
        }


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

# Singleton instance for easy access
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get global PromptManager instance"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
