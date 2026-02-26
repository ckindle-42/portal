"""
Tests for structured logger secret redaction.
"""

from portal.core.structured_logger import _redact_secrets


class TestSecretRedaction:
    """Ensure _redact_secrets catches common secret patterns."""

    def test_slack_bot_token_redacted(self):
        msg = "Using token xoxb-1234-5678-abcdef to post"
        assert "xoxb-" not in _redact_secrets(msg)
        assert "[REDACTED]" in _redact_secrets(msg)

    def test_openai_key_redacted(self):
        msg = "API key is sk-abc123def456"
        assert "sk-abc123def456" not in _redact_secrets(msg)
        assert "[REDACTED]" in _redact_secrets(msg)

    def test_telegram_bot_token_redacted(self):
        msg = "bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        result = _redact_secrets(msg)
        assert "ABC-DEF1234" not in result
        assert "[REDACTED]" in result

    def test_github_pat_redacted(self):
        msg = "token ghp_abc123def456ghi789"
        assert "ghp_abc123def456ghi789" not in _redact_secrets(msg)

    def test_bearer_token_redacted(self):
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
        assert "eyJhbGciOiJIUzI1NiJ9" not in _redact_secrets(msg)

    def test_no_secrets_unchanged(self):
        msg = "Normal log message without secrets"
        assert _redact_secrets(msg) == msg

    def test_empty_string(self):
        assert _redact_secrets("") == ""
