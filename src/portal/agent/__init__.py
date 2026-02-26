"""portal.agent — interface registry and dispatcher."""

from portal.agent.dispatcher import CentralDispatcher, UnknownInterfaceError

__all__ = ["CentralDispatcher", "UnknownInterfaceError"]
