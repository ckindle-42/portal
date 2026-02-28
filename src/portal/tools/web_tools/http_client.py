"""HTTP REST Client Tool - Make HTTP requests"""

import json
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory


class HTTPClientTool(BaseTool):
    """Make HTTP requests to REST APIs"""

    METADATA = {
        "name": "http_client",
        "description": "Make HTTP requests (GET, POST, PUT, DELETE) to REST APIs",
        "category": ToolCategory.WEB,
        "version": "1.0.0",
        "requires_confirmation": True,
        "parameters": [
            {"name": "url", "param_type": "string", "description": "Target URL", "required": True},
            {"name": "method", "param_type": "string", "description": "HTTP method: GET, POST, PUT, DELETE", "required": False, "default": "GET"},
            {"name": "headers", "param_type": "string", "description": "JSON string of headers", "required": False},
            {"name": "body", "param_type": "string", "description": "Request body (JSON string for POST/PUT)", "required": False},
            {"name": "timeout", "param_type": "int", "description": "Timeout in seconds", "required": False, "default": 30},
        ],
        "examples": ["GET https://api.example.com/data"],
    }

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute HTTP request"""
        try:
            import aiohttp

            url = parameters.get("url", "")
            method = parameters.get("method", "GET").upper()
            headers_str = parameters.get("headers")
            body_str = parameters.get("body")
            timeout = parameters.get("timeout", 30)

            if not url:
                return self._error_response("URL is required")

            # Parse headers
            headers = {}
            if headers_str:
                try:
                    headers = json.loads(headers_str)
                except json.JSONDecodeError:
                    return self._error_response("Invalid headers JSON")

            # Parse body
            body = None
            if body_str and method in ["POST", "PUT", "PATCH"]:
                try:
                    body = json.loads(body_str)
                except json.JSONDecodeError:
                    body = body_str  # Use as raw string

            # Make request
            async with aiohttp.ClientSession() as session:
                request_kwargs = {
                    "url": url,
                    "headers": headers,
                    "timeout": aiohttp.ClientTimeout(total=timeout),
                }

                if body:
                    if isinstance(body, dict):
                        request_kwargs["json"] = body
                    else:
                        request_kwargs["data"] = body

                async with session.request(method, **request_kwargs) as response:
                    status = response.status
                    response_headers = dict(response.headers)

                    # Try to get response body
                    try:
                        response_body = await response.json()
                    except Exception:
                        response_body = await response.text()

                    return self._success_response(
                        {
                            "status": status,
                            "headers": {k: v for k, v in list(response_headers.items())[:10]},
                            "body": response_body
                            if len(str(response_body)) < 5000
                            else str(response_body)[:5000] + "...",
                        }
                    )

        except ImportError:
            return self._error_response("aiohttp not installed. Run: pip install aiohttp")
        except Exception as e:
            return self._error_response(str(e))
