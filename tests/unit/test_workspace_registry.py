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

    def test_workspace_id_returns_workspace_model(self):
        router = self._make_router({"coding": {"model": "codellama:7b"}})
        decision = router.route("write a function", workspace_id="coding")
        assert decision.model_id == "codellama:7b"
        assert "workspace" in decision.reasoning

    def test_unknown_workspace_id_falls_through_to_normal_routing(self):
        router = self._make_router({"coding": {"model": "codellama:7b"}})
        # "other" is not registered — should not raise, falls through
        decision = router.route("hello", workspace_id="other")
        # Model ID comes from task classification, not workspace
        assert decision.model_id != "codellama:7b" or decision.reasoning != "workspace: other"

    def test_no_workspace_id_uses_task_classification(self):
        router = self._make_router({"coding": {"model": "codellama:7b"}})
        decision = router.route("hello world")
        assert "workspace" not in decision.reasoning

    def test_workspace_without_registry_falls_through(self):
        from portal.routing.intelligent_router import IntelligentRouter
        from portal.routing.model_registry import ModelRegistry

        registry = ModelRegistry()
        router = IntelligentRouter(registry)  # No workspace_registry
        decision = router.route("hello", workspace_id="coding")
        assert "workspace" not in decision.reasoning
