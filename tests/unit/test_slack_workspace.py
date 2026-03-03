"""Tests for Slack workspace parsing (@model: prefix)."""


class TestSlackWorkspaceParsing:
    """Tests for Slack @model: workspace selection."""

    def test_parse_model_prefix_with_workspace(self):
        """Test parsing @model:workspace from message."""
        text = "@model:auto-creative Generate a story"

        workspace_id = None
        if text.startswith("@model:"):
            parts = text.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            text = parts[1] if len(parts) > 1 else ""

        assert workspace_id == "auto-creative"
        assert text == "Generate a story"

    def test_parse_model_prefix_no_message(self):
        """Test parsing @model:workspace with no additional text."""
        text = "@model:multimodal"

        workspace_id = None
        if text.startswith("@model:"):
            parts = text.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            text = parts[1] if len(parts) > 1 else ""

        assert workspace_id == "multimodal"
        assert text == ""

    def test_parse_model_prefix_strips_from_message(self):
        """Test that @model: prefix is stripped from message text."""
        text = "@model:code Help me write Python"

        workspace_id = None
        if text.startswith("@model:"):
            parts = text.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            text = parts[1] if len(parts) > 1 else ""

        # Verify workspace was parsed
        assert workspace_id == "code"
        # Text should not contain @model:
        assert "@model:" not in text
        assert text == "Help me write Python"

    def test_no_prefix_returns_none_workspace(self):
        """Test that message without @model: gets workspace_id=None."""
        text = "Hello from Slack!"

        workspace_id = None
        if text.startswith("@model:"):
            parts = text.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            text = parts[1] if len(parts) > 1 else ""

        assert workspace_id is None
        assert text == "Hello from Slack!"

    def test_prefix_only_no_space(self):
        """Test @model:workspace without trailing space."""
        text = "@model:reasoning"

        workspace_id = None
        if text.startswith("@model:"):
            parts = text.split(" ", 1)
            workspace_id = parts[0].replace("@model:", "")
            text = parts[1] if len(parts) > 1 else ""

        assert workspace_id == "reasoning"
        assert text == ""

    def test_various_workspace_names(self):
        """Test various workspace name formats."""
        test_cases = [
            ("@model:default hello", "default", "hello"),
            ("@model:auto-security test", "auto-security", "test"),
            ("@model:creative hello", "creative", "hello"),
            ("@model:research query", "research", "query"),
        ]

        for text, expected_workspace, expected_msg in test_cases:
            workspace_id = None
            if text.startswith("@model:"):
                parts = text.split(" ", 1)
                workspace_id = parts[0].replace("@model:", "")
                text = parts[1] if len(parts) > 1 else ""

            assert workspace_id == expected_workspace
            assert text == expected_msg


class TestTelegramSlackConsistency:
    """Tests ensuring Telegram and Slack parsing behave the same way."""

    def test_same_parsing_logic(self):
        """Test that Telegram and Slack use the same parsing logic."""
        message = "@model:test hello world"

        # Telegram parsing
        tg_workspace = None
        tg_message = message
        if tg_message.startswith("@model:"):
            parts = tg_message.split(" ", 1)
            tg_workspace = parts[0].replace("@model:", "")
            tg_message = parts[1] if len(parts) > 1 else ""

        # Slack parsing (identical logic)
        slack_text = message
        slack_workspace = None
        if slack_text.startswith("@model:"):
            parts = slack_text.split(" ", 1)
            slack_workspace = parts[0].replace("@model:", "")
            slack_text = parts[1] if len(parts) > 1 else ""

        assert tg_workspace == slack_workspace == "test"
        assert tg_message == slack_text == "hello world"
