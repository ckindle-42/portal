# Integration Tests

This directory contains integration tests that require external dependencies:
- Docker containers
- Network connectivity
- Database connections
- LLM backends

## Running Integration Tests

```bash
# Run all integration tests
pytest tests/integration -v

# Run specific integration test
pytest tests/integration/test_docker_integration.py -v

# Skip integration tests (run only unit tests)
pytest tests/unit -v
```

## Markers

All tests in this directory should be marked with:
```python
@pytest.mark.integration
```

## Requirements

Integration tests may require:
- Docker daemon running
- Network access
- Specific environment variables
- External services (databases, APIs)
