"""Tests for DocumentMetadataExtractorTool."""

from pathlib import Path
from unittest.mock import patch

import pytest

from portal.core.interfaces.tool import ToolCategory


def _make_tool():
    from portal.tools.document_processing.document_metadata_extractor import (
        DocumentMetadataExtractorTool,
    )
    return DocumentMetadataExtractorTool()


def _create_file(tmp: Path, name: str, content: bytes = b"data") -> Path:
    p = tmp / name
    p.write_bytes(content)
    return p


_EXTRACTOR_BASE = (
    "portal.tools.document_processing.document_metadata_extractor"
    ".DocumentMetadataExtractorTool"
)


@pytest.mark.unit
class TestDocumentMetadataExtractorMetadata:
    def test_metadata(self):
        tool = _make_tool()
        assert tool.metadata.name == "document_metadata"
        assert tool.metadata.category == ToolCategory.UTILITY
        assert tool.metadata.version == "1.0.0"
        names = {p.name for p in tool.metadata.parameters}
        assert names == {"file_path", "detailed"}


@pytest.mark.unit
class TestFileNotFound:
    @pytest.mark.asyncio
    async def test_nonexistent_file(self, temp_dir):
        tool = _make_tool()
        result = await tool.execute({"file_path": str(temp_dir / "nope.pdf")})
        assert result["success"] is False
        assert "not found" in result["error"]


@pytest.mark.unit
class TestUnsupportedFormat:
    @pytest.mark.asyncio
    async def test_unsupported_extension(self, temp_dir):
        f = _create_file(temp_dir, "data.xyz")
        tool = _make_tool()
        result = await tool.execute({"file_path": str(f)})
        assert result["success"] is False
        assert "Unsupported" in result["error"]


@pytest.mark.unit
class TestPdfExtraction:
    @pytest.mark.asyncio
    async def test_pdf_success(self, temp_dir):
        f = _create_file(temp_dir, "doc.pdf")
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_pdf_metadata",
                   return_value={"type": "PDF Document", "pages": 2, "title": "My PDF", "author": "Bob"}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert result["result"]["type"] == "PDF Document"
            assert "file_properties" in result["result"]

    @pytest.mark.asyncio
    async def test_pdf_import_error(self, temp_dir):
        f = _create_file(temp_dir, "doc.pdf")
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_pdf_metadata",
                   return_value={"error": "PyPDF2 not installed"}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert result["result"]["error"] == "PyPDF2 not installed"


@pytest.mark.unit
class TestDocxExtraction:
    @pytest.mark.asyncio
    async def test_docx_success(self, temp_dir):
        f = _create_file(temp_dir, "file.docx")
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_docx_metadata",
                   return_value={"type": "Word Document", "title": "Doc", "author": "A"}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert result["result"]["type"] == "Word Document"

    @pytest.mark.asyncio
    async def test_doc_extension_routes_to_docx(self, temp_dir):
        f = _create_file(temp_dir, "file.doc")
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_docx_metadata",
                   return_value={"type": "Word Document"}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_docx_import_error(self, temp_dir):
        f = _create_file(temp_dir, "file.docx")
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_docx_metadata",
                   return_value={"error": "python-docx not installed"}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert "error" in result["result"]


@pytest.mark.unit
class TestPptxExtraction:
    @pytest.mark.asyncio
    async def test_pptx_success(self, temp_dir):
        f = _create_file(temp_dir, "pres.pptx")
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_pptx_metadata",
                   return_value={"type": "PowerPoint Presentation", "slides": 3}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert result["result"]["slides"] == 3


@pytest.mark.unit
class TestXlsxExtraction:
    @pytest.mark.asyncio
    async def test_xlsx_success(self, temp_dir):
        f = _create_file(temp_dir, "data.xlsx")
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_xlsx_metadata",
                   return_value={"type": "Excel Spreadsheet", "sheets": ["Sheet1"]}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert result["result"]["type"] == "Excel Spreadsheet"

    @pytest.mark.asyncio
    async def test_xls_extension(self, temp_dir):
        f = _create_file(temp_dir, "data.xls")
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_xlsx_metadata",
                   return_value={"type": "Excel Spreadsheet"}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True


@pytest.mark.unit
class TestImageExtraction:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("filename,fmt", [
        ("photo.jpg", "JPEG"),
        ("pic.jpeg", "JPEG"),
        ("img.png", "PNG"),
        ("anim.gif", "GIF"),
        ("img.bmp", "BMP"),
    ])
    async def test_image_formats(self, temp_dir, filename, fmt):
        f = _create_file(temp_dir, filename)
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_image_metadata",
                   return_value={"type": "Image", "format": fmt}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True


@pytest.mark.unit
class TestAudioExtraction:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("filename", [
        "song.mp3", "clip.wav", "music.flac", "clip.ogg", "clip.m4a",
    ])
    async def test_audio_formats(self, temp_dir, filename):
        f = _create_file(temp_dir, filename)
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_audio_metadata",
                   return_value={"type": "Audio"}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True


@pytest.mark.unit
class TestFileProperties:
    @pytest.mark.asyncio
    async def test_file_properties_present(self, temp_dir):
        f = _create_file(temp_dir, "test.pdf", b"some content here")
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_pdf_metadata",
                   return_value={"type": "PDF Document"}):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            fp = result["result"]["file_properties"]
            assert fp["size_bytes"] > 0
            assert "size_mb" in fp
            assert "created" in fp
            assert "modified" in fp
            assert fp["format"] == "pdf"


@pytest.mark.unit
class TestGeneralException:
    @pytest.mark.asyncio
    async def test_extraction_exception_is_caught(self, temp_dir):
        f = _create_file(temp_dir, "bad.pdf")
        tool = _make_tool()
        with patch(f"{_EXTRACTOR_BASE}._extract_pdf_metadata",
                   side_effect=RuntimeError("kaboom")):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is False
            assert "Extraction error" in result["error"]
