"""QR Code Generator Tool"""

import base64
import io
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter


class QRGeneratorTool(BaseTool):
    """Generate QR codes from text or URLs"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="qr_generator",
            description="Generate QR codes from text or URLs",
            category=ToolCategory.UTILITY,
            version="1.0.0",
            requires_confirmation=False,
            parameters=[
                ToolParameter(
                    name="content",
                    param_type="string",
                    description="Text or URL to encode",
                    required=True,
                ),
                ToolParameter(
                    name="size",
                    param_type="int",
                    description="QR code size (1-10)",
                    required=False,
                    default=5,
                ),
            ],
            examples=["Generate QR for https://example.com"],
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Generate QR code"""
        try:
            import qrcode

            content = parameters.get("content", "")
            size = min(max(parameters.get("size", 5), 1), 10)

            if not content:
                return self._error_response("No content provided")

            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=size,
                border=4,
            )
            qr.add_data(content)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode()

            # Save to file
            output_path = f"qr_{hash(content) % 100000}.png"
            img.save(output_path)

            return self._success_response(
                {
                    "message": f"QR code generated for: {content[:50]}...",
                    "file_path": output_path,
                    "base64": img_base64[:100] + "...",  # Truncated for display
                }
            )

        except ImportError:
            return self._error_response(
                "qrcode library not installed. Run: pip install qrcode[pil]"
            )
        except Exception as e:
            return self._error_response(str(e))
