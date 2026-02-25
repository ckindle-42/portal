"""
MCP Security Policy - Granular Access Control for MCP Servers
==============================================================

When Portal acts as an MCP *Client*, it needs granular permissions
to control what MCP servers can access.

Examples:
- Allow filesystem access only to /tmp
- Allow network access only to specific domains
- Deny root/privileged operations
- Limit resource usage (CPU, memory, disk)

This prevents MCP servers from having unrestricted access to the system.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AccessLevel(Enum):
    """Access levels for MCP servers"""
    NONE = "none"           # No access
    READ_ONLY = "read"      # Read-only access
    READ_WRITE = "write"    # Read and write access
    PRIVILEGED = "privileged"  # Full access (use with caution!)


@dataclass
class FileSystemPolicy:
    """Filesystem access policy for MCP servers"""
    access_level: AccessLevel = AccessLevel.NONE
    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=list)
    max_file_size_mb: int = 100

    def can_access(self, path: str, write: bool = False) -> bool:
        """
        Check if access to a path is allowed

        Args:
            path: File path to check
            write: Whether write access is requested

        Returns:
            True if access is allowed
        """
        # Check access level
        if self.access_level == AccessLevel.NONE:
            return False

        if write and self.access_level == AccessLevel.READ_ONLY:
            return False

        # Check denied paths (takes precedence)
        for denied in self.denied_paths:
            if path.startswith(denied):
                return False

        # Check allowed paths
        if not self.allowed_paths:
            # If no allowed paths specified, allow all (except denied)
            return True

        for allowed in self.allowed_paths:
            if path.startswith(allowed):
                return True

        return False


@dataclass
class NetworkPolicy:
    """Network access policy for MCP servers"""
    access_level: AccessLevel = AccessLevel.NONE
    allowed_domains: List[str] = field(default_factory=list)
    denied_domains: List[str] = field(default_factory=list)
    allowed_ports: List[int] = field(default_factory=lambda: [80, 443])

    def can_access(self, domain: str, port: int = 443) -> bool:
        """
        Check if network access is allowed

        Args:
            domain: Domain to access
            port: Port number

        Returns:
            True if access is allowed
        """
        if self.access_level == AccessLevel.NONE:
            return False

        # Check port
        if self.allowed_ports and port not in self.allowed_ports:
            return False

        # Check denied domains
        for denied in self.denied_domains:
            if domain.endswith(denied):
                return False

        # Check allowed domains
        if not self.allowed_domains:
            return True

        for allowed in self.allowed_domains:
            if domain.endswith(allowed):
                return True

        return False


@dataclass
class ResourcePolicy:
    """Resource usage policy for MCP servers"""
    max_cpu_percent: int = 50       # Max CPU usage percentage
    max_memory_mb: int = 512        # Max memory in MB
    max_execution_time_sec: int = 300  # Max execution time in seconds
    max_disk_usage_mb: int = 1024   # Max disk usage in MB


@dataclass
class MCPSecurityPolicy:
    """
    Complete security policy for an MCP server

    This defines what an MCP server can and cannot do when
    connected to Portal.

    Example:
        # Strict policy - only /tmp access
        policy = MCPSecurityPolicy(
            server_name="my-mcp-server",
            filesystem=FileSystemPolicy(
                access_level=AccessLevel.READ_WRITE,
                allowed_paths=["/tmp"],
                max_file_size_mb=10
            ),
            network=NetworkPolicy(
                access_level=AccessLevel.READ_ONLY,
                allowed_domains=["api.example.com"]
            )
        )

        # Check access
        assert policy.filesystem.can_access("/tmp/file.txt", write=True)
        assert not policy.filesystem.can_access("/etc/passwd")
    """
    server_name: str
    enabled: bool = True

    # Policies
    filesystem: FileSystemPolicy = field(default_factory=FileSystemPolicy)
    network: NetworkPolicy = field(default_factory=NetworkPolicy)
    resources: ResourcePolicy = field(default_factory=ResourcePolicy)

    # Advanced
    allow_shell_execution: bool = False
    allow_privileged_operations: bool = False
    require_approval_for_destructive_ops: bool = True

    def validate(self):
        """Validate policy configuration"""
        if self.allow_privileged_operations:
            logger.warning(
                f"⚠️  MCP server '{self.server_name}' has PRIVILEGED access!",
                server=self.server_name
            )

        if self.allow_shell_execution:
            logger.warning(
                f"⚠️  MCP server '{self.server_name}' can execute shell commands!",
                server=self.server_name
            )


# Predefined policies
SANDBOXED_POLICY = MCPSecurityPolicy(
    server_name="default-sandboxed",
    filesystem=FileSystemPolicy(
        access_level=AccessLevel.READ_WRITE,
        allowed_paths=["/tmp"],
        max_file_size_mb=10
    ),
    network=NetworkPolicy(
        access_level=AccessLevel.NONE
    ),
    allow_shell_execution=False,
    allow_privileged_operations=False
)

TRUSTED_POLICY = MCPSecurityPolicy(
    server_name="default-trusted",
    filesystem=FileSystemPolicy(
        access_level=AccessLevel.READ_WRITE,
        allowed_paths=["/home", "/tmp"],
        denied_paths=["/home/.ssh", "/home/.aws"],
        max_file_size_mb=100
    ),
    network=NetworkPolicy(
        access_level=AccessLevel.READ_WRITE,
        allowed_ports=[80, 443, 8080]
    ),
    allow_shell_execution=False,
    allow_privileged_operations=False
)

UNRESTRICTED_POLICY = MCPSecurityPolicy(
    server_name="default-unrestricted",
    filesystem=FileSystemPolicy(
        access_level=AccessLevel.PRIVILEGED
    ),
    network=NetworkPolicy(
        access_level=AccessLevel.PRIVILEGED
    ),
    allow_shell_execution=True,
    allow_privileged_operations=True,
    require_approval_for_destructive_ops=True
)
