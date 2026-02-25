# Configuration Schemas

This directory contains Pydantic schemas for all PocketPortal configuration files.

## Purpose

- **Strict Validation**: All config is validated at startup
- **Type Safety**: Strong typing for all configuration fields
- **Documentation**: Self-documenting configuration structure
- **IDE Support**: Autocomplete for config fields
- **Hot-Reload**: Schemas used by ConfigWatcher for validation before applying changes

## Schema Files

- `settings_schema.py`: Main settings schema (interfaces, security, LLM, observability)
- More schemas can be added as needed (e.g., `plugin_schema.py`, `tool_schema.py`)

## Usage

```python
from portal.config.schemas import SettingsSchema

# Load and validate configuration
config_dict = load_yaml("config.yaml")
settings = SettingsSchema(**config_dict)  # Validates against schema

# Access typed configuration
print(settings.llm.default_model)  # IDE autocomplete works!
print(settings.security.rate_limit_requests)
```

## Adding New Schemas

When adding new configuration sections:

1. Create a Pydantic model in this directory
2. Add validation logic as needed
3. Export from `__init__.py`
4. Update documentation
