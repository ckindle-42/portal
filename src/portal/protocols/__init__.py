"""
Protocols Package
=================

Protocol-level integrations that are first-class citizens
in the Portal architecture.

Modules:
--------
- mcp: Model Context Protocol (bidirectional client/server)
- resource_resolver: Universal resource access (file/web/mcp/db)

Unlike tools (which are user-facing features), protocols are
infrastructure-level integrations that enable core functionality.
"""

from .resource_resolver import (
    UniversalResourceResolver,
    Resource,
    ResourceProvider,
    FileSystemProvider,
    WebProvider,
    MCPProvider,
    DatabaseProvider,
)

__all__ = [
    # Resource Resolution
    'UniversalResourceResolver',
    'Resource',
    'ResourceProvider',
    'FileSystemProvider',
    'WebProvider',
    'MCPProvider',
    'DatabaseProvider',
]
