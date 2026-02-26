"""Math Visualizer Tool - Plot equations and functions"""

from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter


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

            # Validate expression (security check)
            allowed_chars = set("x0123456789+-*/().** sincostanlogexpsqrtabspi")
            expr_clean = expression.replace(" ", "")
            if not all(c in allowed_chars for c in expr_clean.replace("np.", "")):
                return self._error_response("Expression contains invalid characters")

            # Generate x values
            x = np.linspace(x_range[0], x_range[1], 500)

            # Safe expression evaluation
            safe_dict = {
                "x": x,
                "np": np,
                "sin": np.sin,
                "cos": np.cos,
                "tan": np.tan,
                "log": np.log,
                "exp": np.exp,
                "sqrt": np.sqrt,
                "abs": np.abs,
                "pi": np.pi
            }

            try:
                try:
                    import numexpr
                    y = numexpr.evaluate(expression, local_dict={"x": x})
                except ImportError:
                    # Fallback: use ast-based safe eval with restricted builtins
                    y = eval(expression, {"__builtins__": {}}, safe_dict)
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
