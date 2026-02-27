"""
Pandoc Document Converter Tool
===============================

Universal document converter using Pandoc.

Supports:
- Markdown ↔ PDF ↔ DOCX ↔ HTML ↔ LaTeX ↔ EPUB ↔ ODT
- Preserves formatting and structure
- Template support for branded output
- Metadata handling
- Citation processing

Install: brew install pandoc
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter

logger = logging.getLogger(__name__)

# Check Pandoc availability
try:
    result = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, timeout=2)
    PANDOC_AVAILABLE = result.returncode == 0
except Exception:
    PANDOC_AVAILABLE = False


class PandocConverterTool(BaseTool):
    """
    Universal document converter using Pandoc.

    The Swiss Army knife of document conversion - handles 40+ formats!
    """

    # Supported formats
    SUPPORTED_FORMATS = {
        # Input and output
        "markdown": ["md", "markdown"],
        "html": ["html", "htm"],
        "docx": ["docx"],
        "pdf": ["pdf"],
        "latex": ["tex", "latex"],
        "epub": ["epub"],
        "odt": ["odt"],
        "rtf": ["rtf"],
        "rst": ["rst"],
        "org": ["org"],
        "textile": ["textile"],
        "asciidoc": ["asciidoc", "adoc"],
        "man": ["man"],
        "mediawiki": ["mediawiki"],
        "docbook": ["docbook"],
        "json": ["json"],
        "ipynb": ["ipynb"],  # Jupyter notebooks
        "pptx": ["pptx"],  # PowerPoint
        "xlsx": ["xlsx"],  # Excel (limited support)
    }

    def __init__(self) -> None:
        super().__init__()

        # Template directory
        self.template_dir = Path.home() / ".telegram_agent" / "pandoc_templates"
        self.template_dir.mkdir(parents=True, exist_ok=True)

        # Default templates
        self._install_default_templates()

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="pandoc_convert",
            description="Convert documents between 40+ formats (MD, PDF, DOCX, HTML, LaTeX, EPUB)",
            category=ToolCategory.UTILITY,
            version="1.0.0",
            requires_confirmation=False,
            parameters=[
                ToolParameter(
                    name="input_file",
                    param_type="string",
                    description="Path to input document",
                    required=True,
                ),
                ToolParameter(
                    name="output_file",
                    param_type="string",
                    description="Path to output document (extension determines format)",
                    required=True,
                ),
                ToolParameter(
                    name="from_format",
                    param_type="string",
                    description="Input format (auto-detected if not specified)",
                    required=False,
                ),
                ToolParameter(
                    name="to_format",
                    param_type="string",
                    description="Output format (auto-detected from extension if not specified)",
                    required=False,
                ),
                ToolParameter(
                    name="template",
                    param_type="string",
                    description="Template name for branded output (optional)",
                    required=False,
                ),
                ToolParameter(
                    name="metadata",
                    param_type="object",
                    description="Document metadata (title, author, date, etc.)",
                    required=False,
                ),
                ToolParameter(
                    name="toc",
                    param_type="boolean",
                    description="Include table of contents (default: False)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="standalone",
                    param_type="boolean",
                    description="Produce standalone document with headers (default: True)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="pdf_engine",
                    param_type="string",
                    description="PDF engine: pdflatex, xelatex, lualatex, wkhtmltopdf (default: pdflatex)",
                    required=False,
                    default="pdflatex",
                ),
            ],
        )

    def _install_default_templates(self) -> None:
        """Install default Pandoc templates"""

        # Simple HTML template
        html_template = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>$title$</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.6;
      max-width: 800px;
      margin: 0 auto;
      padding: 20px;
      color: #333;
    }
    code {
      background: #f4f4f4;
      padding: 2px 6px;
      border-radius: 3px;
    }
    pre {
      background: #f4f4f4;
      padding: 15px;
      border-radius: 5px;
      overflow-x: auto;
    }
  </style>
</head>
<body>
$if(title)$
<h1>$title$</h1>
$endif$
$if(author)$
<p><strong>Author:</strong> $author$</p>
$endif$
$if(date)$
<p><strong>Date:</strong> $date$</p>
$endif$
$body$
</body>
</html>
"""

        html_template_path = self.template_dir / "default.html"
        if not html_template_path.exists():
            html_template_path.write_text(html_template)

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute document conversion"""

        if not PANDOC_AVAILABLE:
            return self._error_response(
                "Pandoc not installed. Install:\n"
                "macOS: brew install pandoc\n"
                "Linux: sudo apt install pandoc"
            )

        input_file = Path(parameters.get("input_file", "")).expanduser()
        output_file = Path(parameters.get("output_file", "")).expanduser()
        from_format = parameters.get("from_format")
        to_format = parameters.get("to_format")
        template = parameters.get("template")
        metadata = parameters.get("metadata", {})
        toc = parameters.get("toc", False)
        standalone = parameters.get("standalone", True)
        pdf_engine = parameters.get("pdf_engine", "pdflatex")

        # Validate input
        if not input_file.exists():
            return self._error_response(f"Input file not found: {input_file}")

        # Auto-detect formats from extensions
        if not from_format:
            from_format = self._detect_format(input_file.suffix[1:])
        if not to_format:
            to_format = self._detect_format(output_file.suffix[1:])

        if not from_format or not to_format:
            return self._error_response(
                "Could not determine format. Specify from_format and to_format explicitly."
            )

        # Build Pandoc command
        try:
            cmd = await self._build_pandoc_command(
                input_file=input_file,
                output_file=output_file,
                from_format=from_format,
                to_format=to_format,
                template=template,
                metadata=metadata,
                toc=toc,
                standalone=standalone,
                pdf_engine=pdf_engine,
            )

            # Execute conversion
            logger.info(
                "Converting %s (%s) → %s (%s)", input_file, from_format, output_file, to_format
            )
            logger.debug("Command: %s", " ".join(cmd))

            result = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                return self._error_response(f"Pandoc conversion failed:\n{error_msg}")

            # Verify output
            if not output_file.exists():
                return self._error_response("Conversion completed but output file not found")

            output_size = output_file.stat().st_size

            return self._success_response(
                result={
                    "output_file": str(output_file),
                    "output_size": output_size,
                    "output_size_mb": round(output_size / (1024 * 1024), 2),
                },
                metadata={
                    "from_format": from_format,
                    "to_format": to_format,
                    "template": template or "default",
                    "toc_included": toc,
                },
            )

        except Exception as e:
            logger.error("Pandoc conversion error: %s", e)
            return self._error_response(f"Conversion error: {e}")

    async def _build_pandoc_command(
        self,
        input_file: Path,
        output_file: Path,
        from_format: str,
        to_format: str,
        template: str | None,
        metadata: dict[str, str],
        toc: bool,
        standalone: bool,
        pdf_engine: str,
    ) -> list[str]:
        """Build Pandoc command with all options"""

        cmd = ["pandoc"]

        # Input/output
        cmd.extend([str(input_file), "-o", str(output_file)])

        # Formats
        cmd.extend(["-f", from_format, "-t", to_format])

        # Standalone document
        if standalone:
            cmd.append("--standalone")

        # Table of contents
        if toc:
            cmd.append("--toc")

        # Template
        if template:
            template_path = self.template_dir / f"{template}.{to_format}"
            if template_path.exists():
                cmd.extend(["--template", str(template_path)])

        # Metadata
        for key, value in metadata.items():
            cmd.extend(["-M", f"{key}={value}"])

        # PDF-specific options
        if to_format == "pdf":
            cmd.extend(["--pdf-engine", pdf_engine])

        return cmd

    def _detect_format(self, extension: str) -> str | None:
        """Detect Pandoc format from file extension"""

        extension = extension.lower().lstrip(".")

        for format_name, extensions in self.SUPPORTED_FORMATS.items():
            if extension in extensions:
                return format_name

        return None
