"""
Prompt Manager - Loads and composes system prompts from templates
===============================================================

Allows hot-reloading of prompts without restart.
Supports composable prompt templates.
Supports persona-based prompts from config/personas/.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class PersonaLibrary:
    """
    Loads and manages persona YAML files from config/personas/.

    Each persona is a specialized AI assistant with its own system prompt,
    category, and optional workspace routing configuration.
    """

    def __init__(self, personas_dir: Path | None = None) -> None:
        """
        Initialize the persona library.

        Args:
            personas_dir: Directory containing persona YAML files.
                         Defaults to config/personas/ relative to repo root.
        """
        if personas_dir is None:
            # Default to config/personas at repo root (portal/config/personas)
            personas_dir = Path(__file__).parent.parent.parent.parent / "config" / "personas"

        self.personas_dir = personas_dir
        self._personas: dict[str, dict] = {}
        self._load_personas()

    def _load_personas(self) -> None:
        """Scan directory and load all valid persona YAML files."""
        if not self.personas_dir.exists():
            logger.warning("Personas directory does not exist: %s", self.personas_dir)
            return

        for yaml_file in self.personas_dir.glob("*.yaml"):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not data:
                    logger.warning("Empty persona file: %s", yaml_file)
                    continue

                # Validate required fields
                required = ["name", "slug", "system_prompt"]
                missing = [f for f in required if not data.get(f)]
                if missing:
                    logger.warning("Persona %s missing required fields: %s", yaml_file.name, missing)
                    continue

                slug = data["slug"]
                self._personas[slug] = data
                logger.debug("Loaded persona: %s", slug)

            except yaml.YAMLError as e:
                logger.error("Failed to parse persona %s: %s", yaml_file.name, e)
            except Exception as e:
                logger.error("Error loading persona %s: %s", yaml_file.name, e)

        logger.info("PersonaLibrary loaded %d personas from %s", len(self._personas), self.personas_dir)

    def get_persona(self, slug: str) -> dict | None:
        """
        Get a persona by slug.

        Args:
            slug: Persona slug (e.g., 'cybersecurity-specialist')

        Returns:
            Persona dict or None if not found
        """
        return self._personas.get(slug)

    def list_personas(self) -> list[dict]:
        """
        List all loaded personas.

        Returns:
            List of persona dicts with public fields (slug, name, category, description)
        """
        result = []
        for slug, data in self._personas.items():
            result.append({
                "slug": slug,
                "name": data.get("name"),
                "category": data.get("category"),
                "description": data.get("workspace", {}).get("description") if data.get("workspace") else None,
                "workspace_model": data.get("workspace_model"),
            })
        return result

    def reload(self) -> None:
        """Reload all personas from disk."""
        self._personas.clear()
        self._load_personas()


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
    - Persona support: Load specialized prompts from config/personas/
    """

    def __init__(
        self,
        prompts_dir: Path | None = None,
        personas_dir: Path | None = None,
        cache_ttl_seconds: int = 300,
    ) -> None:
        """
        Initialize prompt manager

        Args:
            prompts_dir: Directory containing prompt templates
            personas_dir: Directory containing persona YAML files
            cache_ttl_seconds: Cache time-to-live (default: 5 minutes)
        """
        self.prompts_dir = prompts_dir or Path(__file__).parent.parent / "prompts"
        self.cache_ttl_seconds = cache_ttl_seconds

        # Cache: {template_name: (timestamp, content)}
        self._cache: dict[str, tuple[float, str]] = {}

        # Persona library
        self.persona_library = PersonaLibrary(personas_dir)

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
        self,
        interface: str = "unknown",
        user_preferences: dict | None = None,
        persona_slug: str | None = None,
    ) -> str:
        """
        Build a complete system prompt

        Args:
            interface: Interface name ('telegram', 'web', 'slack', etc.)
            user_preferences: User preference dictionary
            persona_slug: Optional persona slug to use (e.g., 'cybersecurity-specialist')

        Returns:
            Composed system prompt
        """
        user_preferences = user_preferences or {}

        # Check for persona override
        if persona_slug:
            persona = self.persona_library.get_persona(persona_slug)
            if persona:
                system_prompt = persona.get("system_prompt", "")
                if system_prompt:
                    logger.debug("Using persona prompt for: %s", persona_slug)
                    return system_prompt
            else:
                logger.warning("Persona not found: %s", persona_slug)

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
