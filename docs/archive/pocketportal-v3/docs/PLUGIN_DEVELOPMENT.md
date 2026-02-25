# PocketPortal Plugin Development Guide

**Version:** 4.3.0+
**Status:** Production-Ready

---

## Overview

PocketPortal supports a plugin architecture that allows third-party developers to create and distribute custom tools without modifying the core codebase. Plugins are automatically discovered using Python's `entry_points` mechanism.

**Key Benefits:**
- ✅ No need to fork PocketPortal
- ✅ Distribute via PyPI: `pip install pocketportal-tool-yourplugin`
- ✅ Automatic discovery on installation
- ✅ Full access to PocketPortal's tool API
- ✅ Independent versioning and maintenance

---

## Quick Start

### 1. Create Plugin Package Structure

```
pocketportal-tool-example/
├── pyproject.toml
├── README.md
├── LICENSE
└── pocketportal_example/
    ├── __init__.py
    └── example_tool.py
```

### 2. Define Your Tool

```python
# pocketportal_example/example_tool.py
from pocketportal.tools.base_tool import BaseTool, ToolMetadata, ToolCategory
from typing import Dict, Any

class ExampleTool(BaseTool):
    """
    An example plugin tool for PocketPortal.

    This tool demonstrates how to create a custom plugin that can be
    distributed independently and automatically discovered by PocketPortal.
    """

    def __init__(self):
        metadata = ToolMetadata(
            name="example_tool",
            description="Demonstrates plugin architecture",
            category=ToolCategory.SYSTEM,
            version="1.0.0",
            requires_confirmation=False,
            async_capable=True,
        )
        super().__init__(metadata)

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool.

        Args:
            parameters: Tool parameters
                - message (str): Message to process

        Returns:
            dict: Result with processed message
        """
        message = parameters.get('message', 'Hello from plugin!')

        return {
            'success': True,
            'result': f"Plugin says: {message}",
            'plugin_version': self.metadata.version
        }

    def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, str | None]:
        """Optional: Validate parameters before execution"""
        if 'message' in parameters and not isinstance(parameters['message'], str):
            return False, "message must be a string"
        return True, None
```

### 3. Export Tool in __init__.py

```python
# pocketportal_example/__init__.py
from .example_tool import ExampleTool

__version__ = "1.0.0"
__all__ = ['ExampleTool']
```

### 4. Register as Entry Point

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "pocketportal-tool-example"
version = "1.0.0"
description = "Example plugin tool for PocketPortal"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "you@example.com"}
]
keywords = ["pocketportal", "plugin", "ai", "agent"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
]

dependencies = [
    "pocketportal>=4.3.0",
]

# CRITICAL: Register your tool as an entry point
[project.entry-points."pocketportal.tools"]
example_tool = "pocketportal_example:ExampleTool"
#   ^               ^                    ^
#   |               |                    |
#   Name shown      Package name         Class to load
#   in logs

[project.urls]
Homepage = "https://github.com/yourusername/pocketportal-tool-example"
Repository = "https://github.com/yourusername/pocketportal-tool-example"
Issues = "https://github.com/yourusername/pocketportal-tool-example/issues"
```

### 5. Install and Test

```bash
# Install your plugin
pip install -e .

# Or install from PyPI (once published)
pip install pocketportal-tool-example

# Start PocketPortal - your tool is automatically discovered!
pocketportal
```

**Expected Output:**
```
INFO - Scanning for tools in /path/to/pocketportal/tools
INFO - Loaded tool: example_tool (system) from plugin:pocketportal_example:ExampleTool
INFO - Tool registry: 25 loaded (24 internal, 1 plugins), 0 failed
```

---

## Tool Development Best Practices

### 1. Tool Metadata

Always provide comprehensive metadata:

```python
metadata = ToolMetadata(
    name="my_tool",                    # Unique identifier (snake_case)
    description="Clear description",   # What the tool does
    category=ToolCategory.DATA,        # Category for organization
    version="1.0.0",                   # Semantic versioning
    requires_confirmation=False,       # True for dangerous operations
    async_capable=True,               # Supports async execution
    parameters={                       # Parameter schema (optional)
        'input_file': {
            'type': 'string',
            'description': 'Path to input file',
            'required': True
        },
        'format': {
            'type': 'string',
            'description': 'Output format',
            'required': False,
            'default': 'json'
        }
    }
)
```

### 2. Error Handling

Always handle errors gracefully:

```python
async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Tool logic
        result = await self._process(parameters)

        return {
            'success': True,
            'result': result
        }

    except FileNotFoundError as e:
        return {
            'success': False,
            'error': f"File not found: {e}",
            'error_type': 'FileNotFoundError'
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error: {e}",
            'error_type': type(e).__name__
        }
```

### 3. Lazy Imports for Heavy Dependencies

Only import heavy libraries when needed:

```python
async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    # Lazy import - only loaded when tool is executed
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        return {
            'success': False,
            'error': 'Required dependencies not installed. Run: pip install pandas numpy'
        }

    # Tool logic using pandas/numpy
    ...
```

### 4. Async Support

Support async operations properly:

```python
async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    # Use async HTTP requests
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()

    # Use async file I/O
    async with aiofiles.open(file_path, 'r') as f:
        content = await f.read()

    return {'success': True, 'result': data}
```

### 5. Parameter Validation

Implement parameter validation:

```python
def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate parameters before execution.

    Returns:
        (is_valid, error_message)
    """
    # Check required parameters
    if 'url' not in parameters:
        return False, "Missing required parameter: url"

    # Validate types
    if not isinstance(parameters['url'], str):
        return False, "url must be a string"

    # Validate values
    if not parameters['url'].startswith('http'):
        return False, "url must start with http:// or https://"

    return True, None
```

### 6. Dangerous Operations

Mark dangerous operations for human approval:

```python
metadata = ToolMetadata(
    name="delete_files",
    description="Delete files matching pattern",
    category=ToolCategory.SYSTEM,
    requires_confirmation=True,  # ← Admin approval required
    version="1.0.0"
)
```

---

## Advanced Features

### 1. Tool Dependencies

Declare dependencies in pyproject.toml:

```toml
[project]
dependencies = [
    "pocketportal>=4.3.0",
    "requests>=2.31.0",
    "beautifulsoup4>=4.12.0",
]

[project.optional-dependencies]
# Heavy optional dependencies
ml = [
    "tensorflow>=2.14.0",
    "torch>=2.1.0",
]
```

### 2. Configuration

Access PocketPortal config from your tool:

```python
async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    # Access agent config (if available)
    config = parameters.get('_config', {})
    api_key = config.get('my_plugin_api_key')

    if not api_key:
        return {
            'success': False,
            'error': 'Please set MY_PLUGIN_API_KEY in environment'
        }

    # Use API key
    ...
```

### 3. Job Queue Support

For long-running operations:

```python
metadata = ToolMetadata(
    name="video_process",
    description="Process large video files",
    category=ToolCategory.MEDIA,
    use_job_queue=True,  # ← Use async queue (v4.3+)
    version="1.0.0"
)

async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    # This will run in background queue
    await self._process_video(parameters['video_path'])
    return {'success': True}
```

### 4. Event Emission

Emit events for monitoring:

```python
async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    event_bus = parameters.get('_event_bus')

    if event_bus:
        await event_bus.emit('plugin.started', {
            'plugin': self.metadata.name,
            'parameters': parameters
        })

    # Tool logic
    result = await self._process(parameters)

    if event_bus:
        await event_bus.emit('plugin.completed', {
            'plugin': self.metadata.name,
            'result': result
        })

    return result
```

---

## Testing Your Plugin

### 1. Unit Tests

```python
# tests/test_example_tool.py
import pytest
from pocketportal_example import ExampleTool

@pytest.mark.asyncio
async def test_example_tool_basic():
    tool = ExampleTool()

    result = await tool.execute({
        'message': 'Test message'
    })

    assert result['success'] is True
    assert 'Test message' in result['result']

@pytest.mark.asyncio
async def test_example_tool_validation():
    tool = ExampleTool()

    is_valid, error = tool.validate_parameters({
        'message': 123  # Invalid type
    })

    assert is_valid is False
    assert 'must be a string' in error
```

### 2. Integration Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_plugin_discovery():
    """Test that plugin is discovered by PocketPortal"""
    from pocketportal.tools import registry

    # Trigger discovery
    registry.discover_and_load()

    # Check tool is registered
    tool = registry.get_tool('example_tool')
    assert tool is not None
    assert tool.metadata.name == 'example_tool'
```

---

## Publishing Your Plugin

### 1. Prepare for Publishing

```bash
# Install build tools
pip install build twine

# Build distribution
python -m build

# Check distribution
twine check dist/*
```

### 2. Publish to PyPI

```bash
# Test PyPI first (recommended)
twine upload --repository testpypi dist/*

# Then real PyPI
twine upload dist/*
```

### 3. Documentation

Create a comprehensive README.md:

```markdown
# PocketPortal Example Tool

A plugin tool for PocketPortal that demonstrates the plugin architecture.

## Installation

```bash
pip install pocketportal-tool-example
```

## Usage

Once installed, the tool is automatically discovered by PocketPortal:

```bash
pocketportal
```

Ask the agent: "Use the example tool to say hello"

## Configuration

No configuration needed!

## License

MIT
```

---

## Example Plugins

### 1. Stock Price Tool

```python
class StockPriceTool(BaseTool):
    def __init__(self):
        metadata = ToolMetadata(
            name="stock_price",
            description="Get real-time stock prices",
            category=ToolCategory.DATA,
            version="1.0.0",
            parameters={
                'symbol': {
                    'type': 'string',
                    'description': 'Stock ticker symbol (e.g., AAPL)',
                    'required': True
                }
            }
        )
        super().__init__(metadata)

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # Lazy import
        try:
            import yfinance as yf
        except ImportError:
            return {
                'success': False,
                'error': 'Install yfinance: pip install yfinance'
            }

        symbol = parameters['symbol']
        ticker = yf.Ticker(symbol)
        info = ticker.info

        return {
            'success': True,
            'symbol': symbol,
            'price': info.get('regularMarketPrice'),
            'currency': info.get('currency'),
            'name': info.get('longName')
        }
```

### 2. Weather Tool

```python
class WeatherTool(BaseTool):
    def __init__(self):
        metadata = ToolMetadata(
            name="weather",
            description="Get current weather for a location",
            category=ToolCategory.WEB,
            version="1.0.0"
        )
        super().__init__(metadata)

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        import aiohttp

        location = parameters.get('location', 'New York')
        api_key = parameters.get('_config', {}).get('openweather_api_key')

        if not api_key:
            return {
                'success': False,
                'error': 'Set OPENWEATHER_API_KEY in environment'
            }

        url = f"https://api.openweathermap.org/data/2.5/weather"
        params = {'q': location, 'appid': api_key, 'units': 'metric'}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'success': True,
                        'location': location,
                        'temperature': data['main']['temp'],
                        'description': data['weather'][0]['description']
                    }
                else:
                    return {
                        'success': False,
                        'error': f'API error: {response.status}'
                    }
```

---

## Troubleshooting

### Plugin Not Discovered

**Problem:** Plugin tool doesn't appear in PocketPortal

**Solutions:**
1. Check entry_point is correctly registered in pyproject.toml
2. Verify plugin is installed: `pip list | grep pocketportal-tool`
3. Check import works: `python -c "from pocketportal_example import ExampleTool"`
4. Look for errors in logs: `pocketportal --verbose`

### Import Errors

**Problem:** `ModuleNotFoundError` or `ImportError`

**Solutions:**
1. Install plugin in same environment as PocketPortal
2. Check dependencies are installed: `pip install -e ".[all]"`
3. Verify Python version compatibility (>=3.11)

### Tool Validation Fails

**Problem:** Tool loads but validation fails

**Solutions:**
1. Ensure tool inherits from `BaseTool`
2. Check `metadata` attribute exists
3. Implement `execute()` method
4. Run tests: `pytest tests/`

---

## Support

- **Issues:** https://github.com/ckindle-42/pocketportal/issues
- **Docs:** https://github.com/ckindle-42/pocketportal/docs
- **Examples:** https://github.com/pocketportal-plugins

---

**Happy Plugin Development! 🚀**
