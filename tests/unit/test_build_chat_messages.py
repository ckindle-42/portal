"""
Tests for BaseHTTPBackend._build_chat_messages shared helper.
"""

from portal.routing.model_backends import BaseHTTPBackend


class TestBuildChatMessages:
    """Test the shared _build_chat_messages static method."""

    def test_prompt_only(self):
        """With just a prompt, returns a single user message."""
        result = BaseHTTPBackend._build_chat_messages("hello", None, None)
        assert result == [{"role": "user", "content": "hello"}]

    def test_prompt_with_system(self):
        """With prompt + system prompt, returns system + user."""
        result = BaseHTTPBackend._build_chat_messages("hello", "You are helpful.", None)
        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "You are helpful."}
        assert result[1] == {"role": "user", "content": "hello"}

    def test_messages_passthrough(self):
        """When messages are provided, they are returned (without mutation)."""
        msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        result = BaseHTTPBackend._build_chat_messages("ignored", None, msgs)
        assert result == msgs
        # Verify original list is not mutated
        assert len(msgs) == 2

    def test_messages_with_system_prepended(self):
        """System prompt is prepended when messages don't start with one."""
        msgs = [{"role": "user", "content": "hi"}]
        result = BaseHTTPBackend._build_chat_messages("ignored", "Be brief.", msgs)
        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "Be brief."}
        assert result[1] == {"role": "user", "content": "hi"}

    def test_messages_with_existing_system_not_duplicated(self):
        """When messages already start with system, no duplicate is added."""
        msgs = [
            {"role": "system", "content": "existing"},
            {"role": "user", "content": "hi"},
        ]
        result = BaseHTTPBackend._build_chat_messages("ignored", "new system", msgs)
        assert result[0]["content"] == "existing"
        assert len(result) == 2

    def test_empty_messages_list(self):
        """Empty messages list with system prompt prepends system."""
        result = BaseHTTPBackend._build_chat_messages("ignored", "sys", [])
        assert result == [{"role": "system", "content": "sys"}]
