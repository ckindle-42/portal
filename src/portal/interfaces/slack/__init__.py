from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from portal.interfaces.slack.interface import SlackInterface

try:
    from portal.interfaces.slack.interface import SlackInterface

    SLACK_AVAILABLE = True
except ImportError:
    SlackInterface = None  # type: ignore[misc,assignment]
    SLACK_AVAILABLE = False

__all__ = ["SlackInterface", "SLACK_AVAILABLE"]
