"""
Universal Resource Resolver
============================

Unified interface for accessing resources from multiple sources:
- Local filesystem (file://)
- Web resources (http://, https://)
- MCP resources (mcp://server/resource)
- Database records (db://table/id)
- Conversation history (conversation://chat_id)
- Knowledge base (knowledge://doc_id)

This provides a consistent API regardless of resource location.

Example:
--------
resolver = UniversalResourceResolver()

# All return the same Resource object
file = await resolver.resolve("file:///home/user/doc.txt")
web = await resolver.resolve("https://example.com/page.html")
mcp = await resolver.resolve("mcp://github/repos/owner/repo")
db = await resolver.resolve("db://users/123")
"""

import logging
from typing import Dict, Any, Optional, Protocol, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

logger = logging.getLogger(__name__)


# =============================================================================
# RESOURCE DATA MODEL
# =============================================================================


@dataclass
class Resource:
    """
    Unified resource representation.

    All resources (files, web pages, MCP resources, etc.)
    are represented using this common format.
    """
    uri: str
    content: str
    content_type: str = "text/plain"
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'uri': self.uri,
            'content': self.content,
            'content_type': self.content_type,
            'metadata': self.metadata or {},
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'source': self.source
        }


# =============================================================================
# RESOURCE PROVIDER INTERFACE
# =============================================================================


class ResourceProvider(ABC):
    """
    Abstract interface for resource providers.

    Each provider handles a specific URI scheme (file://, http://, mcp://, etc.)
    """

    @abstractmethod
    def can_handle(self, uri: str) -> bool:
        """Check if this provider can handle the given URI"""
        pass

    @abstractmethod
    async def resolve(self, uri: str) -> Resource:
        """Resolve URI to a resource"""
        pass

    @abstractmethod
    def get_schemes(self) -> List[str]:
        """Get list of URI schemes this provider handles"""
        pass


# =============================================================================
# FILE SYSTEM PROVIDER
# =============================================================================


class FileSystemProvider(ResourceProvider):
    """Provider for local filesystem resources (file://)"""

    def can_handle(self, uri: str) -> bool:
        """Check if URI is a file path"""
        return uri.startswith("file://") or Path(uri).exists()

    async def resolve(self, uri: str) -> Resource:
        """Read file from filesystem"""
        # Remove file:// prefix if present
        path_str = uri.replace("file://", "")
        path = Path(path_str)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {uri}")

        # Read file content
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Binary file
            content = f"<binary file: {path.name}, {path.stat().st_size} bytes>"

        # Determine content type from extension
        content_type = self._guess_content_type(path.suffix)

        return Resource(
            uri=uri,
            content=content,
            content_type=content_type,
            metadata={
                'path': str(path.absolute()),
                'size': path.stat().st_size,
                'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            },
            timestamp=datetime.now(),
            source='filesystem'
        )

    def get_schemes(self) -> List[str]:
        """Get supported schemes"""
        return ["file"]

    def _guess_content_type(self, suffix: str) -> str:
        """Guess content type from file extension"""
        type_map = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.py': 'text/x-python',
            '.js': 'text/javascript',
            '.html': 'text/html',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
        }
        return type_map.get(suffix.lower(), 'application/octet-stream')


# =============================================================================
# WEB PROVIDER
# =============================================================================


class WebProvider(ResourceProvider):
    """Provider for web resources (http://, https://)"""

    def can_handle(self, uri: str) -> bool:
        """Check if URI is a web URL"""
        return uri.startswith("http://") or uri.startswith("https://")

    async def resolve(self, uri: str) -> Resource:
        """Fetch resource from web"""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(uri) as response:
                    content = await response.text()
                    content_type = response.headers.get('Content-Type', 'text/html')

                    return Resource(
                        uri=uri,
                        content=content,
                        content_type=content_type,
                        metadata={
                            'status': response.status,
                            'headers': dict(response.headers)
                        },
                        timestamp=datetime.now(),
                        source='web'
                    )

        except Exception as e:
            logger.exception(f"Failed to fetch web resource: {uri}")
            raise RuntimeError(f"Web fetch failed: {e}")

    def get_schemes(self) -> List[str]:
        """Get supported schemes"""
        return ["http", "https"]


# =============================================================================
# MCP PROVIDER
# =============================================================================


class MCPProvider(ResourceProvider):
    """Provider for MCP resources (mcp://server/resource)"""

    def __init__(self, mcp_connector: Optional[Any] = None):
        """
        Initialize MCP provider.

        Args:
            mcp_connector: Optional MCP connector instance
        """
        self.mcp_connector = mcp_connector

    def can_handle(self, uri: str) -> bool:
        """Check if URI is an MCP resource"""
        return uri.startswith("mcp://")

    async def resolve(self, uri: str) -> Resource:
        """Resolve MCP resource"""
        if self.mcp_connector is None:
            raise RuntimeError("MCP connector not configured")

        # Parse URI: mcp://server/resource_path
        match = re.match(r'mcp://([^/]+)/(.*)', uri)
        if not match:
            raise ValueError(f"Invalid MCP URI: {uri}")

        server_name = match.group(1)
        resource_path = match.group(2)

        # Use MCP connector to fetch resource
        # (Implementation depends on MCP connector API)
        logger.info(f"Resolving MCP resource: {uri}")

        # Placeholder implementation
        return Resource(
            uri=uri,
            content=f"MCP resource from {server_name}: {resource_path}",
            content_type='text/plain',
            metadata={'server': server_name, 'path': resource_path},
            timestamp=datetime.now(),
            source='mcp'
        )

    def get_schemes(self) -> List[str]:
        """Get supported schemes"""
        return ["mcp"]


# =============================================================================
# DATABASE PROVIDER
# =============================================================================


class DatabaseProvider(ResourceProvider):
    """Provider for database resources (db://table/id)"""

    def __init__(self, repositories: Optional[Dict[str, Any]] = None):
        """
        Initialize database provider.

        Args:
            repositories: Dict mapping table names to repository instances
        """
        self.repositories = repositories or {}

    def can_handle(self, uri: str) -> bool:
        """Check if URI is a database resource"""
        return uri.startswith("db://")

    async def resolve(self, uri: str) -> Resource:
        """Resolve database resource"""
        # Parse URI: db://table/id
        match = re.match(r'db://([^/]+)/(.+)', uri)
        if not match:
            raise ValueError(f"Invalid database URI: {uri}")

        table_name = match.group(1)
        record_id = match.group(2)

        # Get repository for table
        repo = self.repositories.get(table_name)
        if repo is None:
            raise ValueError(f"No repository found for table: {table_name}")

        # Fetch record
        # (Implementation depends on repository interface)
        logger.info(f"Resolving database resource: {uri}")

        # Placeholder implementation
        return Resource(
            uri=uri,
            content=f"Database record from {table_name}: {record_id}",
            content_type='application/json',
            metadata={'table': table_name, 'id': record_id},
            timestamp=datetime.now(),
            source='database'
        )

    def get_schemes(self) -> List[str]:
        """Get supported schemes"""
        return ["db"]


# =============================================================================
# UNIVERSAL RESOLVER
# =============================================================================


class UniversalResourceResolver:
    """
    Universal resource resolver.

    Provides a unified interface for accessing resources
    from multiple sources (files, web, MCP, database, etc.)
    """

    def __init__(self):
        """Initialize resolver with default providers"""
        self.providers: List[ResourceProvider] = []

        # Register default providers
        self.register_provider(FileSystemProvider())
        self.register_provider(WebProvider())
        self.register_provider(MCPProvider())
        self.register_provider(DatabaseProvider())

        logger.info("UniversalResourceResolver initialized")

    def register_provider(self, provider: ResourceProvider):
        """Register a resource provider"""
        self.providers.append(provider)
        schemes = ", ".join(provider.get_schemes())
        logger.info(f"Registered provider for schemes: {schemes}")

    async def resolve(self, uri: str) -> Resource:
        """
        Resolve a URI to a resource.

        Args:
            uri: Resource URI (file://, http://, mcp://, db://, etc.)

        Returns:
            Resource object

        Raises:
            ValueError: If no provider can handle the URI
        """
        # Find provider that can handle this URI
        for provider in self.providers:
            if provider.can_handle(uri):
                logger.info(f"Resolving {uri} with {provider.__class__.__name__}")
                return await provider.resolve(uri)

        # No provider found
        raise ValueError(f"No provider can handle URI: {uri}")

    async def resolve_batch(self, uris: List[str]) -> List[Resource]:
        """
        Resolve multiple URIs in parallel.

        Args:
            uris: List of URIs to resolve

        Returns:
            List of resources (in same order as input URIs)
        """
        import asyncio

        tasks = [self.resolve(uri) for uri in uris]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error resources
        resources = []
        for uri, result in zip(uris, results):
            if isinstance(result, Exception):
                resources.append(Resource(
                    uri=uri,
                    content=f"Error: {result}",
                    content_type='text/plain',
                    metadata={'error': str(result)},
                    source='error'
                ))
            else:
                resources.append(result)

        return resources

    def get_supported_schemes(self) -> List[str]:
        """Get list of all supported URI schemes"""
        schemes = set()
        for provider in self.providers:
            schemes.update(provider.get_schemes())
        return sorted(schemes)
