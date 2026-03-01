"""BackendRegistry — registry for ModelBackend instances."""

from .model_backends import ModelBackend


class BackendRegistry:
    """Registry mapping backend names to ModelBackend instances.

    Allows ExecutionEngine to accept pre-built backends at construction
    time rather than hard-coding OllamaBackend in __init__.
    """

    def __init__(self) -> None:
        self._backends: dict[str, ModelBackend] = {}

    def register(self, name: str, backend: ModelBackend) -> None:
        """Register a backend under *name*."""
        self._backends[name] = backend

    def get(self, name: str) -> ModelBackend:
        """Return the backend registered as *name*.

        Raises:
            KeyError: If no backend with that name is registered.
        """
        if name not in self._backends:
            raise KeyError(f"Backend '{name}' not registered")
        return self._backends[name]

    def available(self) -> list[str]:
        """Return names of all registered backends."""
        return list(self._backends.keys())
