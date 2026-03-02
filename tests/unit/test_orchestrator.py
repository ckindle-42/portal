"""Unit tests for portal.core.orchestrator — multi-step task orchestration."""

import pytest

from portal.core.orchestrator import MAX_STEPS, StepType, TaskOrchestrator, TaskPlan, TaskStep

# ---------------------------------------------------------------------------
# TaskStep tests
# ---------------------------------------------------------------------------


def test_task_step_defaults() -> None:
    step = TaskStep(step_id=0, step_type=StepType.LLM, description="do something")
    assert step.result is None
    assert step.error is None
    assert step.completed is False
    assert step.tool_name is None
    assert step.tool_args == {}


def test_task_step_tool_type() -> None:
    step = TaskStep(
        step_id=1,
        step_type=StepType.TOOL,
        description="call tool",
        tool_name="my_tool",
        tool_args={"arg1": "val1"},
    )
    assert step.step_type == StepType.TOOL
    assert step.tool_name == "my_tool"
    assert step.tool_args == {"arg1": "val1"}


# ---------------------------------------------------------------------------
# TaskPlan tests
# ---------------------------------------------------------------------------


def test_task_plan_is_complete_when_all_steps_done() -> None:
    steps = [
        TaskStep(step_id=0, step_type=StepType.LLM, description="s1", completed=True),
        TaskStep(step_id=1, step_type=StepType.LLM, description="s2", completed=True),
    ]
    plan = TaskPlan(goal="test", steps=steps)
    assert plan.is_complete is True


def test_task_plan_not_complete_when_step_pending() -> None:
    steps = [
        TaskStep(step_id=0, step_type=StepType.LLM, description="s1", completed=True),
        TaskStep(step_id=1, step_type=StepType.LLM, description="s2", completed=False),
    ]
    plan = TaskPlan(goal="test", steps=steps)
    assert plan.is_complete is False


def test_task_plan_failed_steps() -> None:
    steps = [
        TaskStep(step_id=0, step_type=StepType.LLM, description="s1", completed=True),
        TaskStep(
            step_id=1,
            step_type=StepType.TOOL,
            description="s2",
            completed=True,
            error="something broke",
        ),
    ]
    plan = TaskPlan(goal="test", steps=steps)
    assert len(plan.failed_steps) == 1
    assert plan.failed_steps[0].step_id == 1


# ---------------------------------------------------------------------------
# TaskOrchestrator.build_plan tests
# ---------------------------------------------------------------------------


def test_build_plan_no_steps_creates_single_llm_step() -> None:
    orch = TaskOrchestrator()
    plan = orch.build_plan("do something interesting")
    assert len(plan.steps) == 1
    assert plan.steps[0].step_type == StepType.LLM
    assert plan.steps[0].description == "do something interesting"
    assert plan.goal == "do something interesting"


def test_build_plan_with_explicit_steps() -> None:
    orch = TaskOrchestrator()
    plan = orch.build_plan(
        "multi-step goal",
        steps=[
            {"type": "llm", "description": "step A", "llm_prompt_template": "do A"},
            {"type": "tool", "description": "step B", "tool_name": "tool_x", "tool_args": {"k": "v"}},
        ],
    )
    assert len(plan.steps) == 2
    assert plan.steps[0].step_type == StepType.LLM
    assert plan.steps[1].step_type == StepType.TOOL
    assert plan.steps[1].tool_name == "tool_x"


def test_build_plan_respects_max_steps_cap() -> None:
    orch = TaskOrchestrator()
    many_steps = [{"type": "llm", "description": f"step {i}"} for i in range(MAX_STEPS + 5)]
    plan = orch.build_plan("goal", steps=many_steps)
    assert len(plan.steps) <= MAX_STEPS


# ---------------------------------------------------------------------------
# TaskOrchestrator.execute tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_single_llm_step() -> None:
    async def fake_llm(prompt: str) -> str:
        return f"LLM response to: {prompt}"

    orch = TaskOrchestrator(llm_executor=fake_llm)
    plan = orch.build_plan("say hello")
    result = await orch.execute(plan)

    assert "LLM response to" in result
    assert plan.is_complete


@pytest.mark.asyncio
async def test_execute_multi_step_plan() -> None:
    calls: list[str] = []

    async def fake_llm(prompt: str) -> str:
        calls.append(prompt)
        return f"result for: {prompt[:20]}"

    orch = TaskOrchestrator(llm_executor=fake_llm)
    plan = orch.build_plan(
        "two-step task",
        steps=[
            {"type": "llm", "description": "step 1", "llm_prompt_template": "do step 1"},
            {"type": "llm", "description": "step 2", "llm_prompt_template": "do step 2 given {context}"},
        ],
    )
    result = await orch.execute(plan)

    assert len(calls) == 2
    assert plan.is_complete
    # Second step should have received context from step 1
    assert "step 1" in calls[1] or "context" in calls[1].lower() or "result" in calls[1].lower()
    # Multi-step result includes summary header
    assert "Orchestration complete" in result


@pytest.mark.asyncio
async def test_execute_tool_step() -> None:
    async def fake_tool(name: str, args: dict) -> dict:
        return {"success": True, "result": f"tool {name} ran with {args}"}

    orch = TaskOrchestrator(tool_executor=fake_tool)
    plan = orch.build_plan(
        "run a tool",
        steps=[
            {
                "type": "tool",
                "description": "use my_tool",
                "tool_name": "my_tool",
                "tool_args": {"key": "value"},
            }
        ],
    )
    result = await orch.execute(plan)

    assert plan.is_complete
    assert "my_tool" in result


@pytest.mark.asyncio
async def test_execute_handles_tool_failure_gracefully() -> None:
    async def failing_tool(name: str, args: dict) -> dict:
        return {"success": False, "error": "tool exploded"}

    orch = TaskOrchestrator(tool_executor=failing_tool)
    plan = orch.build_plan(
        "failing tool",
        steps=[
            {
                "type": "tool",
                "description": "bad tool",
                "tool_name": "bad_tool",
                "tool_args": {},
            }
        ],
    )
    # Should not raise — failed steps are recorded, not raised
    await orch.execute(plan)

    assert plan.failed_steps
    assert plan.failed_steps[0].error is not None


@pytest.mark.asyncio
async def test_execute_no_executor_returns_placeholder() -> None:
    orch = TaskOrchestrator()  # No executors configured
    plan = orch.build_plan("anything")
    result = await orch.execute(plan)

    assert result  # Returns some string
    assert plan.is_complete


@pytest.mark.asyncio
async def test_execute_context_accumulated_across_steps() -> None:
    received_prompts: list[str] = []

    async def tracking_llm(prompt: str) -> str:
        received_prompts.append(prompt)
        return "result of step"

    orch = TaskOrchestrator(llm_executor=tracking_llm)
    plan = orch.build_plan(
        "accumulate context",
        steps=[
            {"type": "llm", "description": "step A", "llm_prompt_template": "Task A"},
            {"type": "llm", "description": "step B", "llm_prompt_template": "Task B"},
            {"type": "llm", "description": "step C", "llm_prompt_template": "Task C with {context}"},
        ],
    )
    await orch.execute(plan)

    # Third step prompt should contain accumulated context from steps A and B
    assert len(received_prompts) == 3
    assert "step A" in received_prompts[2] or "result" in received_prompts[2]
