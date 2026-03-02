"""Tests for multi-step detection in AgentCore"""
import pytest

from portal.core.agent_core import AgentCore


class TestMultiStepDetection:
    """Tests for _is_multi_step() conservative detection"""

    @pytest.fixture
    def agent_core(self):
        """Create AgentCore instance with minimal deps for testing"""
        from portal.routing import ExecutionEngine, IntelligentRouter, ModelRegistry
        from portal.core.context_manager import ContextManager
        from portal.core.event_bus import EventBus
        from portal.core.prompt_manager import PromptManager
        from portal.tools import ToolRegistry

        # Minimal setup - we just need the agent_core instance to test _is_multi_step
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

    # SHOULD NOT trigger orchestrator (single-turn prompts)
    def test_single_turn_write_function(self, agent_core):
        """'Write a Python function' - single turn, should NOT trigger"""
        assert agent_core._is_multi_step("Write a Python function that generates CSV files") is False

    def test_single_turn_first_explain(self, agent_core):
        """'First, let me explain' - casual use of 'first', should NOT trigger"""
        assert agent_core._is_multi_step("First, let me explain quantum computing") is False

    def test_single_turn_find_and_summarize(self, agent_core):
        """'Find and summarize' - single thought, should NOT trigger"""
        assert agent_core._is_multi_step("Find and summarize the key points") is False

    def test_single_turn_hello(self, agent_core):
        """'hello' - basic greeting"""
        assert agent_core._is_multi_step("hello") is False

    def test_single_turn_create_image(self, agent_core):
        """'create an image' - simple action"""
        assert agent_core._is_multi_step("Create an image of a sunset") is False

    def test_single_turn_research_topic(self, agent_core):
        """'research X' - single action"""
        assert agent_core._is_multi_step("Research quantum computing") is False

    def test_single_turn_write_code_and_debug(self, agent_core):
        """'write and debug' - compound but still single intent"""
        assert agent_core._is_multi_step("Write and debug a sorting function") is False

    def test_single_turn_explain_step_by_step(self, agent_core):
        """'explain step by step' - does NOT mean multi-step"""
        assert agent_core._is_multi_step("Explain quantum computing step by step") is False

    def test_single_turn_second_thought(self, agent_core):
        """'second thought' - casual, not step numbering"""
        assert agent_core._is_multi_step("My second thought is that this is complex") is False

    def test_single_turn_finally_done(self, agent_core):
        """'finally' - casual word use"""
        assert agent_core._is_multi_step("I'm finally done with this task") is False

    # SHOULD trigger orchestrator (explicitly structured multi-step)
    def test_multi_step_step_1_step_2(self, agent_core):
        """'Step 1: X. Step 2: Y' - explicit numbered steps"""
        assert (
            agent_core._is_multi_step(
                "Step 1: research quantum computing. Step 2: create a presentation about it"
            )
            is True
        )

    def test_multi_step_first_then_finally(self, agent_core):
        """'first X, then Y, then Z' - explicit sequence"""
        assert (
            agent_core._is_multi_step(
                "First research X, then write a report, then create slides"
            )
            is True
        )

    def test_multi_step_do_both(self, agent_core):
        """'do both X and Y' - explicitly multi"""
        assert (
            agent_core._is_multi_step("Do both: write the code and create the documentation")
            is True
        )

    def test_multi_step_numbered_list(self, agent_core):
        """'1) X 2) Y' - numbered list format"""
        assert agent_core._is_multi_step("1) Research the topic 2) Write a summary") is True

    def test_multi_step_step_1_only(self, agent_core):
        """'step 1' alone without step 2 - should NOT trigger"""
        assert agent_core._is_multi_step("Step 1: research this topic") is False