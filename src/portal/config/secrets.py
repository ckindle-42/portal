"""
Secret Provider - Abstract Secret Management
=============================================

Abstracts secret loading to support multiple backends:
- Environment variables (.env)
- Docker secrets (/run/secrets/)
- Generic vaults (AWS Secrets Manager, HashiCorp Vault, etc.)

This is a hallmark of production-ready applications.

Architecture:
    SecretProvider (ABC)
        ├─ EnvSecretProvider (default, reads from environment)
        ├─ DockerSecretProvider (reads from /run/secrets/)
        └─ VaultSecretProvider (future, for cloud vaults)
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class SecretProvider(ABC):
    """
    Abstract base class for secret providers

    Provides a unified interface for accessing secrets from
    different backends.
    """

    @abstractmethod
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value

        Args:
            key: Secret key
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        pass

    @abstractmethod
    def get_required(self, key: str) -> str:
        """
        Get a required secret value

        Args:
            key: Secret key

        Returns:
            Secret value

        Raises:
            ValueError: If secret not found
        """
        pass

    @abstractmethod
    def has_secret(self, key: str) -> bool:
        """
        Check if a secret exists

        Args:
            key: Secret key

        Returns:
            True if secret exists
        """
        pass


class EnvSecretProvider(SecretProvider):
    """
    Environment variable secret provider

    Reads secrets from environment variables (e.g., from .env file).
    This is the default provider.
    """

    def __init__(self, prefix: str = ""):
        """
        Initialize environment secret provider

        Args:
            prefix: Optional prefix for environment variables
                   (e.g., "POCKETPORTAL_" -> reads POCKETPORTAL_API_KEY)
        """
        self.prefix = prefix
        logger.info(f"EnvSecretProvider initialized (prefix: {prefix or 'none'})")

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from environment variable"""
        env_key = f"{self.prefix}{key}" if self.prefix else key
        value = os.getenv(env_key, default)

        if value:
            logger.debug(f"Secret '{key}' loaded from environment")
        else:
            logger.debug(f"Secret '{key}' not found, using default")

        return value

    def get_required(self, key: str) -> str:
        """Get required secret from environment"""
        value = self.get_secret(key)
        if value is None:
            raise ValueError(f"Required secret '{key}' not found in environment")
        return value

    def has_secret(self, key: str) -> bool:
        """Check if environment variable exists"""
        env_key = f"{self.prefix}{key}" if self.prefix else key
        return env_key in os.environ


class DockerSecretProvider(SecretProvider):
    """
    Docker secrets provider

    Reads secrets from /run/secrets/ (Docker Swarm/Compose secrets).

    Example:
        # docker-compose.yml
        secrets:
          api_key:
            file: ./secrets/api_key.txt

        # In container: /run/secrets/api_key
    """

    def __init__(self, secrets_dir: str = "/run/secrets"):
        """
        Initialize Docker secret provider

        Args:
            secrets_dir: Directory containing secret files
        """
        self.secrets_dir = Path(secrets_dir)
        logger.info(f"DockerSecretProvider initialized (dir: {secrets_dir})")

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from Docker secrets file"""
        secret_file = self.secrets_dir / key

        try:
            if secret_file.exists():
                value = secret_file.read_text().strip()
                logger.debug(f"Secret '{key}' loaded from Docker secrets")
                return value
            else:
                logger.debug(f"Secret '{key}' not found in Docker secrets")
                return default

        except Exception as e:
            logger.warning(f"Error reading Docker secret '{key}': {e}")
            return default

    def get_required(self, key: str) -> str:
        """Get required secret from Docker secrets"""
        value = self.get_secret(key)
        if value is None:
            raise ValueError(f"Required secret '{key}' not found in Docker secrets")
        return value

    def has_secret(self, key: str) -> bool:
        """Check if Docker secret file exists"""
        return (self.secrets_dir / key).exists()


class CompositeSecretProvider(SecretProvider):
    """
    Composite secret provider that tries multiple providers

    Tries providers in order until a secret is found.

    Example:
        provider = CompositeSecretProvider([
            DockerSecretProvider(),  # Try Docker secrets first
            EnvSecretProvider()      # Fall back to environment
        ])
    """

    def __init__(self, providers: list[SecretProvider]):
        """
        Initialize composite provider

        Args:
            providers: List of providers to try in order
        """
        self.providers = providers
        logger.info(f"CompositeSecretProvider initialized with {len(providers)} providers")

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from first provider that has it"""
        for provider in self.providers:
            if provider.has_secret(key):
                return provider.get_secret(key)

        logger.debug(f"Secret '{key}' not found in any provider, using default")
        return default

    def get_required(self, key: str) -> str:
        """Get required secret from providers"""
        value = self.get_secret(key)
        if value is None:
            raise ValueError(f"Required secret '{key}' not found in any provider")
        return value

    def has_secret(self, key: str) -> bool:
        """Check if any provider has the secret"""
        return any(provider.has_secret(key) for provider in self.providers)


# Factory function
def create_secret_provider(
    backend: str = "env",
    **kwargs
) -> SecretProvider:
    """
    Create a secret provider

    Args:
        backend: Backend type ("env", "docker", "composite")
        **kwargs: Backend-specific configuration

    Returns:
        SecretProvider instance

    Example:
        # Environment variables
        provider = create_secret_provider("env")

        # Docker secrets
        provider = create_secret_provider("docker")

        # Composite (try Docker, then env)
        provider = create_secret_provider("composite", backends=["docker", "env"])
    """
    if backend == "env":
        prefix = kwargs.get("prefix", "")
        return EnvSecretProvider(prefix=prefix)

    elif backend == "docker":
        secrets_dir = kwargs.get("secrets_dir", "/run/secrets")
        return DockerSecretProvider(secrets_dir=secrets_dir)

    elif backend == "composite":
        backends = kwargs.get("backends", ["docker", "env"])
        providers = [create_secret_provider(b) for b in backends]
        return CompositeSecretProvider(providers)

    else:
        raise ValueError(f"Unknown secret provider backend: {backend}")


# Global instance for convenience
_global_provider: Optional[SecretProvider] = None


def get_secret_provider() -> SecretProvider:
    """Get global secret provider instance"""
    global _global_provider
    if _global_provider is None:
        # Default to environment provider
        _global_provider = EnvSecretProvider()
    return _global_provider


def set_secret_provider(provider: SecretProvider):
    """Set global secret provider instance"""
    global _global_provider
    _global_provider = provider
