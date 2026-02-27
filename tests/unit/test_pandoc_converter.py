"""Tests for PandocConverterTool."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from portal.core.interfaces.tool import ToolCategory

_P = "portal.tools.document_processing.pandoc_converter"


def _make_tool():
    from portal.tools.document_processing.pandoc_converter import PandocConverterTool
    return PandocConverterTool()


def _mock_proc(returncode=0, stderr=b""):
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", stderr))
    return proc


@pytest.mark.unit
class TestPandocConverterMetadata:
    def test_metadata(self):
        meta = _make_tool().metadata
        assert meta.name == "pandoc_convert"
        assert meta.category == ToolCategory.UTILITY
        assert meta.version == "1.0.0"
        names = {p.name for p in meta.parameters}
        expected = {"input_file", "output_file", "from_format", "to_format",
                    "template", "metadata", "toc", "standalone", "pdf_engine"}
        assert expected == names
        assert next(p for p in meta.parameters if p.name == "input_file").required is True
        assert next(p for p in meta.parameters if p.name == "output_file").required is True


@pytest.mark.unit
class TestFormatDetection:
    @pytest.mark.parametrize("ext,expected", [
        ("md", "markdown"), ("markdown", "markdown"),
        ("html", "html"), ("htm", "html"),
        ("docx", "docx"), ("pdf", "pdf"),
        ("tex", "latex"), ("latex", "latex"),
        ("epub", "epub"), ("ipynb", "ipynb"),
        ("xyz", None), (".md", "markdown"), ("HTML", "html"),
    ])
    def test_detect_formats(self, ext, expected):
        assert _make_tool()._detect_format(ext) == expected


@pytest.mark.unit
class TestPandocNotAvailable:
    @pytest.mark.asyncio
    async def test_returns_error(self, temp_dir):
        with patch(f"{_P}.PANDOC_AVAILABLE", False):
            result = await _make_tool().execute(
                {"input_file": str(temp_dir / "in.md"), "output_file": str(temp_dir / "out.html")})
        assert result["success"] is False
        assert "Pandoc not installed" in result["error"]


@pytest.mark.unit
class TestInputValidation:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(f"{_P}.PANDOC_AVAILABLE", True):
            result = await _make_tool().execute(
                {"input_file": str(temp_dir / "nope.md"), "output_file": str(temp_dir / "out.html")})
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_undetectable_format(self, temp_dir):
        infile = temp_dir / "data.zzz"
        infile.write_text("hello")
        with patch(f"{_P}.PANDOC_AVAILABLE", True):
            result = await _make_tool().execute(
                {"input_file": str(infile), "output_file": str(temp_dir / "out.qqq")})
        assert result["success"] is False
        assert "Could not determine format" in result["error"]


@pytest.mark.unit
class TestBuildCommand:
    @pytest.mark.asyncio
    async def test_basic_command(self):
        cmd = await _make_tool()._build_pandoc_command(
            input_file=Path("/in.md"), output_file=Path("/out.html"),
            from_format="markdown", to_format="html",
            template=None, metadata={}, toc=False, standalone=False, pdf_engine="pdflatex")
        assert cmd[0] == "pandoc"
        assert "-f" in cmd and "markdown" in cmd
        assert "-t" in cmd and "html" in cmd
        assert "--standalone" not in cmd and "--toc" not in cmd

    @pytest.mark.asyncio
    @pytest.mark.parametrize("flag,kwarg", [
        ("--standalone", {"standalone": True}),
        ("--toc", {"toc": True}),
    ])
    async def test_optional_flags(self, flag, kwarg):
        base = dict(input_file=Path("/in.md"), output_file=Path("/out.html"),
                    from_format="markdown", to_format="html",
                    template=None, metadata={}, toc=False, standalone=False, pdf_engine="pdflatex")
        base.update(kwarg)
        cmd = await _make_tool()._build_pandoc_command(**base)
        assert flag in cmd

    @pytest.mark.asyncio
    async def test_metadata_flags(self):
        cmd = await _make_tool()._build_pandoc_command(
            input_file=Path("/in.md"), output_file=Path("/out.html"),
            from_format="markdown", to_format="html",
            template=None, metadata={"title": "My Doc", "author": "Me"},
            toc=False, standalone=False, pdf_engine="pdflatex")
        assert "-M" in cmd
        assert "title=My Doc" in cmd

    @pytest.mark.asyncio
    async def test_pdf_engine_only_for_pdf(self):
        base = dict(input_file=Path("/in.md"), from_format="markdown",
                    template=None, metadata={}, toc=False, standalone=False, pdf_engine="xelatex")
        cmd_pdf = await _make_tool()._build_pandoc_command(
            output_file=Path("/out.pdf"), to_format="pdf", **base)
        cmd_html = await _make_tool()._build_pandoc_command(
            output_file=Path("/out.html"), to_format="html", **base)
        assert "--pdf-engine" in cmd_pdf and "xelatex" in cmd_pdf
        assert "--pdf-engine" not in cmd_html

    @pytest.mark.asyncio
    async def test_template_when_file_exists(self, temp_dir):
        tool = _make_tool()
        tpl = tool.template_dir / "custom.html"
        tpl.write_text("<html>$body$</html>")
        cmd = await tool._build_pandoc_command(
            input_file=Path("/in.md"), output_file=Path("/out.html"),
            from_format="markdown", to_format="html",
            template="custom", metadata={}, toc=False, standalone=False, pdf_engine="pdflatex")
        assert "--template" in cmd and str(tpl) in cmd

    @pytest.mark.asyncio
    async def test_template_ignored_when_missing(self):
        cmd = await _make_tool()._build_pandoc_command(
            input_file=Path("/in.md"), output_file=Path("/out.html"),
            from_format="markdown", to_format="html",
            template="nonexistent", metadata={}, toc=False, standalone=False, pdf_engine="pdflatex")
        assert "--template" not in cmd


@pytest.mark.unit
class TestConversion:
    @pytest.mark.asyncio
    async def test_markdown_to_html(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        outfile = temp_dir / "doc.html"
        outfile.write_text("<h1>Hello</h1>")
        with patch(f"{_P}.PANDOC_AVAILABLE", True), \
             patch("asyncio.create_subprocess_exec", return_value=_mock_proc()):
            result = await _make_tool().execute(
                {"input_file": str(infile), "output_file": str(outfile)})
        assert result["success"] is True
        assert result["result"]["output_file"] == str(outfile)
        assert "output_size" in result["result"]

    @pytest.mark.asyncio
    async def test_toc_and_standalone_flags(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        outfile = temp_dir / "doc.html"
        outfile.write_text("<html></html>")
        with patch(f"{_P}.PANDOC_AVAILABLE", True), \
             patch("asyncio.create_subprocess_exec", return_value=_mock_proc()) as mock_exec:
            result = await _make_tool().execute(
                {"input_file": str(infile), "output_file": str(outfile), "toc": True, "standalone": True})
        assert result["success"] is True
        assert result["metadata"]["toc_included"] is True
        called = mock_exec.call_args[0]
        assert "--toc" in called and "--standalone" in called

    @pytest.mark.asyncio
    async def test_pandoc_nonzero_return(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        with patch(f"{_P}.PANDOC_AVAILABLE", True), \
             patch("asyncio.create_subprocess_exec", return_value=_mock_proc(1, b"pandoc: error")):
            result = await _make_tool().execute(
                {"input_file": str(infile), "output_file": str(temp_dir / "out.html")})
        assert result["success"] is False
        assert "Pandoc conversion failed" in result["error"]

    @pytest.mark.asyncio
    async def test_output_file_not_created(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        with patch(f"{_P}.PANDOC_AVAILABLE", True), \
             patch("asyncio.create_subprocess_exec", return_value=_mock_proc()):
            result = await _make_tool().execute(
                {"input_file": str(infile), "output_file": str(temp_dir / "out.html")})
        assert result["success"] is False
        assert "output file not found" in result["error"]

    @pytest.mark.asyncio
    async def test_subprocess_exception(self, temp_dir):
        infile = temp_dir / "doc.md"
        infile.write_text("# Hello")
        with patch(f"{_P}.PANDOC_AVAILABLE", True), \
             patch("asyncio.create_subprocess_exec", side_effect=OSError("No pandoc binary")):
            result = await _make_tool().execute(
                {"input_file": str(infile), "output_file": str(temp_dir / "out.html")})
        assert result["success"] is False
        assert "Conversion error" in result["error"]


@pytest.mark.unit
class TestTemplateInstallation:
    def test_default_html_template_created(self):
        tool = _make_tool()
        html_tpl = tool.template_dir / "default.html"
        assert html_tpl.exists()
        assert "$body$" in html_tpl.read_text()
