# PocketPortal Test Suite

This directory contains comprehensive tests for all PocketPortal functionality.

## 📖 Complete Testing Guide

**See [docs/TESTING.md](../docs/TESTING.md) for the complete testing guide** including:
- Installation and setup
- Running tests (unit, integration, E2E)
- Test structure and coverage
- Writing new tests
- Troubleshooting

## Quick Start

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
python -m pytest tests/ -v

# Run unit tests only (fast)
python -m pytest tests/unit/ -v -m unit

# Run with coverage
python -m pytest tests/ --cov=pocketportal --cov-report=html
```

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures and configuration
├── unit/                 # Unit tests (fast, isolated)
│   ├── tools/           # Tests for all 33 tools
│   │   ├── test_git_tools.py
│   │   ├── test_docker_tools.py
│   │   ├── test_data_tools.py
│   │   ├── test_system_tools.py
│   │   ├── test_automation_tools.py
│   │   ├── test_document_tools.py
│   │   └── test_web_and_media_tools.py
│   └── ...              # Framework tests
├── integration/         # Integration tests
│   └── test_tool_loading.py
└── e2e/                # End-to-end tests
    └── test_cli_commands.py
```

## Test Coverage

✅ **All 33 tools have unit test coverage (100%)**

- **Audio** (1): audio_transcribe
- **Automation** (2): job_scheduler, shell_safety
- **Data** (5): csv_analyzer, excel_processor, file_compressor, math_visualizer, pdf_ocr, qr_generator, text_transformer
- **Dev** (15): Git tools (9), Docker tools (5), python_env_manager
- **Utility** (9): clipboard_manager, document_metadata, system_stats, process_monitor, etc.
- **Web** (1): http_client

## Running Specific Tests

```bash
# Test specific tool category
python -m pytest tests/unit/tools/test_git_tools.py -v
python -m pytest tests/unit/tools/test_docker_tools.py -v

# Test CLI functionality
python -m pytest tests/e2e/test_cli_commands.py -v

# Test tool loading
python -m pytest tests/integration/test_tool_loading.py -v
```

## CI/CD

Tests run automatically on:
- Push to main branch
- Pull requests
- Manual workflow dispatch

See `.github/workflows/tests.yml` for CI configuration.

---

For detailed information, troubleshooting, and advanced usage, see **[docs/TESTING.md](../docs/TESTING.md)**.
