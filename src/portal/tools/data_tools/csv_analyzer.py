"""CSV Analyzer Tool - Data analysis for CSV files"""

import os
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory


class CSVAnalyzerTool(BaseTool):
    """Analyze CSV files with statistics and summaries"""

    METADATA = {
        "name": "csv_analyzer",
        "description": "Analyze CSV files - statistics, summaries, and insights",
        "category": ToolCategory.DATA,
        "version": "1.0.0",
        "requires_confirmation": False,
        "parameters": [
            {"name": "file_path", "param_type": "string", "description": "Path to CSV file", "required": True},
            {"name": "analysis_type", "param_type": "string", "description": "Type: summary, statistics, head, describe", "required": False, "default": "summary"},
        ],
        "examples": ["Analyze data.csv and show statistics"],
    }

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Analyze CSV file"""
        try:
            import pandas as pd

            file_path = parameters.get("file_path", "")
            analysis_type = parameters.get("analysis_type", "summary").lower()

            if not os.path.exists(file_path):
                return self._error_response(f"File not found: {file_path}")

            # Load CSV
            df = pd.read_csv(file_path)

            result = {
                "file": file_path,
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
            }

            if analysis_type == "head":
                result["preview"] = df.head(10).to_string()
            if analysis_type == "statistics":
                result["statistics"] = df.describe().to_string()
            if analysis_type == "describe":
                result["dtypes"] = df.dtypes.to_string()
                result["null_counts"] = df.isnull().sum().to_string()
                result["statistics"] = df.describe().to_string()
            if analysis_type not in ("head", "statistics", "describe"):
                result["dtypes"] = {col: str(dtype) for col, dtype in df.dtypes.items()}
                result["null_counts"] = df.isnull().sum().to_dict()
                numeric_cols = df.select_dtypes(include=["number"]).columns
                if len(numeric_cols) > 0:
                    result["numeric_summary"] = {
                        col: {
                            "mean": float(df[col].mean()),
                            "min": float(df[col].min()),
                            "max": float(df[col].max()),
                        }
                        for col in numeric_cols[:5]
                    }

            return self._success_response(result)

        except ImportError:
            return self._error_response("pandas not installed. Run: pip install pandas")
        except Exception as e:
            return self._error_response(str(e))
