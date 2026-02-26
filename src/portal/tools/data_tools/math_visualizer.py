"""Math Visualizer Tool - Plot equations and functions"""

import ast
import operator
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter

_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg,
}


def _safe_eval(expr: str, x: "np.ndarray") -> "np.ndarray":  # type: ignore[name-defined]  # noqa: F821
    """Evaluate a math expression safely via AST walking."""
    import numpy as np

    _SAFE_FUNCS = {
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "log": np.log, "exp": np.exp, "sqrt": np.sqrt, "abs": np.abs,
    }
    _SAFE_CONSTS = {"pi": np.pi, "e": np.e}

    tree = ast.parse(expr, mode="eval")

    def _eval_node(node: ast.expr) -> Any:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id == "x":
                return x
            if node.id in _SAFE_CONSTS:
                return _SAFE_CONSTS[node.id]
            raise ValueError(f"Unknown variable: {node.id}")
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](_eval_node(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _SAFE_FUNCS and len(node.args) == 1:
                return _SAFE_FUNCS[node.func.id](_eval_node(node.args[0]))
            raise ValueError(f"Unknown function: {node.func.id}")
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    return _eval_node(tree)


class MathVisualizerTool(BaseTool):
    """Visualize mathematical functions and equations"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="math_visualizer",
            description="Plot mathematical functions and create visualizations",
            category=ToolCategory.DATA,
            version="1.0.0",
            requires_confirmation=False,
            parameters=[
                ToolParameter(
                    name="expression",
                    param_type="string",
                    description="Math expression (use x as variable, e.g., 'x**2 + 2*x')",
                    required=True
                ),
                ToolParameter(
                    name="x_range",
                    param_type="list",
                    description="X-axis range [min, max]",
                    required=False,
                    default=[-10, 10]
                ),
                ToolParameter(
                    name="title",
                    param_type="string",
                    description="Plot title",
                    required=False,
                    default="Function Plot"
                )
            ],
            examples=["Plot x**2 from -5 to 5"]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Create math visualization"""
        try:
            import matplotlib
            import numpy as np
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt

            expression = parameters.get("expression", "x")
            x_range = parameters.get("x_range", [-10, 10])
            title = parameters.get("title", "Function Plot")

            # Generate x values
            x = np.linspace(x_range[0], x_range[1], 500)

            try:
                y = _safe_eval(expression, x)
            except Exception as e:
                return self._error_response(f"Invalid expression: {e}")

            # Create plot
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(x, y, 'b-', linewidth=2)
            ax.set_xlabel('x')
            ax.set_ylabel('y')
            ax.set_title(title)
            ax.grid(True, alpha=0.3)
            ax.axhline(y=0, color='k', linewidth=0.5)
            ax.axvline(x=0, color='k', linewidth=0.5)

            # Save to file
            output_path = f"plot_{hash(expression) % 100000}.png"
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()

            return self._success_response({
                "message": f"Plot created for: {expression}",
                "file_path": output_path,
                "x_range": x_range
            })

        except ImportError as e:
            return self._error_response(f"Required library not installed: {e}")
        except Exception as e:
            return self._error_response(str(e))
