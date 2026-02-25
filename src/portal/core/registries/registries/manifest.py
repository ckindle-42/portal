"""
Tool Manifest Schema
=====================

Standardized metadata for all tools, including security scopes, operational
characteristics, and resource requirements.

This enables:
- Trust-based execution (Level 0/1/2 sandboxing)
- Queue routing decisions (CPU/network intensive jobs)
- Security access control (READ_ONLY vs READ_WRITE)
- Operational monitoring and metrics
"""

from enum import Enum, IntEnum
from typing import Optional, List, Set
from pydantic import BaseModel, Field


class TrustLevel(IntEnum):
    """
    Trust levels for tools.

    - CORE (0): Internal system tools, fully trusted
    - VERIFIED (1): Installed via pip/official plugins, verified signatures
    - UNTRUSTED (2): Dynamic code execution, user-provided scripts

    Level 2 tools MUST always use Docker Sandbox in production.
    """
    CORE = 0
    VERIFIED = 1
    UNTRUSTED = 2


class SecurityScope(str, Enum):
    """Security scope for tool operations"""
    READ_ONLY = "read_only"           # Can only read data
    READ_WRITE = "read_write"         # Can read and write data
    SYSTEM_MODIFY = "system_modify"   # Can modify system state (create files, etc.)
    NETWORK_ACCESS = "network_access" # Requires internet access
    PRIVILEGED = "privileged"         # Requires elevated privileges


class ResourceProfile(str, Enum):
    """Resource usage profile for queue routing"""
    LIGHTWEIGHT = "lightweight"       # <100ms, minimal CPU/memory
    NORMAL = "normal"                 # <1s, moderate resources
    CPU_INTENSIVE = "cpu_intensive"   # Heavy computation (video, OCR, ML)
    IO_INTENSIVE = "io_intensive"     # Heavy I/O (large file processing)
    NETWORK_INTENSIVE = "network_intensive"  # Heavy network usage (downloads, scraping)


class ToolManifest(BaseModel):
    """
    Complete manifest for a tool.

    Every tool MUST return this manifest for standardized handling.

    Example:
    --------
    manifest = ToolManifest(
        name="file_reader",
        description="Read local files",
        trust_level=TrustLevel.CORE,
        security_scopes={SecurityScope.READ_ONLY},
        resource_profile=ResourceProfile.LIGHTWEIGHT,
        is_idempotent=True,
        requires_internet=False,
        timeout_seconds=5
    )
    """

    # Identity
    name: str = Field(..., description="Unique tool name")
    description: str = Field(..., description="Human-readable description")
    version: str = Field(default="1.0.0", description="Tool version")

    # Security
    trust_level: TrustLevel = Field(
        default=TrustLevel.VERIFIED,
        description="Trust level (CORE/VERIFIED/UNTRUSTED)"
    )
    security_scopes: Set[SecurityScope] = Field(
        default_factory=lambda: {SecurityScope.READ_ONLY},
        description="Required security permissions"
    )
    requires_sandbox: bool = Field(
        default=False,
        description="Must run in Docker sandbox (auto-true for UNTRUSTED)"
    )

    # Operational Characteristics
    resource_profile: ResourceProfile = Field(
        default=ResourceProfile.NORMAL,
        description="Resource usage profile for queue routing"
    )
    is_idempotent: bool = Field(
        default=False,
        description="Safe to retry on failure without side effects"
    )
    requires_internet: bool = Field(
        default=False,
        description="Requires internet connectivity"
    )

    # Performance & Reliability
    timeout_seconds: int = Field(
        default=30,
        description="Max execution time before timeout",
        ge=1,
        le=600
    )
    max_retries: int = Field(
        default=3,
        description="Max retry attempts on failure",
        ge=0,
        le=10
    )

    # Dependencies
    required_packages: List[str] = Field(
        default_factory=list,
        description="Python packages required (e.g., ['pandas', 'numpy'])"
    )
    required_binaries: List[str] = Field(
        default_factory=list,
        description="System binaries required (e.g., ['ffmpeg', 'git'])"
    )

    # Metadata
    author: Optional[str] = Field(
        default=None,
        description="Tool author/maintainer"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Categorization tags (e.g., ['file', 'data', 'analysis'])"
    )

    class Config:
        """Pydantic config"""
        use_enum_values = False  # Keep enum objects, not values

    def enforce_security_policy(self) -> "ToolManifest":
        """
        Enforce security policies.

        - UNTRUSTED tools MUST use sandbox
        - PRIVILEGED scope requires VERIFIED or CORE trust

        Returns:
            Self (for chaining)

        Raises:
            ValueError: If security policy is violated
        """
        # UNTRUSTED tools must use sandbox
        if self.trust_level == TrustLevel.UNTRUSTED:
            self.requires_sandbox = True

        # PRIVILEGED scope requires high trust
        if SecurityScope.PRIVILEGED in self.security_scopes:
            if self.trust_level == TrustLevel.UNTRUSTED:
                raise ValueError(
                    f"Tool '{self.name}' has PRIVILEGED scope but UNTRUSTED level. "
                    "PRIVILEGED requires VERIFIED or CORE trust."
                )

        return self

    def to_dict(self) -> dict:
        """Convert to dictionary with enum values as strings"""
        data = self.model_dump()

        # Convert enums to their values
        data['trust_level'] = self.trust_level.value
        data['security_scopes'] = [scope.value for scope in self.security_scopes]
        data['resource_profile'] = self.resource_profile.value

        return data


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_core_manifest(
    name: str,
    description: str,
    is_idempotent: bool = False,
    requires_internet: bool = False,
    timeout_seconds: int = 30,
    **kwargs
) -> ToolManifest:
    """
    Create a manifest for a CORE system tool.

    Core tools are fully trusted and don't require sandboxing.
    """
    return ToolManifest(
        name=name,
        description=description,
        trust_level=TrustLevel.CORE,
        is_idempotent=is_idempotent,
        requires_internet=requires_internet,
        timeout_seconds=timeout_seconds,
        **kwargs
    ).enforce_security_policy()


def create_plugin_manifest(
    name: str,
    description: str,
    security_scopes: Set[SecurityScope],
    resource_profile: ResourceProfile = ResourceProfile.NORMAL,
    **kwargs
) -> ToolManifest:
    """
    Create a manifest for a VERIFIED plugin tool.

    Plugin tools are verified but may require specific security scopes.
    """
    return ToolManifest(
        name=name,
        description=description,
        trust_level=TrustLevel.VERIFIED,
        security_scopes=security_scopes,
        resource_profile=resource_profile,
        **kwargs
    ).enforce_security_policy()


def create_untrusted_manifest(
    name: str,
    description: str,
    **kwargs
) -> ToolManifest:
    """
    Create a manifest for an UNTRUSTED tool.

    Untrusted tools ALWAYS run in sandbox, regardless of other settings.
    """
    return ToolManifest(
        name=name,
        description=description,
        trust_level=TrustLevel.UNTRUSTED,
        requires_sandbox=True,  # Always true
        **kwargs
    ).enforce_security_policy()
