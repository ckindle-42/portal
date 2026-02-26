"""PromptManager tests — template loading, caching, and composition."""

from pathlib import Path

import pytest

from portal.core.prompt_manager import _DEFAULT_SYSTEM_PROMPT, PromptManager


@pytest.fixture()
def prompts_dir(tmp_path: Path) -> Path:
    d = tmp_path / "prompts"
    d.mkdir()
    return d


@pytest.fixture()
def pm(prompts_dir: Path) -> PromptManager:
    return PromptManager(prompts_dir=prompts_dir)


class TestTemplateLoading:
    def test_load_existing_template(self, pm: PromptManager, prompts_dir: Path) -> None:
        (prompts_dir / "base_system.md").write_text("You are Portal.")
        content = pm.load_template("base_system")
        assert content == "You are Portal."

    def test_load_missing_template_returns_empty(self, pm: PromptManager) -> None:
        content = pm.load_template("nonexistent")
        assert content == ""

    def test_cache_hit(self, pm: PromptManager, prompts_dir: Path) -> None:
        (prompts_dir / "cached.md").write_text("cached content")
        pm.load_template("cached")
        # Modify the file - cached version should be returned
        (prompts_dir / "cached.md").write_text("updated content")
        content = pm.load_template("cached", use_cache=True)
        assert content == "cached content"

    def test_cache_bypass(self, pm: PromptManager, prompts_dir: Path) -> None:
        (prompts_dir / "cached.md").write_text("original")
        pm.load_template("cached")
        (prompts_dir / "cached.md").write_text("updated")
        content = pm.load_template("cached", use_cache=False)
        assert content == "updated"


class TestBuildSystemPrompt:
    def test_fallback_to_default_prompt(self, pm: PromptManager) -> None:
        """When no base_system.md exists, uses built-in default."""
        prompt = pm.build_system_prompt()
        assert prompt == _DEFAULT_SYSTEM_PROMPT

    def test_uses_base_template(self, pm: PromptManager, prompts_dir: Path) -> None:
        (prompts_dir / "base_system.md").write_text("Base prompt.")
        prompt = pm.build_system_prompt()
        assert prompt.startswith("Base prompt.")

    def test_appends_interface_template(self, pm: PromptManager, prompts_dir: Path) -> None:
        (prompts_dir / "base_system.md").write_text("Base.")
        (prompts_dir / "web_interface.md").write_text("Web-specific.")
        prompt = pm.build_system_prompt(interface="web")
        assert "Base." in prompt
        assert "Web-specific." in prompt

    def test_verbose_preference(self, pm: PromptManager, prompts_dir: Path) -> None:
        (prompts_dir / "base_system.md").write_text("Base.")
        prefs_dir = prompts_dir / "preferences"
        prefs_dir.mkdir()
        (prefs_dir / "verbose.md").write_text("Be verbose.")
        prompt = pm.build_system_prompt(user_preferences={"verbose": True})
        assert "Be verbose." in prompt

    def test_custom_context_appended(self, pm: PromptManager, prompts_dir: Path) -> None:
        (prompts_dir / "base_system.md").write_text("Base.")
        prompt = pm.build_system_prompt(user_preferences={"custom_context": "Extra context."})
        assert "Extra context." in prompt
