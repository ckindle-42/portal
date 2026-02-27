"""Text Transformer Tool - Format conversion"""

import json
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter


class TextTransformerTool(BaseTool):
    """Transform text between formats (JSON, YAML, XML, TOML)"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="text_transformer",
            description="Convert text between JSON, YAML, XML, and TOML formats",
            category=ToolCategory.UTILITY,
            version="1.0.0",
            requires_confirmation=False,
            parameters=[
                ToolParameter(
                    name="content",
                    param_type="string",
                    description="Input text to transform",
                    required=True,
                ),
                ToolParameter(
                    name="from_format",
                    param_type="string",
                    description="Source format (json, yaml, xml, toml)",
                    required=True,
                ),
                ToolParameter(
                    name="to_format",
                    param_type="string",
                    description="Target format (json, yaml, xml, toml)",
                    required=True,
                ),
            ],
            examples=["Convert JSON to YAML: {...}"],
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Transform text format"""
        try:
            content = parameters.get("content", "")
            from_fmt = parameters.get("from_format", "").lower()
            to_fmt = parameters.get("to_format", "").lower()

            if not content:
                return self._error_response("No content provided")

            # Parse input
            data = self._parse(content, from_fmt)
            if data is None:
                return self._error_response(f"Failed to parse {from_fmt} input")

            # Convert to output
            output = self._serialize(data, to_fmt)
            if output is None:
                return self._error_response(f"Failed to serialize to {to_fmt}")

            return self._success_response({"converted": output, "from": from_fmt, "to": to_fmt})

        except Exception as e:
            return self._error_response(str(e))

    def _parse(self, content: str, fmt: str) -> Any:
        """Parse content from format"""
        try:
            if fmt == "json":
                return json.loads(content)
            elif fmt == "yaml":
                import yaml

                return yaml.safe_load(content)
            elif fmt == "xml":
                import xmltodict

                return xmltodict.parse(content)
            elif fmt == "toml":
                import toml

                return toml.loads(content)
            else:
                return None
        except Exception:
            return None

    def _serialize(self, data: Any, fmt: str) -> str:
        """Serialize data to format"""
        try:
            if fmt == "json":
                return json.dumps(data, indent=2)
            elif fmt == "yaml":
                import yaml

                return yaml.dump(data, default_flow_style=False)
            elif fmt == "xml":
                import xmltodict

                return xmltodict.unparse(data, pretty=True)
            elif fmt == "toml":
                import toml

                return toml.dumps(data)
            else:
                return None
        except Exception:
            return None
