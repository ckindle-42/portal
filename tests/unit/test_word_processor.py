"""Tests for WordProcessorTool."""

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

from portal.core.interfaces.tool import ToolCategory

_has_docx = importlib.util.find_spec("docx") is not None


def _make_tool():
    from portal.tools.document_processing.word_processor import WordProcessorTool
    return WordProcessorTool()


def _patch_docx(available=True, doc=None):
    """Context manager: patch DOCX_AVAILABLE and optionally Document."""
    patches = [patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", available)]
    if doc is not None:
        patches.append(patch("portal.tools.document_processing.word_processor.Document",
                             return_value=doc))
    import contextlib
    return contextlib.ExitStack(), patches


@pytest.mark.unit
class TestWordProcessorMetadata:
    def test_metadata(self):
        meta = _make_tool().metadata
        assert meta.name == "word_processor"
        assert meta.category == ToolCategory.UTILITY
        assert meta.version == "1.0.0"
        names = {p.name for p in meta.parameters}
        assert {"action", "file_path", "text", "style"} <= names
        assert next(p for p in meta.parameters if p.name == "action").required is True


@pytest.mark.unit
class TestDocxUnavailable:
    @pytest.mark.asyncio
    async def test_returns_error(self):
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", False):
            result = await _make_tool().execute({"action": "create", "file_path": "/tmp/x.docx"})
        assert result["success"] is False
        assert "python-docx" in result["error"]


@pytest.mark.unit
class TestUnknownAction:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", ["explode", ""])
    async def test_unknown_action(self, action):
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute({"action": action, "file_path": "/tmp/x.docx"})
        assert result["success"] is False
        assert "Unknown action" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_docx, reason="python-docx not installed")
class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_create_success(self, temp_dir):
        mock_doc = MagicMock()
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True), \
             patch("portal.tools.document_processing.word_processor.Document", return_value=mock_doc):
            result = await _make_tool().execute(
                {"action": "create", "file_path": str(temp_dir / "doc.docx"), "title": "My Report"})
        assert result["success"] is True
        assert "file_path" in result["result"]
        mock_doc.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_metadata(self, temp_dir):
        mock_doc = MagicMock()
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True), \
             patch("portal.tools.document_processing.word_processor.Document", return_value=mock_doc):
            await _make_tool().execute({
                "action": "create", "file_path": str(temp_dir / "doc.docx"),
                "metadata": {"author": "Alice", "subject": "Q4", "keywords": "finance"},
            })
        cp = mock_doc.core_properties
        assert cp.author == "Alice"
        assert cp.subject == "Q4"

    @pytest.mark.asyncio
    async def test_create_exception(self, temp_dir):
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True), \
             patch("portal.tools.document_processing.word_processor.Document",
                   side_effect=RuntimeError("boom")):
            result = await _make_tool().execute(
                {"action": "create", "file_path": str(temp_dir / "doc.docx")})
        assert result["success"] is False
        assert "Creation error" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_docx, reason="python-docx not installed")
class TestAddHeading:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "add_heading", "file_path": str(temp_dir / "nope.docx"), "heading": "H1"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_empty_heading(self, temp_dir):
        (temp_dir / "doc.docx").write_bytes(b"PK")
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "add_heading", "file_path": str(temp_dir / "doc.docx")})
        assert result["success"] is False
        assert "Heading text required" in result["error"]

    @pytest.mark.asyncio
    async def test_add_heading_success(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")
        mock_doc = MagicMock()
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True), \
             patch("portal.tools.document_processing.word_processor.Document", return_value=mock_doc):
            result = await _make_tool().execute(
                {"action": "add_heading", "file_path": str(docx_file), "heading": "Ch1", "level": 2})
        assert result["success"] is True
        mock_doc.add_heading.assert_called_once_with("Ch1", level=2)


@pytest.mark.unit
@pytest.mark.skipif(not _has_docx, reason="python-docx not installed")
class TestAddParagraph:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "add_paragraph", "file_path": str(temp_dir / "nope.docx"), "text": "Hi"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_empty_text(self, temp_dir):
        (temp_dir / "doc.docx").write_bytes(b"PK")
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "add_paragraph", "file_path": str(temp_dir / "doc.docx")})
        assert result["success"] is False
        assert "Text required" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("style,attr", [
        ("bold", "bold"), ("italic", "italic"), ("underline", "underline"),
    ])
    async def test_add_paragraph_styles(self, temp_dir, style, attr):
        docx_file = temp_dir / f"doc_{style}.docx"
        docx_file.write_bytes(b"PK")
        mock_doc = MagicMock()
        mock_run = MagicMock()
        mock_para = MagicMock(runs=[mock_run])
        mock_doc.add_paragraph.return_value = mock_para
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True), \
             patch("portal.tools.document_processing.word_processor.Document", return_value=mock_doc), \
             patch("portal.tools.document_processing.word_processor.WD_ALIGN_PARAGRAPH") as m:
            m.LEFT = 0
            result = await _make_tool().execute(
                {"action": "add_paragraph", "file_path": str(docx_file), "text": "t", "style": style})
        assert result["success"] is True
        assert getattr(mock_run, attr) is True


@pytest.mark.unit
@pytest.mark.skipif(not _has_docx, reason="python-docx not installed")
class TestAddTable:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "add_table", "file_path": str(temp_dir / "nope.docx"),
                 "table_data": {"rows": [["a"]]}})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_empty_table_data(self, temp_dir):
        (temp_dir / "doc.docx").write_bytes(b"PK")
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "add_table", "file_path": str(temp_dir / "doc.docx")})
        assert result["success"] is False
        assert "Table data required" in result["error"]

    @pytest.mark.asyncio
    async def test_no_rows(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")
        mock_doc = MagicMock()
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True), \
             patch("portal.tools.document_processing.word_processor.Document", return_value=mock_doc):
            result = await _make_tool().execute(
                {"action": "add_table", "file_path": str(docx_file),
                 "table_data": {"headers": ["A"], "rows": []}})
        assert result["success"] is False
        assert "No table rows" in result["error"]

    @pytest.mark.asyncio
    async def test_add_table_with_headers(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")
        mock_doc = MagicMock()
        mock_table = MagicMock()
        hdr_cell = MagicMock(paragraphs=[MagicMock(runs=[MagicMock()])])
        hdr_row = MagicMock(cells=[hdr_cell, MagicMock(paragraphs=[MagicMock(runs=[MagicMock()])])])
        data_row = MagicMock(cells=[MagicMock(), MagicMock()])
        mock_table.rows = [hdr_row, data_row]
        mock_doc.add_table.return_value = mock_table
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True), \
             patch("portal.tools.document_processing.word_processor.Document", return_value=mock_doc):
            result = await _make_tool().execute(
                {"action": "add_table", "file_path": str(docx_file),
                 "table_data": {"headers": ["Name", "Age"], "rows": [["Alice", 30]]}})
        assert result["success"] is True
        assert result["result"]["table_added"] is True


@pytest.mark.unit
@pytest.mark.skipif(not _has_docx, reason="python-docx not installed")
class TestAddImage:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "add_image", "file_path": str(temp_dir / "nope.docx"),
                 "image_path": str(temp_dir / "img.png")})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_image_not_found(self, temp_dir):
        (temp_dir / "doc.docx").write_bytes(b"PK")
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "add_image", "file_path": str(temp_dir / "doc.docx"),
                 "image_path": str(temp_dir / "no.png")})
        assert result["success"] is False
        assert "Image not found" in result["error"]

    @pytest.mark.asyncio
    async def test_add_image_success(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")
        img_file = temp_dir / "img.png"
        img_file.write_bytes(b"PNG")
        mock_doc = MagicMock()
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True), \
             patch("portal.tools.document_processing.word_processor.Document", return_value=mock_doc), \
             patch("portal.tools.document_processing.word_processor.Inches", side_effect=lambda v: int(v * 914400)):
            result = await _make_tool().execute(
                {"action": "add_image", "file_path": str(docx_file), "image_path": str(img_file)})
        assert result["success"] is True
        mock_doc.add_picture.assert_called_once()


@pytest.mark.unit
@pytest.mark.skipif(not _has_docx, reason="python-docx not installed")
class TestReadDocument:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "read", "file_path": str(temp_dir / "nope.docx")})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_read_success(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")
        mock_doc = MagicMock()
        mock_doc.core_properties.title = "My Title"
        mock_doc.core_properties.author = "Alice"
        mock_doc.core_properties.subject = ""
        mock_doc.core_properties.keywords = ""
        mock_para = MagicMock(text="Hello world")
        mock_para.style.name = "Normal"
        mock_doc.paragraphs = [mock_para]
        mock_doc.tables = []
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True), \
             patch("portal.tools.document_processing.word_processor.Document", return_value=mock_doc):
            result = await _make_tool().execute(
                {"action": "read", "file_path": str(docx_file)})
        assert result["success"] is True
        assert result["result"]["metadata"]["title"] == "My Title"
        assert len(result["result"]["paragraphs"]) == 1

    @pytest.mark.asyncio
    async def test_empty_paragraphs_filtered(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")
        mock_doc = MagicMock()
        mock_doc.core_properties.title = mock_doc.core_properties.author = ""
        mock_doc.core_properties.subject = mock_doc.core_properties.keywords = ""
        empty_para = MagicMock(text="   ")
        real_para = MagicMock(text="Real text")
        real_para.style.name = "Normal"
        mock_doc.paragraphs = [empty_para, real_para]
        mock_doc.tables = []
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True), \
             patch("portal.tools.document_processing.word_processor.Document", return_value=mock_doc):
            result = await _make_tool().execute({"action": "read", "file_path": str(docx_file)})
        assert result["success"] is True
        assert len(result["result"]["paragraphs"]) == 1


@pytest.mark.unit
class TestSaveDocument:
    @pytest.mark.asyncio
    async def test_save_file_not_found(self, temp_dir):
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "save", "file_path": str(temp_dir / "nope.docx")})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_save_success(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")
        with patch("portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True):
            result = await _make_tool().execute({"action": "save", "file_path": str(docx_file)})
        assert result["success"] is True
        assert "saved" in result["result"]
