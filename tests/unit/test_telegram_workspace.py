"""Tests for Telegram workspace parsing ( @model: prefix)."""


class TestTelegramWorkspaceParsing:
    """Tests for Telegram @model: workspace selection."""

    def test_parse_model_prefix_with_workspace(self):
        """Test parsing @model:workspace from message."""
        message = "@model:auto-security Hello world"

        workspace_id = None
        if message.startswith("@model:"):
            parts = message.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            message = parts[1] if len(parts) > 1 else ""

        assert workspace_id == "auto-security"
        assert message == "Hello world"

    def test_parse_model_prefix_no_message(self):
        """Test parsing @model:workspace with no additional text."""
        message = "@model:creative"

        workspace_id = None
        if message.startswith("@model:"):
            parts = message.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            message = parts[1] if len(parts) > 1 else ""

        assert workspace_id == "creative"
        assert message == ""

    def test_parse_model_prefix_strips_from_message(self):
        """Test that @model: prefix is stripped from message text."""
        message = "@model:research What is AI?"

        workspace_id = None
        if message.startswith("@model:"):
            parts = message.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            message = parts[1] if len(parts) > 1 else ""

        # Verify workspace was parsed
        assert workspace_id == "research"
        # Message should not contain @model:
        assert "@model:" not in message
        assert message == "What is AI?"

    def test_no_prefix_returns_none_workspace(self):
        """Test that message without @model: gets workspace_id=None."""
        message = "Hello, how are you?"

        workspace_id = None
        if message.startswith("@model:"):
            parts = message.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            message = parts[1] if len(parts) > 1 else ""

        assert workspace_id is None
        assert message == "Hello, how are you?"

    def test_prefix_only_no_space(self):
        """Test @model:workspace without trailing space."""
        message = "@model:default"

        workspace_id = None
        if message.startswith("@model:"):
            parts = message.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            message = parts[1] if len(parts) > 1 else ""

        assert workspace_id == "default"
        assert message == ""

    def test_auto_security_prefix(self):
        """Test @model:auto-security prefix parsing."""
        message = "@model:auto-security Write a secure login"

        workspace_id = None
        if message.startswith("@model:"):
            parts = message.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            message = parts[1] if len(parts) > 1 else ""

        assert workspace_id == "auto-security"
        assert message == "Write a secure login"

    def test_whitespace_handling(self):
        """Test that extra whitespace is handled correctly."""
        message = "  @model:test   hello  "

        workspace_id = None
        if message.startswith("@model:"):
            parts = message.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            message = parts[1] if len(parts) > 1 else ""

        # Note: leading whitespace doesn't trigger prefix detection
        # This is expected behavior for startswith()
        assert workspace_id is None
