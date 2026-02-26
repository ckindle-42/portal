"""
Comprehensive tests for PandocConverterTool.

Covers: metadata, format detection, command building, successful conversions,
        pandoc-not-available fallback, file-not-found, undetectable formats,
        template handling, metadata/toc/standalone flags, pdf engine, and
        subprocess error handling.
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from portal.core.interfaces.tool import ToolCategory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool():
    from portal.tools.document_processing.pandoc_converter import PandocConverterTool
    return PandocConverterTool()


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPandocConverterMetadata:

    def test_metadata_name(self):
        tool = _make_tool()
        assert tool.metadata.name == "pandoc_convert"

    def test_metadata_category(self):
        tool = _make_tool()
        assert tool.metadata.category == ToolCategory.UTILITY

    def test_metadata_version(self):
        tool = _make_tool()
        assert tool.metadata.version == "1.0.0"

    def test_metadata_has_input_file_param(self):
        tool = _make_tool()
        p = next((p for p in tool.metadata.parameters if p.name == "input_file"), None)
        assert p is not None
        assert p.required is True

    def test_metadata_has_output_file_param(self):
        tool = _make_tool()
        p = next((p for p in tool.metadata.parameters if p.name == "output_file"), None)
        assert p is not None
        assert p.required is True

    def test_metadata_parameter_names(self):
        tool = _make_tool()
        names = {p.name for p in tool.metadata.parameters}
        expected = {
            "input_file", "output_file", "from_format", "to_format",
            "template", "metadata", "toc", "standalone", "pdf_engine",
        }
        assert expected == names


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFormatDetection:

    def test_detect_markdown(self):
        tool = _make_tool()
        assert tool._detect_format("md") == "markdown"
        assert tool._detect_format("markdown") == "markdown"

    def test_detect_html(self):
        tool = _make_tool()
        assert tool._detect_format("html") == "html"
        assert tool._detect_format("htm") == "html"

    def test_detect_docx(self):
        tool = _make_tool()
        assert tool._detect_format("docx") == "docx"

    def test_detect_pdf(self):
        tool = _make_tool()
        assert tool._detect_format("pdf") == "pdf"

    def test_detect_latex(self):
        tool = _make_tool()
        assert tool._detect_format("tex") == "latex"
        assert tool._detect_format("latex") == "latex"

    def test_detect_epub(self):
        tool = _make_tool()
        assert tool._detect_format("epub") == "epub"

    def test_detect_ipynb(self):
        tool = _make_tool()
        assert tool._detect_format("ipynb") == "ipynb"

    def test_detect_unknown_returns_none(self):
        tool = _make_tool()
        assert tool._detect_format("xyz") is None

    def test_detect_strips_dot(self):
        tool = _make_tool()
        assert tool._detect_format(".md") == "markdown"

    def test_detect_case_insensitive(self):
        tool = _make_tool()
        assert tool._detect_format("HTML") == "html"


# ---------------------------------------------------------------------------
# Pandoc not available
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPandocNotAvailable:

    @pytest.mark.asyncio
    async def test_returns_error_when_pandoc_missing(self, temp_dir):
        with patch(
            "portal.tools.document_processing.pandoc_converter.PANDOC_AVAILABLE",
            False,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "input_file": str(temp_dir / "in.md"),
                "output_file": str(temp_dir / "out.html"),
            })
            assert result["success"] is False
            assert "Pandoc not installed" in result["error"]


# ---------------------------------------------------------------------------
# Input file not found
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestInputNotFound:

    @pytest.mark.asyncio
    async def test_input_file_missing(self, temp_dir):
        with patch(
            "portal.tools.document_processing.pandoc_converter.PANDOC_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "input_file": str(temp_dir / "nope.md"),
                "output_file": str(temp_dir / "out.html"),
            })
            assert result["success"] is False
            assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# Format auto-detection failure
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFormatDetectionFailure:

    @pytest.mark.asyncio
    async def test_undetectable_format(self, temp_dir):
        infile = temp_dir / "data.zzz"
        infile.write_text("hello")

        with patch(
            "portal.tools.document_processing.pandoc_converter.PANDOC_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "input_file": str(infile),
                "output_file": str(temp_dir / "out.qqq"),
            })
            assert result["success"] is False
            assert "Could not determine format" in result["error"]


# ---------------------------------------------------------------------------
# Build pandoc command
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBuildCommand:

    @pytest.mark.asyncio
    async def test_basic_command(self):
        tool = _make_tool()
        cmd = await tool._build_pandoc_command(
            input_file=Path("/in.md"),
            output_file=Path("/out.html"),
            from_format="markdown",
            to_format="html",
            template=None,
            metadata={},
            toc=False,
            standalone=False,
            pdf_engine="pdflatex",
        )
        assert cmd[0] == "pandoc"
        assert "/in.md" in cmd
        assert "-o" in cmd
        assert "/out.html" in cmd
        assert "-f" in cmd and "markdown" in cmd
        assert "-t" in cmd and "html" in cmd
        assert "--standalone" not in cmd
        assert "--toc" not in cmd

    @pytest.mark.asyncio
    async def test_standalone_flag(self):
        tool = _make_tool()
        cmd = await tool._build_pandoc_command(
            input_file=Path("/in.md"),
            output_file=Path("/out.html"),
            from_format="markdown",
            to_format="html",
            template=None,
            metadata={},
            toc=False,
            standalone=True,
            pdf_engine="pdflatex",
        )
        assert "--standalone" in cmd

    @pytest.mark.asyncio
    async def test_toc_flag(self):
        tool = _make_tool()
        cmd = await tool._build_pandoc_command(
            input_file=Path("/in.md"),
            output_file=Path("/out.html"),
            from_format="markdown",
            to_format="html",
            template=None,
            metadata={},
            toc=True,
            standalone=False,
            pdf_engine="pdflatex",
        )
        assert "--toc" in cmd

    @pytest.mark.asyncio
    async def test_metadata_flags(self):
        tool = _make_tool()
        cmd = await tool._build_pandoc_command(
            input_file=Path("/in.md"),
            output_file=Path("/out.html"),
            from_format="markdown",
            to_format="html",
            template=None,
            metadata={"title": "My Doc", "author": "Me"},
            toc=False,
            standalone=False,
            pdf_engine="pdflatex",
        )
        assert "-M" in cmd
        assert "title=My Doc" in cmd
        assert "author=Me" in cmd

    @pytest.mark.asyncio
    async def test_pdf_engine_flag(self):
        tool = _make_tool()
        cmd = await tool._build_pandoc_command(
            input_file=Path("/in.md"),
            output_file=Path("/out.pdf"),
            from_format="markdown",
            to_format="pdf",
            template=None,
            metadata={},
            toc=False,
            standalone=False,
            pdf_engine="xelatex",
        )
        assert "--pdf-engine" in cmd
        assert "xelatex" in cmd

    @pytest.mark.asyncio
    async def test_pdf_engine_not_added_for_non_pdf(self):
        tool = _make_tool()
        cmd = await tool._build_pandoc_command(
            input_file=Path("/in.md"),
            output_file=Path("/out.html"),
            from_format="markdown",
            to_format="html",
            template=None,
            metadata={},
            toc=False,
            standalone=False,
            pdf_engine="pdflatex",
        )
        assert "--pdf-engine" not in cmd

    @pytest.mark.asyncio
    async def test_template_flag_when_file_exists(self, temp_dir):
        tool = _make_tool()
        # Create a template file in the tool's template dir
        tpl = tool.template_dir / "custom.html"
        tpl.write_text("<html>$body$</html>")

        cmd = await tool._build_pandoc_command(
            input_file=Path("/in.md"),
            output_file=Path("/out.html"),
            from_format="markdown",
            to_format="html",
            template="custom",
            metadata={},
            toc=False,
            standalone=False,
            pdf_engine="pdflatex",
        )
        assert "--template" in cmd
        assert str(tpl) in cmd

    @pytest.mark.asyncio
    async def test_template_flag_when_file_missing(self):
        tool = _make_tool()
        cmd = await tool._build_pandoc_command(
            input_file=Path("/in.md"),
            output_file=Path("/out.html"),
            from_format="markdown",
            to_format="html",
            template="nonexistent_tpl",
            metadata={},
            toc=False,
            standalone=False,
            pdf_engine="pdflatex",
        )
        # No --template if the file doesn't exist
        assert "--template" not in cmd


# ---------------------------------------------------------------------------
# Successful conversion
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSuccessfulConversion:

    @pytest.mark.asyncio
    async def test_markdown_to_html(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        outfile = temp_dir / "doc.html"

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "portal.tools.document_processing.pandoc_converter.PANDOC_AVAILABLE",
            True,
        ), patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            # Write output file to simulate pandoc creating it
            outfile.write_text("<h1>Hello</h1>")

            tool = _make_tool()
            result = await tool.execute({
                "input_file": str(infile),
                "output_file": str(outfile),
            })
            assert result["success"] is True
            assert result["result"]["output_file"] == str(outfile)
            assert "output_size" in result["result"]

    @pytest.mark.asyncio
    async def test_explicit_formats(self, temp_dir):
        infile = temp_dir / "doc.rst"
        infile.write_text("Title\n=====")
        outfile = temp_dir / "doc.docx"

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "portal.tools.document_processing.pandoc_converter.PANDOC_AVAILABLE",
            True,
        ), patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            outfile.write_bytes(b"PKVVV")

            tool = _make_tool()
            result = await tool.execute({
                "input_file": str(infile),
                "output_file": str(outfile),
                "from_format": "rst",
                "to_format": "docx",
            })
            assert result["success"] is True
            assert result["metadata"]["from_format"] == "rst"
            assert result["metadata"]["to_format"] == "docx"


# ---------------------------------------------------------------------------
# Subprocess error
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSubprocessError:

    @pytest.mark.asyncio
    async def test_pandoc_nonzero_return(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        outfile = temp_dir / "out.html"

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"pandoc: error"))

        with patch(
            "portal.tools.document_processing.pandoc_converter.PANDOC_AVAILABLE",
            True,
        ), patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "input_file": str(infile),
                "output_file": str(outfile),
            })
            assert result["success"] is False
            assert "Pandoc conversion failed" in result["error"]

    @pytest.mark.asyncio
    async def test_output_file_not_created(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        outfile = temp_dir / "out.html"

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "portal.tools.document_processing.pandoc_converter.PANDOC_AVAILABLE",
            True,
        ), patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            # Don't create outfile — simulates pandoc completing but no output
            tool = _make_tool()
            result = await tool.execute({
                "input_file": str(infile),
                "output_file": str(outfile),
            })
            assert result["success"] is False
            assert "output file not found" in result["error"]

    @pytest.mark.asyncio
    async def test_subprocess_exception(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        outfile = temp_dir / "out.html"

        with patch(
            "portal.tools.document_processing.pandoc_converter.PANDOC_AVAILABLE",
            True,
        ), patch(
            "asyncio.create_subprocess_exec",
            side_effect=OSError("No pandoc binary"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "input_file": str(infile),
                "output_file": str(outfile),
            })
            assert result["success"] is False
            assert "Conversion error" in result["error"]


# ---------------------------------------------------------------------------
# Conversion with toc and standalone options
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestConversionOptions:

    @pytest.mark.asyncio
    async def test_toc_and_standalone(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        outfile = temp_dir / "doc.html"

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "portal.tools.document_processing.pandoc_converter.PANDOC_AVAILABLE",
            True,
        ), patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ) as mock_exec:
            outfile.write_text("<html></html>")

            tool = _make_tool()
            result = await tool.execute({
                "input_file": str(infile),
                "output_file": str(outfile),
                "toc": True,
                "standalone": True,
                "metadata": {"title": "T", "author": "A"},
            })
            assert result["success"] is True
            assert result["metadata"]["toc_included"] is True

            # Verify the command includes the flags
            called_args = mock_exec.call_args[0]
            assert "--toc" in called_args
            assert "--standalone" in called_args

    @pytest.mark.asyncio
    async def test_default_template_in_metadata(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        outfile = temp_dir / "doc.html"

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "portal.tools.document_processing.pandoc_converter.PANDOC_AVAILABLE",
            True,
        ), patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            outfile.write_text("<html></html>")

            tool = _make_tool()
            result = await tool.execute({
                "input_file": str(infile),
                "output_file": str(outfile),
            })
            assert result["success"] is True
            assert result["metadata"]["template"] == "default"


# ---------------------------------------------------------------------------
# Template installation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTemplateInstallation:

    def test_default_html_template_created(self):
        tool = _make_tool()
        html_tpl = tool.template_dir / "default.html"
        assert html_tpl.exists()
        content = html_tpl.read_text()
        assert "$body$" in content
