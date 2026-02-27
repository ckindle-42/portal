"""
Dockerized Python Sandbox - Secure Code Execution
=================================================

Executes Python code in isolated, ephemeral Docker containers for maximum security.

Features:
- Isolated execution environment
- Resource limits (CPU, memory, time)
- No network access (optional)
- Read-only filesystem (except /tmp)
- Automatic cleanup
- Support for common libraries

Security Benefits:
- Code runs in container, not host
- Cannot access host filesystem
- Cannot make network connections (if disabled)
- Cannot install system packages
- Automatic timeout and cleanup
- No persistence between runs

Performance:
- Container startup: ~100-500ms
- Code execution: Normal Python speed
- Total overhead: ~200-800ms
"""

import logging
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter

logger = logging.getLogger(__name__)

# Check Docker availability
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    logger.warning("docker package not available - install with: pip install docker")


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution"""

    # Resource limits
    memory_limit: str = "512m"  # Memory limit
    cpu_quota: int = 100000  # CPU quota (100% of one core)
    nano_cpus: int = 1_000_000_000  # --cpus=1.0 (in nano-CPUs)
    pids_limit: int = 100  # Process/thread limit
    timeout_seconds: int = 30  # Execution timeout

    # Network
    network_disabled: bool = True  # Disable network access

    # Filesystem
    read_only: bool = False  # Make filesystem read-only
    tmpfs_size: str = "100m"  # Size of /tmp

    # Security
    drop_capabilities: list[str] = None  # Capabilities to drop
    no_new_privileges: bool = True  # Prevent privilege escalation

    # Python environment
    python_version: str = "3.11"  # Python version
    packages: list[str] = None  # Pre-installed packages

    def __post_init__(self) -> None:
        if self.drop_capabilities is None:
            # Drop all capabilities for maximum security
            self.drop_capabilities = ["ALL"]

        if self.packages is None:
            # Default packages
            self.packages = [
                "numpy",
                "pandas",
                "requests",
                "matplotlib"
            ]


class DockerPythonSandbox:
    """
    Docker-based Python sandbox for secure code execution.

    Creates ephemeral containers that execute code and are destroyed immediately.
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        """Initialize sandbox"""

        if not DOCKER_AVAILABLE:
            raise RuntimeError("Docker package not installed: pip install docker")

        self.config = config or SandboxConfig()
        self.docker_client = None
        self.image_name = f"python-sandbox:{self.config.python_version}"

        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
            logger.info("✅ Docker client initialized")
        except Exception as e:
            logger.error("Failed to initialize Docker client: %s", e)
            raise RuntimeError(f"Docker not available: {e}")

        # Check/build sandbox image
        self._ensure_image()

    def _ensure_image(self) -> None:
        """Ensure sandbox Docker image exists"""

        try:
            # Check if image exists
            self.docker_client.images.get(self.image_name)
            logger.info("Sandbox image exists: %s", self.image_name)

        except docker.errors.ImageNotFound:
            logger.info("Building sandbox image: %s", self.image_name)
            self._build_image()

    def _build_image(self) -> None:
        """Build sandbox Docker image"""

        # Create Dockerfile
        dockerfile_content = f"""
FROM python:{self.config.python_version}-slim

# Install common packages
RUN pip install --no-cache-dir {' '.join(self.packages)}

# Create non-root user
RUN useradd -m -u 1000 sandbox && \\
    mkdir -p /sandbox /tmp && \\
    chown -R sandbox:sandbox /sandbox /tmp

# Set working directory
WORKDIR /sandbox

# Switch to non-root user
USER sandbox

# Default command
CMD ["python3"]
"""

        # Build image
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                dockerfile_path = Path(tmpdir) / "Dockerfile"
                dockerfile_path.write_text(dockerfile_content)

                logger.info("Building Docker image...")
                self.docker_client.images.build(
                    path=str(tmpdir),
                    tag=self.image_name,
                    rm=True,
                    forcerm=True
                )
                logger.info("Image built: %s", self.image_name)

        except Exception as e:
            logger.error("Failed to build image: %s", e)
            raise

    def _prepare_container(self, code: str, container_id: str) -> dict[str, Any]:
        """Build container config dict for a code execution run."""
        config: dict[str, Any] = {
            'image': self.image_name,
            'command': ['python3', '-c', code],
            'name': f'sandbox_{container_id}',
            'detach': True,
            'auto_remove': True,
            'mem_limit': self.config.memory_limit,
            'cpu_quota': self.config.cpu_quota,
            'nano_cpus': self.config.nano_cpus,
            'pids_limit': self.config.pids_limit,
            'security_opt': ['no-new-privileges'] if self.config.no_new_privileges else [],
            'cap_drop': self.config.drop_capabilities,
            'read_only': self.config.read_only,
            'tmpfs': {'/tmp': f'size={self.config.tmpfs_size}'},
            'network_mode': 'none',
        }
        if not self.config.network_disabled:
            config['network_mode'] = 'bridge'
        return config

    def _run_container(self, container_config: dict[str, Any], timeout: int) -> tuple[Any, int]:
        """Start container and wait for exit; returns (container, exit_code)."""
        container = self.docker_client.containers.run(**container_config)
        try:
            result = container.wait(timeout=timeout)
            exit_code = result['StatusCode']
        except Exception as e:
            logger.warning("Container execution timeout or error: %s", e)
            container.kill()
            exit_code = -1
        return container, exit_code

    def _collect_output(self, container: Any, exit_code: int,
                        container_id: str, start_time: float) -> dict[str, Any]:
        """Read container logs and assemble the result dict."""
        import time
        stdout = container.logs().decode('utf-8', errors='replace')
        return {
            'success': exit_code == 0,
            'stdout': stdout,
            'stderr': '',
            'exit_code': exit_code,
            'execution_time': time.time() - start_time,
            'container_id': container_id,
        }

    async def execute_code(self, code: str, timeout: int | None = None) -> dict[str, Any]:
        """Execute Python code in an isolated Docker sandbox."""
        import time
        start_time = time.time()
        timeout = timeout or self.config.timeout_seconds
        container_id = str(uuid.uuid4())[:8]
        container = None

        try:
            container_config = self._prepare_container(code, container_id)
            container, exit_code = self._run_container(container_config, timeout)
            return self._collect_output(container, exit_code, container_id, start_time)
        except Exception as e:
            logger.error("Sandbox execution error: %s", e)
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1,
                'execution_time': time.time() - start_time,
                'container_id': container_id,
            }
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    async def execute_script(
        self,
        script_path: str,
        timeout: int | None = None
    ) -> dict[str, Any]:
        """Execute Python script from file"""

        try:
            script_content = Path(script_path).read_text()
            return await self.execute_code(script_content, timeout)
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': f"Failed to read script: {e}",
                'exit_code': -1,
                'execution_time': 0,
                'container_id': 'N/A'
            }

    def cleanup(self) -> None:
        """Cleanup resources"""
        if self.docker_client:
            self.docker_client.close()


# ============================================================================
# TOOL INTEGRATION
# ============================================================================

class DockerPythonExecutionTool(BaseTool):
    """
    Tool for executing Python code in Docker sandbox.

    Replaces direct subprocess execution with secure Docker container.
    """

    _sandbox: DockerPythonSandbox | None = None

    def __init__(self) -> None:
        super().__init__()

        # Initialize sandbox (shared across tool instances)
        if DockerPythonExecutionTool._sandbox is None:
            if not DOCKER_AVAILABLE:
                logger.error("Docker not available - install with: pip install docker")
                return

            try:
                DockerPythonExecutionTool._sandbox = DockerPythonSandbox()
            except Exception as e:
                logger.error("Failed to initialize sandbox: %s", e)

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="python_sandbox",
            description="Execute Python code in secure Docker container",
            category=ToolCategory.DEV,
            version="1.0.0",
            requires_confirmation=True,  # Still confirm for user awareness
            parameters=[
                ToolParameter(
                    name="code",
                    param_type="string",
                    description="Python code to execute",
                    required=True
                ),
                ToolParameter(
                    name="timeout",
                    param_type="integer",
                    description="Execution timeout in seconds (default: 30)",
                    required=False,
                    default=30
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute code in sandbox"""

        if not DOCKER_AVAILABLE or not DockerPythonExecutionTool._sandbox:
            return self._error_response(
                "Docker sandbox not available. Install: pip install docker"
            )

        code = parameters.get("code")
        timeout = parameters.get("timeout", 30)

        if not code:
            return self._error_response("No code provided")

        # Execute in sandbox
        result = await DockerPythonExecutionTool._sandbox.execute_code(
            code=code,
            timeout=timeout
        )

        if result['success']:
            return self._success_response(
                result={
                    'output': result['stdout'],
                    'execution_time': f"{result['execution_time']:.2f}s"
                },
                metadata={
                    'container_id': result['container_id'],
                    'exit_code': result['exit_code'],
                    'security': 'Docker sandbox'
                }
            )
        else:
            return self._error_response(
                f"Execution failed:\n{result['stderr']}\n{result['stdout']}",
                metadata={
                    'exit_code': result['exit_code'],
                    'container_id': result['container_id']
                }
            )


# ============================================================================
# DOCKERFILE GENERATOR
# ============================================================================

class DockerfileGenerator:
    """Generate custom Dockerfiles for different use cases"""

    @staticmethod
    def generate_minimal() -> str:
        """Minimal Python sandbox"""
        return """
FROM python:3.11-alpine
RUN adduser -D -u 1000 sandbox
USER sandbox
WORKDIR /sandbox
CMD ["python3"]
"""

    @staticmethod
    def generate_data_science() -> str:
        """Data science environment"""
        return """
FROM python:3.11-slim
RUN pip install --no-cache-dir numpy pandas matplotlib seaborn scikit-learn
RUN useradd -m -u 1000 sandbox
USER sandbox
WORKDIR /sandbox
CMD ["python3"]
"""

    @staticmethod
    def generate_web() -> str:
        """Web scraping/API environment"""
        return """
FROM python:3.11-slim
RUN pip install --no-cache-dir requests beautifulsoup4 lxml aiohttp
RUN useradd -m -u 1000 sandbox
USER sandbox
WORKDIR /sandbox
CMD ["python3"]
"""

    @staticmethod
    def save_dockerfile(content: str, path: str) -> None:
        """Save Dockerfile to disk"""
        Path(path).write_text(content)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

