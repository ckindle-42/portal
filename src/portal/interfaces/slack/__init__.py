try:
    from portal.interfaces.slack.interface import SlackInterface

    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False
    SlackInterface = None

__all__ = ["SlackInterface", "SLACK_AVAILABLE"]
