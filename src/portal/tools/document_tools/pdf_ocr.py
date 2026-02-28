"""
PDF OCR Tool - Extract text from PDFs using OCR
"""

import logging
from pathlib import Path
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image  # noqa: F401

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class PDFOCRTool(BaseTool):
    """Extract text from PDFs using OCR"""

    METADATA = {
        "name": "pdf_ocr",
        "description": "Extract text from PDF files using OCR",
        "category": ToolCategory.DATA,
        "parameters": [
            {"name": "pdf_path", "param_type": "string", "description": "Path to PDF file", "required": True},
            {"name": "language", "param_type": "string", "description": "OCR language (default: eng)", "required": False},
            {"name": "dpi", "param_type": "int", "description": "Image DPI for conversion (default: 300)", "required": False},
        ],
    }

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Perform OCR on PDF"""

        if not OCR_AVAILABLE:
            return self._error_response(
                "OCR dependencies not installed. Run: pip install pytesseract pdf2image"
            )

        pdf_path = Path(parameters.get("pdf_path"))
        language = parameters.get("language", "eng")
        dpi = parameters.get("dpi", 300)

        if not pdf_path.exists():
            return self._error_response(f"PDF not found: {pdf_path}")

        try:
            # Convert PDF to images
            logger.info("Converting PDF to images: %s", pdf_path)
            images = convert_from_path(str(pdf_path), dpi=dpi)

            # OCR each page
            text_pages = []
            for i, image in enumerate(images):
                logger.info("Processing page %s/%s", i + 1, len(images))
                text = pytesseract.image_to_string(image, lang=language)
                text_pages.append(text)

            full_text = "\n\n--- Page Break ---\n\n".join(text_pages)

            return self._success_response(
                result=full_text,
                metadata={
                    "pages": len(text_pages),
                    "characters": len(full_text),
                    "language": language,
                },
            )

        except Exception as e:
            return self._error_response(f"OCR failed: {str(e)}")
