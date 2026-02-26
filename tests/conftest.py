"""
Pytest configuration for all Portal tests — validates the environment,
registers markers, and applies xfail markers to known-failing legacy API tests.
"""

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

# =============================================================================
# SHARED FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmp_dir = tempfile.mkdtemp()
    yield Path(tmp_dir)
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def mock_file_system(temp_dir):
    """Mock file system with a test directory."""
    test_file = temp_dir / "test_file.txt"
    test_file.write_text("test content")
    test_dir = temp_dir / "test_subdir"
    test_dir.mkdir()
    return {"root": temp_dir, "file": test_file, "dir": test_dir}


@pytest.fixture
def mock_subprocess():
    """Mock subprocess calls."""
    mock = Mock()
    mock.run = Mock(return_value=Mock(returncode=0, stdout="mock output", stderr=""))
    return mock


@pytest.fixture
def mock_docker_client():
    """Mock Docker client."""
    mock_client = Mock()
    mock_client.containers = Mock()
    mock_client.containers.list = Mock(return_value=[])
    mock_client.containers.run = Mock(return_value=Mock(id="mock_container_id"))
    mock_client.containers.get = Mock(
        return_value=Mock(
            id="mock_container_id",
            status="running",
            logs=Mock(return_value=b"mock logs"),
        )
    )
    return mock_client


@pytest.fixture
def mock_git_repo(temp_dir):
    """Mock Git repository."""
    git_dir = temp_dir / ".git"
    git_dir.mkdir()
    return temp_dir


@pytest.fixture
def sample_csv_file(temp_dir):
    """Create a sample CSV file for testing."""
    csv_file = temp_dir / "test.csv"
    csv_file.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n")
    return csv_file


@pytest.fixture
def sample_json_file(temp_dir):
    """Create a sample JSON file for testing."""
    json_file = temp_dir / "test.json"
    json_file.write_text('{"name": "test", "value": 123}')
    return json_file


@pytest.fixture
def mock_http_response():
    """Mock HTTP response."""
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.text = "mock response"
    mock_resp.json = Mock(return_value={"status": "ok"})
    mock_resp.headers = {"Content-Type": "application/json"}
    return mock_resp


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp ClientSession."""
    mock_session = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value="mock response")
    mock_resp.json = AsyncMock(return_value={"status": "ok"})
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.post = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


@pytest.fixture
def tool_success_params():
    """Standard parameters for successful tool execution."""
    return {"dry_run": False, "verbose": False}


@pytest.fixture
def mock_logger():
    """Mock logger to prevent log spam during tests."""
    return Mock()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def assert_tool_success(result: dict[str, Any]):
    """Assert that a tool execution was successful."""
    assert isinstance(result, dict), "Result should be a dictionary"
    assert result.get("success") is True, f"Tool should succeed: {result}"
    assert "result" in result or "data" in result, "Result should contain result or data"


def assert_tool_failure(result: dict[str, Any], expected_error: str = None):
    """Assert that a tool execution failed as expected."""
    assert isinstance(result, dict), "Result should be a dictionary"
    assert result.get("success") is False, "Tool should fail"
    assert "error" in result, "Failed result should contain error message"
    if expected_error:
        assert expected_error.lower() in result["error"].lower(), (
            f"Expected error '{expected_error}' not in '{result['error']}'"
        )


def create_mock_tool_response(success: bool = True, **kwargs) -> dict[str, Any]:
    """Create a mock tool response."""
    if success:
        return {"success": True, "result": kwargs.get("result", "mock result"), **kwargs}
    return {"success": False, "error": kwargs.get("error", "mock error"), **kwargs}


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================


def pytest_configure(config):
    """Validate test environment and configure pytest with custom markers."""
    missing = []
    for mod in ("httpx", "aiohttp", "fastapi", "pydantic"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)

    if missing:
        print(
            "\n"
            "=" * 70 + "\n"
            " TEST ENVIRONMENT ERROR\n"
            "=" * 70 + "\n"
            f"\n"
            f" Missing dependencies: {', '.join(missing)}\n"
            f"\n"
            f" Portal must be installed before running tests.\n"
            f" Run one of:\n"
            f"\n"
            f"   pip install -e '.[dev]'     # pip (includes all extras)\n"
            f"   uv sync --all-extras --dev  # uv\n"
            f"   make install                # Makefile shortcut\n"
            f"\n"
            "=" * 70,
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        import portal  # noqa: F401
    except ImportError:
        print(
            "\n"
            "=" * 70 + "\n"
            " Portal package not installed.\n"
            " Run: pip install -e '.[dev]'\n"
            "=" * 70,
            file=sys.stderr,
        )
        raise SystemExit(1)

    config.addinivalue_line(
        "markers", "unit: Fast unit tests with no external dependencies"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests requiring external services"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests for full workflows"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take more than 5 seconds"
    )
    config.addinivalue_line(
        "markers", "requires_docker: Tests requiring Docker"
    )
    config.addinivalue_line(
        "markers", "requires_llm: Tests requiring LLM backend"
    )
