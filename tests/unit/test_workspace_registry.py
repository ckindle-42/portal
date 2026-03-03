"""Unit tests for WorkspaceRegistry and IntelligentRouter workspace routing (TASK-18)."""

from portal.routing.workspace_registry import WorkspaceRegistry


class TestWorkspaceRegistry:
    def test_get_model_known_workspace(self):
        registry = WorkspaceRegistry({"coding": {"model": "qwen2.5-coder:7b"}})
        assert registry.get_model("coding") == "qwen2.5-coder:7b"

    def test_get_model_unknown_workspace_returns_none(self):
        registry = WorkspaceRegistry({})
        assert registry.get_model("unknown") is None

    def test_list_workspaces(self):
        registry = WorkspaceRegistry({"ws1": {"model": "m1"}, "ws2": {"model": "m2"}})
        assert set(registry.list_workspaces()) == {"ws1", "ws2"}

    def test_empty_registry(self):
        registry = WorkspaceRegistry({})
        assert registry.list_workspaces() == []


class TestIntelligentRouterWorkspace:
    """IntelligentRouter.route() with workspace_id consults WorkspaceRegistry."""

    def _make_router(self, workspaces: dict):
        from portal.routing.intelligent_router import IntelligentRouter
        from portal.routing.model_registry import ModelRegistry

        registry = ModelRegistry()
        ws_registry = WorkspaceRegistry(workspaces)
        return IntelligentRouter(registry, workspace_registry=ws_registry)

    async def test_workspace_id_returns_workspace_model(self):
        router = self._make_router({"coding": {"model": "codellama:7b"}})
        decision = await router.route("write a function", workspace_id="coding")
        assert decision.model_id == "codellama:7b"
        assert "workspace" in decision.reasoning

    async def test_unknown_workspace_id_falls_through_to_normal_routing(self):
        router = self._make_router({"coding": {"model": "codellama:7b"}})
        # "other" is not registered — should not raise, falls through
        decision = await router.route("hello", workspace_id="other")
        # Model ID comes from task classification, not workspace
        assert decision.model_id != "codellama:7b" or decision.reasoning != "workspace: other"

    async def test_no_workspace_id_uses_task_classification(self):
        router = self._make_router({"coding": {"model": "codellama:7b"}})
        decision = await router.route("hello world")
        assert "workspace" not in decision.reasoning

    async def test_workspace_without_registry_falls_through(self):
        from portal.routing.intelligent_router import IntelligentRouter
        from portal.routing.model_registry import ModelRegistry

        registry = ModelRegistry()
        router = IntelligentRouter(registry)  # No workspace_registry
        decision = await router.route("hello", workspace_id="coding")
        assert "workspace" not in decision.reasoning


class TestWorkspacePersonaSelection:
    """Tests for workspace-based persona selection."""

    def test_workspace_with_system_prompt(self):
        """Test that workspace can have a system prompt for persona routing."""
        registry = WorkspaceRegistry({
            "code-reviewer": {
                "model": "qwen2.5:7b",
                "system_prompt": "You are a code reviewer. Review code for bugs and improvements."
            }
        })
        prompt = registry.get_system_prompt("code-reviewer")
        assert prompt is not None
        assert "code reviewer" in prompt.lower()

    def test_workspace_without_system_prompt(self):
        """Test that workspace without system prompt returns None."""
        registry = WorkspaceRegistry({
            "simple": {"model": "qwen2.5:7b"}
        })
        prompt = registry.get_system_prompt("simple")
        assert prompt is None

    def test_workspace_with_acl_tools(self):
        """Test workspace ACL tool restrictions."""
        registry = WorkspaceRegistry({
            "restricted": {
                "model": "qwen2.5:7b",
                "acl": {
                    "allowed_tools": ["git", "filesystem_read"]
                }
            }
        })
        acl = registry.get_acl("restricted")
        assert acl is not None
        assert acl.allowed_tools == ["git", "filesystem_read"]
        assert registry.is_tool_allowed("restricted", "git") is True
        assert registry.is_tool_allowed("restricted", "bash") is False

    def test_workspace_with_acl_users(self):
        """Test workspace ACL user restrictions."""
        registry = WorkspaceRegistry({
            "private": {
                "model": "qwen2.5:7b",
                "acl": {
                    "allowed_users": ["user1", "user2"]
                }
            }
        })
        assert registry.is_user_allowed("private", "user1") is True
        assert registry.is_user_allowed("private", "user3") is False

    def test_workspace_with_blocked_users(self):
        """Test workspace ACL blocked users."""
        registry = WorkspaceRegistry({
            "public": {
                "model": "qwen2.5:7b",
                "acl": {
                    "blocked_users": ["bad_user"]
                }
            }
        })
        assert registry.is_user_allowed("public", "good_user") is True
        assert registry.is_user_allowed("public", "bad_user") is False

    def test_workspace_rate_limit(self):
        """Test workspace-specific rate limiting."""
        registry = WorkspaceRegistry({
            "high-traffic": {
                "model": "qwen2.5:7b",
                "acl": {"rate_limit": 100}
            }
        })
        rate_limit = registry.get_rate_limit("high-traffic")
        assert rate_limit == 100

    def test_workspace_max_tokens(self):
        """Test workspace-specific max tokens."""
        registry = WorkspaceRegistry({
            "long-output": {
                "model": "qwen2.5:7b",
                "acl": {"max_tokens": 8000}
            }
        })
        max_tokens = registry.get_max_tokens("long-output")
        assert max_tokens == 8000
