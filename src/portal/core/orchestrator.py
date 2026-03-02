"""
Multi-Step Task Orchestrator
==============================

Decomposes complex user requests into sequential steps and executes them,
passing results forward as context. Implements linear chains; DAG support
is deferred to a future iteration.

Design constraints:
- No external agent frameworks (no LangChain, no CrewAI)
- OpenAI-compatible API contract unchanged
- Each step is either an LLM call or a tool call
- Max steps capped to prevent runaway chains
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

MAX_STEPS = 8  # Hard cap on plan length


class StepType(StrEnum):
    """Type of orchestration step."""

    LLM = "llm"  # LLM call with accumulated context
    TOOL = "tool"  # Tool/MCP call


@dataclass
class TaskStep:
    """A single step in an orchestration plan."""

    step_id: int
    step_type: StepType
    description: str
    tool_name: str | None = None  # for TOOL steps
    tool_args: dict[str, Any] = field(default_factory=dict)
    llm_prompt_template: str | None = None  # for LLM steps; {context} substituted
    result: str | None = None
    error: str | None = None
    completed: bool = False


@dataclass
class TaskPlan:
    """An ordered list of steps to execute for a complex task."""

    goal: str
    steps: list[TaskStep]
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return all(s.completed for s in self.steps)

    @property
    def failed_steps(self) -> list[TaskStep]:
        return [s for s in self.steps if s.error is not None]


class TaskOrchestrator:
    """
    Orchestrates multi-step tasks by decomposing a user goal into sequential steps
    and executing them, passing accumulated results forward as context.

    Usage:
        orchestrator = TaskOrchestrator(execute_llm, execute_tool)
        plan = orchestrator.build_plan("Research X, write a report, create slides")
        result = await orchestrator.execute(plan)
    """

    def __init__(
        self,
        llm_executor: Any | None = None,
        tool_executor: Any | None = None,
    ) -> None:
        """
        Args:
            llm_executor: Callable (prompt: str) -> str for LLM calls
            tool_executor: Callable (name: str, args: dict) -> dict for tool calls
        """
        self._llm_executor = llm_executor
        self._tool_executor = tool_executor

    def build_plan(self, goal: str, steps: list[dict[str, Any]] | None = None) -> TaskPlan:
        """
        Build a TaskPlan from a goal and optional explicit step list.

        If no steps are provided, creates a single LLM step for the goal.
        For more complex decomposition, pass explicit steps or use build_plan_from_llm.

        Args:
            goal: The user's overall objective
            steps: Optional list of step dicts with keys:
                   - type: "llm" | "tool"
                   - description: human-readable step description
                   - tool_name: (tool steps) name of tool to call
                   - tool_args: (tool steps) args dict
                   - llm_prompt_template: (llm steps) prompt with {context} placeholder

        Returns:
            TaskPlan ready for execution
        """
        if not steps:
            return TaskPlan(
                goal=goal,
                steps=[
                    TaskStep(
                        step_id=0,
                        step_type=StepType.LLM,
                        description=goal,
                        llm_prompt_template=goal,
                    )
                ],
            )

        task_steps = []
        for i, step_dict in enumerate(steps[:MAX_STEPS]):
            step_type = StepType(step_dict.get("type", "llm"))
            task_steps.append(
                TaskStep(
                    step_id=i,
                    step_type=step_type,
                    description=step_dict.get("description", f"Step {i}"),
                    tool_name=step_dict.get("tool_name"),
                    tool_args=step_dict.get("tool_args", {}),
                    llm_prompt_template=step_dict.get("llm_prompt_template"),
                )
            )

        return TaskPlan(goal=goal, steps=task_steps)

    async def execute(self, plan: TaskPlan) -> str:
        """
        Execute all steps in a TaskPlan sequentially.

        Results from each step are accumulated into a shared context and
        passed forward to subsequent steps via {context} substitution.

        Args:
            plan: TaskPlan to execute

        Returns:
            Final result string (last step's output, or summary of all steps)
        """
        accumulated_context = f"Goal: {plan.goal}\n\n"

        for step in plan.steps:
            logger.info(
                "Orchestrator step %d/%d: %s [%s]",
                step.step_id + 1,
                len(plan.steps),
                step.description,
                step.step_type,
            )

            try:
                if step.step_type == StepType.TOOL:
                    result = await self._run_tool_step(step)
                else:
                    result = await self._run_llm_step(step, accumulated_context)

                step.result = result
                step.completed = True
                accumulated_context += (
                    f"Step {step.step_id + 1} ({step.description}):\n{result}\n\n"
                )

            except Exception as e:
                step.error = str(e)
                step.completed = True
                logger.warning("Step %d failed: %s", step.step_id, e)
                accumulated_context += (
                    f"Step {step.step_id + 1} ({step.description}) FAILED: {e}\n\n"
                )

        return self._summarize(plan)

    async def _run_llm_step(self, step: TaskStep, context: str) -> str:
        """Execute an LLM step, substituting {context} in the prompt template."""
        if self._llm_executor is None:
            return f"[LLM executor not configured — step: {step.description}]"

        prompt = step.llm_prompt_template or step.description
        if "{context}" in prompt:
            prompt = prompt.format(context=context)
        else:
            # Prepend context if template doesn't reference it
            prompt = f"Context from previous steps:\n{context}\n\nTask: {prompt}"

        return await self._llm_executor(prompt)

    async def _run_tool_step(self, step: TaskStep) -> str:
        """Execute a tool step and return a string summary of the result."""
        if self._tool_executor is None:
            return f"[Tool executor not configured — tool: {step.tool_name}]"
        if not step.tool_name:
            return "[No tool_name specified for tool step]"

        result = await self._tool_executor(step.tool_name, step.tool_args)
        if isinstance(result, dict):
            if result.get("success") is False:
                raise RuntimeError(result.get("error", "Tool call failed"))
            return str(result.get("result", result))
        return str(result)

    def _summarize(self, plan: TaskPlan) -> str:
        """Produce a final summary from all completed steps."""
        if not plan.steps:
            return "No steps to execute."

        # If only one step, return its result directly
        if len(plan.steps) == 1:
            return plan.steps[0].result or plan.steps[0].error or "No result"

        # Multi-step: return last successful result, with a brief summary header
        results = []
        for step in plan.steps:
            status = "✓" if not step.error else "✗"
            results.append(f"{status} Step {step.step_id + 1}: {step.description}")

        last_result = next(
            (s.result for s in reversed(plan.steps) if s.result),
            "No result produced",
        )

        summary_header = "\n".join(results)
        return f"**Orchestration complete** ({len(plan.steps)} steps):\n{summary_header}\n\n---\n\n{last_result}"
