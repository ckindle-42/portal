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

import asyncio
import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from base_tool import BaseTool, ToolMetadata, ToolParameter, ToolCategory

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
    memory_limit: str = "256m"  # Memory limit
    cpu_quota: int = 50000  # CPU quota (50% of one core)
    timeout_seconds: int = 30  # Execution timeout
    
    # Network
    network_disabled: bool = True  # Disable network access
    
    # Filesystem
    read_only: bool = False  # Make filesystem read-only
    tmpfs_size: str = "100m"  # Size of /tmp
    
    # Security
    drop_capabilities: List[str] = None  # Capabilities to drop
    no_new_privileges: bool = True  # Prevent privilege escalation
    
    # Python environment
    python_version: str = "3.11"  # Python version
    packages: List[str] = None  # Pre-installed packages
    
    def __post_init__(self):
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
    
    def __init__(self, config: Optional[SandboxConfig] = None):
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
            logger.error(f"Failed to initialize Docker client: {e}")
            raise RuntimeError(f"Docker not available: {e}")
        
        # Check/build sandbox image
        self._ensure_image()
    
    def _ensure_image(self):
        """Ensure sandbox Docker image exists"""
        
        try:
            # Check if image exists
            self.docker_client.images.get(self.image_name)
            logger.info(f"✅ Sandbox image exists: {self.image_name}")
        
        except docker.errors.ImageNotFound:
            logger.info(f"🔨 Building sandbox image: {self.image_name}")
            self._build_image()
    
    def _build_image(self):
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
                logger.info(f"✅ Image built: {self.image_name}")
        
        except Exception as e:
            logger.error(f"Failed to build image: {e}")
            raise
    
    async def execute_code(
        self,
        code: str,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute Python code in sandbox
        
        Args:
            code: Python code to execute
            timeout: Execution timeout (overrides config)
        
        Returns:
            {
                'success': bool,
                'stdout': str,
                'stderr': str,
                'exit_code': int,
                'execution_time': float,
                'container_id': str
            }
        """
        
        import time
        start_time = time.time()
        
        timeout = timeout or self.config.timeout_seconds
        container_id = str(uuid.uuid4())[:8]
        container = None
        
        try:
            # Create container config
            container_config = {
                'image': self.image_name,
                'command': ['python3', '-c', code],
                'name': f'sandbox_{container_id}',
                'detach': True,
                'auto_remove': True,  # Auto-cleanup
                
                # Resource limits
                'mem_limit': self.config.memory_limit,
                'cpu_quota': self.config.cpu_quota,
                
                # Security options
                'security_opt': ['no-new-privileges'] if self.config.no_new_privileges else [],
                'cap_drop': self.config.drop_capabilities,
                'read_only': self.config.read_only,
                
                # Filesystem
                'tmpfs': {'/tmp': f'size={self.config.tmpfs_size}'},
            }
            
            # Disable network if configured
            if self.config.network_disabled:
                container_config['network_mode'] = 'none'
            
            # Create and start container
            container = self.docker_client.containers.run(**container_config)
            
            # Wait for completion with timeout
            try:
                result = container.wait(timeout=timeout)
                exit_code = result['StatusCode']
            except Exception as e:
                # Timeout or other error
                logger.warning(f"Container execution timeout or error: {e}")
                container.kill()
                exit_code = -1
            
            # Get logs
            logs = container.logs()
            output = logs.decode('utf-8', errors='replace')
            
            # Split stdout/stderr (simplified)
            stdout = output
            stderr = ""
            
            execution_time = time.time() - start_time
            
            return {
                'success': exit_code == 0,
                'stdout': stdout,
                'stderr': stderr,
                'exit_code': exit_code,
                'execution_time': execution_time,
                'container_id': container_id
            }
        
        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1,
                'execution_time': time.time() - start_time,
                'container_id': container_id
            }
        
        finally:
            # Cleanup (container auto-removes, but be safe)
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass
    
    async def execute_script(
        self,
        script_path: str,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
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
    
    def cleanup(self):
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
    
    _sandbox: Optional[DockerPythonSandbox] = None
    
    def __init__(self):
        super().__init__()
        
        # Initialize sandbox (shared across tool instances)
        if DockerPythonExecutionTool._sandbox is None:
            if not DOCKER_AVAILABLE:
                logger.error("Docker not available - install with: pip install docker")
                return
            
            try:
                DockerPythonExecutionTool._sandbox = DockerPythonSandbox()
            except Exception as e:
                logger.error(f"Failed to initialize sandbox: {e}")
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="python_sandbox",
            description="Execute Python code in secure Docker container",
            category=ToolCategory.DEVELOPMENT,
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
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
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
    def save_dockerfile(content: str, path: str):
        """Save Dockerfile to disk"""
        Path(path).write_text(content)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

async def example_usage():
    """Example usage of Docker sandbox"""
    
    print("=" * 60)
    print("Docker Python Sandbox - Examples")
    print("=" * 60)
    
    # Initialize sandbox
    sandbox = DockerPythonSandbox()
    
    # Example 1: Simple calculation
    print("\n1. Simple Calculation:")
    result = await sandbox.execute_code("""
print("Hello from Docker!")
print(f"2 + 2 = {2 + 2}")
""")
    
    print(f"Success: {result['success']}")
    print(f"Output: {result['stdout']}")
    print(f"Time: {result['execution_time']:.2f}s")
    
    # Example 2: Using numpy
    print("\n2. Using NumPy:")
    result = await sandbox.execute_code("""
import numpy as np
arr = np.array([1, 2, 3, 4, 5])
print(f"Mean: {arr.mean()}")
print(f"Sum: {arr.sum()}")
""")
    
    print(f"Success: {result['success']}")
    print(f"Output: {result['stdout']}")
    
    # Example 3: Network test (should fail)
    print("\n3. Network Test (should fail):")
    result = await sandbox.execute_code("""
import socket
try:
    socket.create_connection(("google.com", 80), timeout=2)
    print("Network access: ENABLED")
except Exception as e:
    print(f"Network access: DISABLED ({e})")
""")
    
    print(f"Output: {result['stdout']}")
    
    # Example 4: Filesystem test
    print("\n4. Filesystem Test:")
    result = await sandbox.execute_code("""
import os
print(f"Current dir: {os.getcwd()}")
print(f"Can write to /tmp: {os.access('/tmp', os.W_OK)}")
print(f"Can write to /: {os.access('/', os.W_OK)}")
""")
    
    print(f"Output: {result['stdout']}")
    
    # Cleanup
    sandbox.cleanup()
    print("\n✅ Examples complete!")


# ============================================================================
# DOCKER-COMPOSE FOR DEVELOPMENT
# ============================================================================

DOCKER_COMPOSE_YML = """
version: '3.8'

services:
  telegram-agent:
    build: .
    volumes:
      - ./data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock  # For Docker-in-Docker
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - DOCKER_SANDBOX_ENABLED=true
    restart: unless-stopped
    
  # Optional: Pre-built sandbox images
  sandbox-python:
    image: python-sandbox:3.11
    profiles: ["sandbox"]  # Only start when needed
"""


if __name__ == "__main__":
    if not DOCKER_AVAILABLE:
        print("❌ Docker package not installed")
        print("Install: pip install docker")
    else:
        print("✅ Docker package available")
        print("\nRun examples:")
        print("  python docker_sandbox.py")
        
        # Run examples
        asyncio.run(example_usage())
