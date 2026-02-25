# End-to-End Tests

This directory contains end-to-end (E2E) tests for PocketPortal.

## Test Files

- `test_phase2_standalone.py`: Async Job Queue system tests
- `test_phase3_standalone.py`: MCP protocol and resource resolution tests
- `test_phase4_standalone.py`: Observability features tests

## Running E2E Tests

```bash
# Run all e2e tests
pytest tests/e2e/

# Run specific test file
pytest tests/e2e/test_phase2_standalone.py

# Run with verbose output
pytest -v tests/e2e/
```

## Guidelines

E2E tests should:
- Test complete workflows across multiple components
- May require external dependencies (Docker, network, etc.)
- Use the `@pytest.mark.integration` marker
- Include proper setup and teardown
- Verify end-to-end functionality, not individual units
