"""Integration tests for AgentCore orchestrator wiring"""
import pytest

from portal.core.agent_core import AgentCore


class TestAgentCoreOrchestrator:
    """Tests for orchestrator integration in AgentCore"""

    @pytest.fixture
    def agent_core(self):
        """Create AgentCore instance with minimal deps for testing"""
        from portal.core.context_manager import ContextManager
        from portal.core.event_bus import EventBus
        from portal.core.prompt_manager import PromptManager
        from portal.routing import ExecutionEngine, IntelligentRouter, ModelRegistry
        from portal.tools import ToolRegistry

        registry = ModelRegistry()
        router = IntelligentRouter(registry)
        engine = ExecutionEngine(registry, router)
        ctx_mgr = ContextManager()
        event_bus = EventBus()
        prompt_mgr = PromptManager()
        tool_registry = ToolRegistry()

        return AgentCore(
            model_registry=registry,
            router=router,
            execution_engine=engine,
            context_manager=ctx_mgr,
            event_bus=event_bus,
            prompt_manager=prompt_mgr,
            tool_registry=tool_registry,
            config={},
        )

    # Test _is_multi_step detection
    def test_is_multi_step_hello(self, agent_core):
        """Basic greeting should NOT trigger orchestrator"""
        assert agent_core._is_multi_step("hello") is False

    def test_is_multi_step_write_function(self, agent_core):
        """Simple write request should NOT trigger"""
        assert agent_core._is_multi_step("write a Python sort function") is False

    def test_is_multi_step_first_let_me_explain(self, agent_core):
        """Casual 'first' usage should NOT trigger"""
        assert agent_core._is_multi_step("first, let me explain") is False

    def test_is_multi_step_step_1_step_2(self, agent_core):
        """Explicit 'Step 1: X. Step 2: Y' SHOULD trigger"""
        assert (
            agent_core._is_multi_step("Step 1: research. Step 2: write report") is True
        )

    def test_is_multi_step_do_both(self, agent_core):
        """Explicit 'do both' should trigger"""
        assert agent_core._is_multi_step("Do both: write the code and create docs") is True

    # Test that orchestrator is initialized
    def test_orchestrator_initialized(self, agent_core):
        """AgentCore should have orchestrator attribute"""
        assert hasattr(agent_core, "_orchestrator")
        assert agent_core._orchestrator is not None
