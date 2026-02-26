"""
Comprehensive tests for WordProcessorTool.

Covers: metadata, create, add_heading, add_paragraph, add_table, add_image,
        read, save, unknown action, docx-not-available fallback, and error handling.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from portal.core.interfaces.tool import ToolCategory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool():
    from portal.tools.document_processing.word_processor import WordProcessorTool
    return WordProcessorTool()


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestWordProcessorMetadata:

    def test_metadata_name(self):
        tool = _make_tool()
        assert tool.metadata.name == "word_processor"

    def test_metadata_category(self):
        tool = _make_tool()
        assert tool.metadata.category == ToolCategory.UTILITY

    def test_metadata_version(self):
        tool = _make_tool()
        assert tool.metadata.version == "1.0.0"

    def test_metadata_has_action_parameter(self):
        tool = _make_tool()
        action = next((p for p in tool.metadata.parameters if p.name == "action"), None)
        assert action is not None
        assert action.required is True

    def test_metadata_parameter_names(self):
        tool = _make_tool()
        names = {p.name for p in tool.metadata.parameters}
        expected = {
            "action", "file_path", "title", "text", "heading", "level",
            "style", "alignment", "table_data", "image_path",
            "image_width", "metadata",
        }
        assert expected == names


# ---------------------------------------------------------------------------
# DOCX not available
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDocxNotAvailable:

    @pytest.mark.asyncio
    async def test_returns_error_when_docx_missing(self):
        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", False
        ):
            tool = _make_tool()
            result = await tool.execute({"action": "create", "file_path": "/tmp/x.docx"})
            assert result["success"] is False
            assert "python-docx" in result["error"]


# ---------------------------------------------------------------------------
# Unknown / empty action
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestWordUnknownAction:

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({"action": "explode", "file_path": "/tmp/x.docx"})
            assert result["success"] is False
            assert "Unknown action" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_action(self):
        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({"file_path": "/tmp/x.docx"})
            assert result["success"] is False
            assert "Unknown action" in result["error"]


# ---------------------------------------------------------------------------
# Create document
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCreateDocument:

    @pytest.mark.asyncio
    async def test_create_success(self, temp_dir):
        mock_doc = MagicMock()
        mock_doc.core_properties = MagicMock()

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "create",
                "file_path": str(temp_dir / "doc.docx"),
                "title": "My Report",
            })
            assert result["success"] is True
            assert "file_path" in result["result"]
            mock_doc.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_metadata(self, temp_dir):
        mock_doc = MagicMock()
        mock_doc.core_properties = MagicMock()

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "create",
                "file_path": str(temp_dir / "doc.docx"),
                "title": "Report",
                "metadata": {"author": "Alice", "subject": "Q4", "keywords": "finance"},
            })
            assert result["success"] is True
            cp = mock_doc.core_properties
            assert cp.author == "Alice"
            assert cp.subject == "Q4"
            assert cp.keywords == "finance"

    @pytest.mark.asyncio
    async def test_create_exception(self, temp_dir):
        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            side_effect=RuntimeError("boom"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "create",
                "file_path": str(temp_dir / "doc.docx"),
            })
            assert result["success"] is False
            assert "Creation error" in result["error"]


# ---------------------------------------------------------------------------
# Add heading
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAddHeading:

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_heading",
                "file_path": str(temp_dir / "nope.docx"),
                "heading": "H1",
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_heading(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_heading",
                "file_path": str(docx_file),
            })
            assert result["success"] is False
            assert "Heading text required" in result["error"]

    @pytest.mark.asyncio
    async def test_add_heading_success(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_heading",
                "file_path": str(docx_file),
                "heading": "Chapter 1",
                "level": 2,
            })
            assert result["success"] is True
            assert result["result"]["heading_added"] == "Chapter 1"
            mock_doc.add_heading.assert_called_once_with("Chapter 1", level=2)

    @pytest.mark.asyncio
    async def test_add_heading_exception(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            side_effect=RuntimeError("bad"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_heading",
                "file_path": str(docx_file),
                "heading": "H",
            })
            assert result["success"] is False
            assert "Add heading error" in result["error"]


# ---------------------------------------------------------------------------
# Add paragraph
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAddParagraph:

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_paragraph",
                "file_path": str(temp_dir / "nope.docx"),
                "text": "Hello",
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_text(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_paragraph",
                "file_path": str(docx_file),
            })
            assert result["success"] is False
            assert "Text required" in result["error"]

    @pytest.mark.asyncio
    async def test_add_paragraph_normal(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()
        mock_para = MagicMock()
        mock_run = MagicMock()
        mock_para.runs = [mock_run]
        mock_doc.add_paragraph.return_value = mock_para

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ), patch(
            "portal.tools.document_processing.word_processor.WD_ALIGN_PARAGRAPH",
        ) as mock_align:
            mock_align.LEFT = 0
            mock_align.CENTER = 1
            mock_align.RIGHT = 2
            mock_align.JUSTIFY = 3
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_paragraph",
                "file_path": str(docx_file),
                "text": "Hello world",
                "style": "normal",
                "alignment": "left",
            })
            assert result["success"] is True
            assert result["result"]["paragraph_added"] is True

    @pytest.mark.asyncio
    async def test_add_paragraph_bold(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()
        mock_run = MagicMock()
        mock_para = MagicMock()
        mock_para.runs = [mock_run]
        mock_doc.add_paragraph.return_value = mock_para

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ), patch(
            "portal.tools.document_processing.word_processor.WD_ALIGN_PARAGRAPH",
        ) as mock_align:
            mock_align.LEFT = 0
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_paragraph",
                "file_path": str(docx_file),
                "text": "Bold text",
                "style": "bold",
            })
            assert result["success"] is True
            assert mock_run.bold is True

    @pytest.mark.asyncio
    async def test_add_paragraph_italic(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()
        mock_run = MagicMock()
        mock_para = MagicMock()
        mock_para.runs = [mock_run]
        mock_doc.add_paragraph.return_value = mock_para

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ), patch(
            "portal.tools.document_processing.word_processor.WD_ALIGN_PARAGRAPH",
        ) as mock_align:
            mock_align.LEFT = 0
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_paragraph",
                "file_path": str(docx_file),
                "text": "Italic text",
                "style": "italic",
            })
            assert result["success"] is True
            assert mock_run.italic is True

    @pytest.mark.asyncio
    async def test_add_paragraph_underline(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()
        mock_run = MagicMock()
        mock_para = MagicMock()
        mock_para.runs = [mock_run]
        mock_doc.add_paragraph.return_value = mock_para

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ), patch(
            "portal.tools.document_processing.word_processor.WD_ALIGN_PARAGRAPH",
        ) as mock_align:
            mock_align.LEFT = 0
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_paragraph",
                "file_path": str(docx_file),
                "text": "Underlined",
                "style": "underline",
            })
            assert result["success"] is True
            assert mock_run.underline is True

    @pytest.mark.asyncio
    async def test_add_paragraph_center_alignment(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()
        mock_para = MagicMock()
        mock_run = MagicMock()
        mock_para.runs = [mock_run]
        mock_doc.add_paragraph.return_value = mock_para

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ), patch(
            "portal.tools.document_processing.word_processor.WD_ALIGN_PARAGRAPH",
        ) as mock_align:
            mock_align.LEFT = 0
            mock_align.CENTER = 1
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_paragraph",
                "file_path": str(docx_file),
                "text": "Centered",
                "alignment": "center",
            })
            assert result["success"] is True
            assert mock_para.alignment == 1

    @pytest.mark.asyncio
    async def test_add_paragraph_exception(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            side_effect=RuntimeError("bad"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_paragraph",
                "file_path": str(docx_file),
                "text": "test",
            })
            assert result["success"] is False
            assert "Add paragraph error" in result["error"]


# ---------------------------------------------------------------------------
# Add table
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAddTable:

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_table",
                "file_path": str(temp_dir / "nope.docx"),
                "table_data": {"rows": [["a"]]},
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_table_data(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_table",
                "file_path": str(docx_file),
            })
            assert result["success"] is False
            assert "Table data required" in result["error"]

    @pytest.mark.asyncio
    async def test_no_rows(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_table",
                "file_path": str(docx_file),
                "table_data": {"headers": ["A", "B"], "rows": []},
            })
            assert result["success"] is False
            assert "No table rows" in result["error"]

    @pytest.mark.asyncio
    async def test_add_table_with_headers(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()
        mock_table = MagicMock()
        # Two rows: header + 1 data row
        header_cell_a = MagicMock()
        header_cell_a.paragraphs = [MagicMock(runs=[MagicMock()])]
        header_cell_b = MagicMock()
        header_cell_b.paragraphs = [MagicMock(runs=[MagicMock()])]

        data_cell_a = MagicMock()
        data_cell_b = MagicMock()

        header_row = MagicMock()
        header_row.cells = [header_cell_a, header_cell_b]
        data_row = MagicMock()
        data_row.cells = [data_cell_a, data_cell_b]

        mock_table.rows = [header_row, data_row]
        mock_doc.add_table.return_value = mock_table

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_table",
                "file_path": str(docx_file),
                "table_data": {
                    "headers": ["Name", "Age"],
                    "rows": [["Alice", 30]],
                },
            })
            assert result["success"] is True
            assert result["result"]["table_added"] is True

    @pytest.mark.asyncio
    async def test_add_table_without_headers(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()
        data_cell = MagicMock()
        data_row = MagicMock()
        data_row.cells = [data_cell]
        mock_table = MagicMock()
        mock_table.rows = [data_row]
        mock_doc.add_table.return_value = mock_table

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_table",
                "file_path": str(docx_file),
                "table_data": {"rows": [["val"]]},
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_add_table_exception(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            side_effect=RuntimeError("nope"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_table",
                "file_path": str(docx_file),
                "table_data": {"rows": [["v"]]},
            })
            assert result["success"] is False
            assert "Add table error" in result["error"]


# ---------------------------------------------------------------------------
# Add image
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAddImage:

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_image",
                "file_path": str(temp_dir / "nope.docx"),
                "image_path": str(temp_dir / "img.png"),
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_image_not_found(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_image",
                "file_path": str(docx_file),
                "image_path": str(temp_dir / "no.png"),
            })
            assert result["success"] is False
            assert "Image not found" in result["error"]

    @pytest.mark.asyncio
    async def test_add_image_success(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")
        img_file = temp_dir / "img.png"
        img_file.write_bytes(b"PNG")

        mock_doc = MagicMock()

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ), patch(
            "portal.tools.document_processing.word_processor.Inches",
            side_effect=lambda v: int(v * 914400),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_image",
                "file_path": str(docx_file),
                "image_path": str(img_file),
                "image_width": 6,
            })
            assert result["success"] is True
            assert "image_added" in result["result"]
            mock_doc.add_picture.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_image_exception(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")
        img_file = temp_dir / "img.png"
        img_file.write_bytes(b"PNG")

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            side_effect=RuntimeError("bad"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_image",
                "file_path": str(docx_file),
                "image_path": str(img_file),
            })
            assert result["success"] is False
            assert "Add image error" in result["error"]


# ---------------------------------------------------------------------------
# Read document
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestReadDocument:

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(temp_dir / "nope.docx"),
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_read_success(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()
        mock_doc.core_properties.title = "My Title"
        mock_doc.core_properties.author = "Alice"
        mock_doc.core_properties.subject = "Report"
        mock_doc.core_properties.keywords = "test"

        mock_para = MagicMock()
        mock_para.text = "Hello world"
        mock_para.style.name = "Normal"
        mock_doc.paragraphs = [mock_para]

        mock_cell = MagicMock()
        mock_cell.text = "cell_val"
        mock_row = MagicMock()
        mock_row.cells = [mock_cell]
        mock_table = MagicMock()
        mock_table.rows = [mock_row]
        mock_doc.tables = [mock_table]

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(docx_file),
            })
            assert result["success"] is True
            content = result["result"]
            assert content["metadata"]["title"] == "My Title"
            assert len(content["paragraphs"]) == 1
            assert content["paragraphs"][0]["text"] == "Hello world"
            assert len(content["tables"]) == 1

    @pytest.mark.asyncio
    async def test_read_empty_paragraphs_filtered(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        mock_doc = MagicMock()
        mock_doc.core_properties.title = ""
        mock_doc.core_properties.author = ""
        mock_doc.core_properties.subject = ""
        mock_doc.core_properties.keywords = ""

        # Empty paragraph should be skipped
        empty_para = MagicMock()
        empty_para.text = "   "
        nonempty_para = MagicMock()
        nonempty_para.text = "Real text"
        nonempty_para.style.name = "Normal"
        mock_doc.paragraphs = [empty_para, nonempty_para]
        mock_doc.tables = []

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            return_value=mock_doc,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(docx_file),
            })
            assert result["success"] is True
            assert len(result["result"]["paragraphs"]) == 1

    @pytest.mark.asyncio
    async def test_read_exception(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ), patch(
            "portal.tools.document_processing.word_processor.Document",
            side_effect=RuntimeError("corrupt"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(docx_file),
            })
            assert result["success"] is False
            assert "Read error" in result["error"]


# ---------------------------------------------------------------------------
# Save document
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSaveDocument:

    @pytest.mark.asyncio
    async def test_save_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "save",
                "file_path": str(temp_dir / "nope.docx"),
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_save_success(self, temp_dir):
        docx_file = temp_dir / "doc.docx"
        docx_file.write_bytes(b"PK")

        with patch(
            "portal.tools.document_processing.word_processor.DOCX_AVAILABLE", True
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "save",
                "file_path": str(docx_file),
            })
            assert result["success"] is True
            assert "saved" in result["result"]
