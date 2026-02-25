# PocketPortal Testing Guide

Complete guide for running tests and understanding the test infrastructure.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Writing Tests](#writing-tests)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Python 3.11+** (tested with 3.11.14)
- **pip** (package manager)
- **git** (for version control)

### Optional Dependencies

Some tests require optional dependencies. Install them based on your needs:

```bash
# For testing all document processing tools
pip install -e ".[documents]"

# For testing data analysis tools
pip install -e ".[data]"

# For testing Docker tools
pip install -e ".[dev]"
# Note: Docker daemon must be running

# For testing audio tools
pip install -e ".[audio]"

# Install ALL optional dependencies
pip install -e ".[all]"
```

**Tool categories and required extras**

Unit tests under `tests/unit/tools/` map to the `pocketportal list-tools` categories. Install
the extras below to cover each category in tests:

| Tool category | Extra(s) | Notes |
| --- | --- | --- |
| utility | `tools`, `documents` | QR/image utilities use `tools`; document conversion utilities use `documents`. |
| data | `data`, `documents` | Data analysis tools use `data`; Excel processing uses `documents`. |
| web | (core) | Web/HTTP tools rely on core dependencies. |
| audio | `audio` | Audio transcription tools. |
| automation | `automation` | Scheduling and cron tools. |
| knowledge | `knowledge` | RAG and embedding tools. |
| dev | `security` | Docker tools require `security`; Git tools use system `git`. |

### Operating System Notes

- **Linux**: All tests should pass without issues
- **macOS**: All tests should pass; clipboard tests may require additional permissions
- **Windows**: Some shell-based tests may need WSL

## Installation

### 1. Clone and Setup

```bash
git clone https://github.com/ckindle-42/pocketportal.git
cd pocketportal
```

### 2. Install Core Dependencies

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### 3. Verify Installation

```bash
# Check that pocketportal is installed
pocketportal --version

# Should output: pocketportal 4.7.4
```

## Running Tests

### Run All Tests

```bash
python -m pytest tests/ -v
```

### Run by Test Type

#### Unit Tests Only (Fast)

```bash
python -m pytest tests/unit/ -v -m unit
```

#### Integration Tests

```bash
python -m pytest tests/integration/ -v -m integration
```

#### End-to-End Tests

```bash
python -m pytest tests/e2e/ -v -m e2e
```

### Run Specific Test Files

```bash
# Test all Git tools
python -m pytest tests/unit/tools/test_git_tools.py -v

# Test Docker tools
python -m pytest tests/unit/tools/test_docker_tools.py -v

# Test CLI commands
python -m pytest tests/e2e/test_cli_commands.py -v
```

### Run with Coverage

```bash
# Generate coverage report
python -m pytest tests/ --cov=pocketportal --cov-report=html

# View coverage report
# Open htmlcov/index.html in browser
```

## Quick Reference

```bash
# Common test commands (copy-paste ready)

# Full test suite
python -m pytest tests/ -v

# Fast tests only
python -m pytest tests/unit/ -v -m unit

# With coverage
python -m pytest tests/ --cov=pocketportal --cov-report=term-missing

# Specific tool category
python -m pytest tests/unit/tools/test_git_tools.py -v

# Stop on first failure
python -m pytest tests/ -x

# Show test output
python -m pytest tests/ -v -s
```

## Troubleshooting

### ModuleNotFoundError: No module named 'pocketportal'

```bash
# Reinstall in editable mode
pip install -e .
```

### ImportError for optional dependencies

```bash
# Install specific dependency group
pip install -e ".[data]"
pip install -e ".[documents]"
```

### Docker tests fail

```bash
# Skip Docker tests if Docker is not available
python -m pytest -v -m "not requires_docker"
```

## Test Coverage

**All 33 tools have unit test coverage (100%)**

- Audio: 1 tool
- Automation: 2 tools
- Data: 5 tools
- Dev: 15 tools (Git + Docker + Python env)
- Utility: 9 tools
- Web: 1 tool

See `tests/unit/tools/` for individual test files.
