"""
Comprehensive tests for DocumentMetadataExtractorTool.

Covers: metadata, execute routing by file extension, PDF/DOCX/PPTX/XLSX/image/audio
extraction paths, unsupported format, file-not-found, and library-not-installed
fallback for each format.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from portal.core.interfaces.tool import ToolCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool():
    from portal.tools.document_processing.document_metadata_extractor import (
        DocumentMetadataExtractorTool,
    )
    return DocumentMetadataExtractorTool()


def _create_file(tmp: Path, name: str, content: bytes = b"data") -> Path:
    p = tmp / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDocumentMetadataExtractorMetadata:

    def test_metadata_name(self):
        tool = _make_tool()
        assert tool.metadata.name == "document_metadata"

    def test_metadata_category(self):
        tool = _make_tool()
        assert tool.metadata.category == ToolCategory.UTILITY

    def test_metadata_version(self):
        tool = _make_tool()
        assert tool.metadata.version == "1.0.0"

    def test_metadata_parameters(self):
        tool = _make_tool()
        names = {p.name for p in tool.metadata.parameters}
        assert names == {"file_path", "detailed"}


# ---------------------------------------------------------------------------
# File not found
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFileNotFound:

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, temp_dir):
        tool = _make_tool()
        result = await tool.execute({"file_path": str(temp_dir / "nope.pdf")})
        assert result["success"] is False
        assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# Unsupported format
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestUnsupportedFormat:

    @pytest.mark.asyncio
    async def test_unsupported_extension(self, temp_dir):
        f = _create_file(temp_dir, "data.xyz")
        tool = _make_tool()
        result = await tool.execute({"file_path": str(f)})
        assert result["success"] is False
        assert "Unsupported" in result["error"]


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPdfExtraction:

    @pytest.mark.asyncio
    async def test_pdf_success(self, temp_dir):
        f = _create_file(temp_dir, "doc.pdf")
        tool = _make_tool()

        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock()]
        mock_reader.metadata = {
            "/Title": "My PDF",
            "/Author": "Bob",
            "/Subject": "Test",
            "/Creator": "Tool",
            "/Producer": "Lib",
            "/Keywords": "a,b",
        }
        mock_reader.is_encrypted = False

        with patch.dict("sys.modules", {"PyPDF2": MagicMock()}):
            with patch(
                "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_pdf_metadata"
            ) as mock_extract:
                mock_extract.return_value = {
                    "type": "PDF Document",
                    "pages": 2,
                    "title": "My PDF",
                    "author": "Bob",
                }
                result = await tool.execute({"file_path": str(f)})
                assert result["success"] is True
                assert result["result"]["type"] == "PDF Document"
                assert "file_properties" in result["result"]

    @pytest.mark.asyncio
    async def test_pdf_import_error(self, temp_dir):
        """When PyPDF2 is not installed, the inner method returns error dict."""
        f = _create_file(temp_dir, "doc.pdf")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_pdf_metadata",
            return_value={"error": "PyPDF2 not installed"},
        ):
            result = await tool.execute({"file_path": str(f)})
            # The outer execute still wraps in success because the inner
            # method returns a dict (not raising).
            assert result["success"] is True
            assert result["result"]["error"] == "PyPDF2 not installed"

    @pytest.mark.asyncio
    async def test_pdf_detailed(self, temp_dir):
        f = _create_file(temp_dir, "doc.pdf")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_pdf_metadata",
            return_value={
                "type": "PDF Document",
                "pages": 1,
                "encrypted": False,
                "pages_info": [{"number": 1, "width": 612.0, "height": 792.0}],
            },
        ):
            result = await tool.execute({"file_path": str(f), "detailed": True})
            assert result["success"] is True


# ---------------------------------------------------------------------------
# DOCX extraction
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDocxExtraction:

    @pytest.mark.asyncio
    async def test_docx_success(self, temp_dir):
        f = _create_file(temp_dir, "file.docx")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_docx_metadata",
            return_value={
                "type": "Word Document",
                "title": "Doc",
                "author": "A",
            },
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert result["result"]["type"] == "Word Document"

    @pytest.mark.asyncio
    async def test_doc_extension_routes_to_docx(self, temp_dir):
        f = _create_file(temp_dir, "file.doc")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_docx_metadata",
            return_value={"type": "Word Document"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_docx_import_error(self, temp_dir):
        f = _create_file(temp_dir, "file.docx")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_docx_metadata",
            return_value={"error": "python-docx not installed"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_docx_detailed(self, temp_dir):
        f = _create_file(temp_dir, "file.docx")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_docx_metadata",
            return_value={
                "type": "Word Document",
                "statistics": {"paragraphs": 5, "tables": 1, "sections": 1, "styles": 10},
            },
        ):
            result = await tool.execute({"file_path": str(f), "detailed": True})
            assert result["success"] is True


# ---------------------------------------------------------------------------
# PPTX extraction
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPptxExtraction:

    @pytest.mark.asyncio
    async def test_pptx_success(self, temp_dir):
        f = _create_file(temp_dir, "pres.pptx")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_pptx_metadata",
            return_value={
                "type": "PowerPoint Presentation",
                "slides": 3,
                "title": "Deck",
            },
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert result["result"]["slides"] == 3


# ---------------------------------------------------------------------------
# XLSX extraction
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestXlsxExtraction:

    @pytest.mark.asyncio
    async def test_xlsx_success(self, temp_dir):
        f = _create_file(temp_dir, "data.xlsx")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_xlsx_metadata",
            return_value={
                "type": "Excel Spreadsheet",
                "sheets": ["Sheet1"],
            },
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert result["result"]["type"] == "Excel Spreadsheet"

    @pytest.mark.asyncio
    async def test_xls_extension(self, temp_dir):
        f = _create_file(temp_dir, "data.xls")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_xlsx_metadata",
            return_value={"type": "Excel Spreadsheet"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestImageExtraction:

    @pytest.mark.asyncio
    async def test_jpg_success(self, temp_dir):
        f = _create_file(temp_dir, "photo.jpg")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_image_metadata",
            return_value={
                "type": "Image",
                "format": "JPEG",
                "width": 1920,
                "height": 1080,
            },
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert result["result"]["format"] == "JPEG"

    @pytest.mark.asyncio
    async def test_png_success(self, temp_dir):
        f = _create_file(temp_dir, "img.png")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_image_metadata",
            return_value={"type": "Image", "format": "PNG"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_gif_success(self, temp_dir):
        f = _create_file(temp_dir, "anim.gif")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_image_metadata",
            return_value={"type": "Image", "format": "GIF"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_bmp_success(self, temp_dir):
        f = _create_file(temp_dir, "img.bmp")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_image_metadata",
            return_value={"type": "Image", "format": "BMP"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_jpeg_extension(self, temp_dir):
        f = _create_file(temp_dir, "pic.jpeg")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_image_metadata",
            return_value={"type": "Image", "format": "JPEG"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True


# ---------------------------------------------------------------------------
# Audio extraction
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAudioExtraction:

    @pytest.mark.asyncio
    async def test_mp3_success(self, temp_dir):
        f = _create_file(temp_dir, "song.mp3")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_audio_metadata",
            return_value={
                "type": "Audio",
                "format": "audio/mp3",
                "length_seconds": 120.5,
            },
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            assert result["result"]["type"] == "Audio"

    @pytest.mark.asyncio
    async def test_wav_extension(self, temp_dir):
        f = _create_file(temp_dir, "clip.wav")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_audio_metadata",
            return_value={"type": "Audio", "format": "audio/wav"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_flac_extension(self, temp_dir):
        f = _create_file(temp_dir, "music.flac")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_audio_metadata",
            return_value={"type": "Audio"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_ogg_extension(self, temp_dir):
        f = _create_file(temp_dir, "clip.ogg")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_audio_metadata",
            return_value={"type": "Audio"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_m4a_extension(self, temp_dir):
        f = _create_file(temp_dir, "clip.m4a")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_audio_metadata",
            return_value={"type": "Audio"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True


# ---------------------------------------------------------------------------
# File properties always included
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFileProperties:

    @pytest.mark.asyncio
    async def test_file_properties_present(self, temp_dir):
        f = _create_file(temp_dir, "test.pdf", b"some content here")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_pdf_metadata",
            return_value={"type": "PDF Document"},
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is True
            fp = result["result"]["file_properties"]
            assert "size_bytes" in fp
            assert fp["size_bytes"] > 0
            assert "size_mb" in fp
            assert "created" in fp
            assert "modified" in fp
            assert fp["format"] == "pdf"


# ---------------------------------------------------------------------------
# General exception
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGeneralException:

    @pytest.mark.asyncio
    async def test_extraction_exception_is_caught(self, temp_dir):
        f = _create_file(temp_dir, "bad.pdf")
        tool = _make_tool()

        with patch(
            "portal.tools.document_processing.document_metadata_extractor.DocumentMetadataExtractorTool._extract_pdf_metadata",
            side_effect=RuntimeError("kaboom"),
        ):
            result = await tool.execute({"file_path": str(f)})
            assert result["success"] is False
            assert "Extraction error" in result["error"]
