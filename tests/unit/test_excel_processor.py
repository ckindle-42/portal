"""
Comprehensive tests for ExcelProcessorTool.

Covers: metadata, read, write, analyze, format, add_chart, unknown action,
        openpyxl-not-available fallback, cell formatting helper, and error
        handling for every path.
"""

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

from portal.core.interfaces.tool import ToolCategory

_has_openpyxl = importlib.util.find_spec("openpyxl") is not None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool():
    from portal.tools.document_processing.excel_processor import ExcelProcessorTool
    return ExcelProcessorTool()


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExcelProcessorMetadata:

    def test_metadata_name(self):
        tool = _make_tool()
        assert tool.metadata.name == "excel_processor"

    def test_metadata_category(self):
        tool = _make_tool()
        assert tool.metadata.category == ToolCategory.DATA

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
            "action", "file_path", "sheet_name", "data", "range",
            "headers", "formatting", "chart_type", "formulas",
        }
        assert expected == names


# ---------------------------------------------------------------------------
# openpyxl not available
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestOpenpyxlNotAvailable:

    @pytest.mark.asyncio
    async def test_returns_error_when_openpyxl_missing(self):
        """When the lazy import in execute() fails, the tool returns an error."""
        tool = _make_tool()

        with patch.dict("sys.modules", {"openpyxl": None}):
            # Force the lazy import inside execute() to raise ImportError
            with patch(
                "builtins.__import__",
                side_effect=_selective_import_error("openpyxl"),
            ):
                result = await tool.execute({
                    "action": "read",
                    "file_path": "/tmp/test.xlsx",
                })
                assert result["success"] is False
                assert "openpyxl" in result["error"]


def _selective_import_error(blocked_module):
    """Return a function that raises ImportError only for `blocked_module`."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    def _import(name, *args, **kwargs):
        if name == blocked_module:
            raise ImportError(f"No module named '{blocked_module}'")
        return real_import(name, *args, **kwargs)

    return _import


# ---------------------------------------------------------------------------
# Unknown action
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestExcelUnknownAction:

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        tool = _make_tool()
        result = await tool.execute({
            "action": "destroy",
            "file_path": "/tmp/test.xlsx",
        })
        assert result["success"] is False
        assert "Unknown action" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_action(self):
        tool = _make_tool()
        result = await tool.execute({"file_path": "/tmp/test.xlsx"})
        assert result["success"] is False
        assert "Unknown action" in result["error"]


# ---------------------------------------------------------------------------
# Read Excel
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestReadExcel:

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        tool = _make_tool()
        result = await tool.execute({
            "action": "read",
            "file_path": str(temp_dir / "nope.xlsx"),
        })
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_sheet_not_found(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Data"]

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(xlsx_file),
                "sheet_name": "Missing",
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_read_all_rows(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_cell1 = MagicMock(value="Name", data_type="s")
        mock_cell2 = MagicMock(value="Age", data_type="s")
        mock_ws = MagicMock()
        mock_ws.max_row = 1
        mock_ws.max_column = 2
        mock_ws.iter_rows.return_value = [[mock_cell1, mock_cell2]]

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(xlsx_file),
            })
            assert result["success"] is True
            assert "data" in result["result"]

    @pytest.mark.asyncio
    async def test_read_with_range(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_cell = MagicMock(value=42, data_type="n")
        mock_ws = MagicMock()
        mock_ws.max_row = 1
        mock_ws.max_column = 1
        mock_ws.__getitem__ = MagicMock(return_value=[[mock_cell]])
        mock_ws.iter_rows.return_value = [[mock_cell]]

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(xlsx_file),
                "range": "A1:A1",
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_read_exception(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        with patch("openpyxl.load_workbook", side_effect=RuntimeError("corrupt")):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(xlsx_file),
            })
            assert result["success"] is False
            assert "Read error" in result["error"]


# ---------------------------------------------------------------------------
# Write Excel
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestWriteExcel:

    @pytest.mark.asyncio
    async def test_no_data(self):
        tool = _make_tool()
        result = await tool.execute({
            "action": "write",
            "file_path": "/tmp/out.xlsx",
        })
        assert result["success"] is False
        assert "No data" in result["error"]

    @pytest.mark.asyncio
    async def test_write_list_data(self, temp_dir):
        mock_ws = MagicMock()
        mock_ws.columns = []
        mock_wb = MagicMock()
        mock_wb.active = mock_ws

        with patch("openpyxl.Workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "write",
                "file_path": str(temp_dir / "out.xlsx"),
                "data": [["Alice", 30], ["Bob", 25]],
            })
            assert result["success"] is True
            assert result["result"]["file_path"] == str(temp_dir / "out.xlsx")
            assert result["metadata"]["rows_written"] == 2

    @pytest.mark.asyncio
    async def test_write_with_headers(self, temp_dir):
        mock_ws = MagicMock()
        mock_ws.columns = []
        mock_wb = MagicMock()
        mock_wb.active = mock_ws

        with patch("openpyxl.Workbook", return_value=mock_wb), patch(
            "openpyxl.styles.Font"
        ), patch("openpyxl.styles.PatternFill"):
            tool = _make_tool()
            result = await tool.execute({
                "action": "write",
                "file_path": str(temp_dir / "out.xlsx"),
                "data": [["Alice", 30]],
                "headers": ["Name", "Age"],
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_write_dict_data(self, temp_dir):
        mock_ws = MagicMock()
        mock_ws.columns = []
        mock_wb = MagicMock()
        mock_wb.active = mock_ws

        with patch("openpyxl.Workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "write",
                "file_path": str(temp_dir / "out.xlsx"),
                "data": {"row1": ["Alice", 30], "row2": ["Bob", 25]},
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_write_with_formulas(self, temp_dir):
        mock_ws = MagicMock()
        mock_ws.columns = []
        mock_wb = MagicMock()
        mock_wb.active = mock_ws

        with patch("openpyxl.Workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "write",
                "file_path": str(temp_dir / "out.xlsx"),
                "data": [[1, 2]],
                "formulas": [{"cell": "C1", "formula": "=A1+B1"}],
            })
            assert result["success"] is True
            assert result["metadata"]["formulas_added"] == 1

    @pytest.mark.asyncio
    async def test_write_dict_rows(self, temp_dir):
        """When rows are dicts, their values are extracted."""
        mock_ws = MagicMock()
        mock_ws.columns = []
        mock_wb = MagicMock()
        mock_wb.active = mock_ws

        with patch("openpyxl.Workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "write",
                "file_path": str(temp_dir / "out.xlsx"),
                "data": [{"name": "Alice", "age": 30}],
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_write_exception(self, temp_dir):
        with patch("openpyxl.Workbook", side_effect=RuntimeError("bad")):
            tool = _make_tool()
            result = await tool.execute({
                "action": "write",
                "file_path": str(temp_dir / "out.xlsx"),
                "data": [[1]],
            })
            assert result["success"] is False
            assert "Write error" in result["error"]


# ---------------------------------------------------------------------------
# Analyze Excel
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestAnalyzeExcel:

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        tool = _make_tool()
        result = await tool.execute({
            "action": "analyze",
            "file_path": str(temp_dir / "nope.xlsx"),
        })
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_pandas_not_installed(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        with patch.dict("sys.modules", {"pandas": None}):
            with patch(
                "builtins.__import__",
                side_effect=_selective_import_error("pandas"),
            ):
                tool = _make_tool()
                result = await tool.execute({
                    "action": "analyze",
                    "file_path": str(xlsx_file),
                })
                assert result["success"] is False
                assert "pandas" in result["error"]

    @pytest.mark.asyncio
    async def test_analyze_success(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_df = MagicMock()
        mock_df.__len__ = lambda self: 5
        mock_df.columns = ["name", "value"]
        mock_df.dtypes.astype.return_value.to_dict.return_value = {
            "name": "object", "value": "float64"
        }
        mock_df.isnull.return_value.sum.return_value.to_dict.return_value = {
            "name": 0, "value": 1
        }

        # Numeric columns
        mock_numeric = MagicMock()
        mock_numeric.columns = ["value"]
        mock_df.select_dtypes.return_value = mock_numeric

        mock_df.__getitem__ = MagicMock()
        mock_col = MagicMock()
        mock_col.mean.return_value = 10.0
        mock_col.median.return_value = 9.0
        mock_col.std.return_value = 2.0
        mock_col.min.return_value = 5.0
        mock_col.max.return_value = 15.0
        mock_df.__getitem__.return_value = mock_col

        mock_df.head.return_value.to_dict.return_value = [
            {"name": "A", "value": 10}
        ]

        with patch("pandas.read_excel", return_value=mock_df):
            tool = _make_tool()
            result = await tool.execute({
                "action": "analyze",
                "file_path": str(xlsx_file),
            })
            assert result["success"] is True
            assert "shape" in result["result"]
            assert result["result"]["shape"]["rows"] == 5

    @pytest.mark.asyncio
    async def test_analyze_exception(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        with patch("pandas.read_excel", side_effect=RuntimeError("bad file")):
            tool = _make_tool()
            result = await tool.execute({
                "action": "analyze",
                "file_path": str(xlsx_file),
            })
            assert result["success"] is False
            assert "Analysis error" in result["error"]


# ---------------------------------------------------------------------------
# Format Excel
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestFormatExcel:

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        tool = _make_tool()
        result = await tool.execute({
            "action": "format",
            "file_path": str(temp_dir / "nope.xlsx"),
        })
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_sheet_not_found(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Data"]

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "format",
                "file_path": str(xlsx_file),
                "sheet_name": "Missing",
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_format_success(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_cell = MagicMock()
        mock_ws = MagicMock()
        mock_ws.__getitem__ = MagicMock(return_value=mock_cell)

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "format",
                "file_path": str(xlsx_file),
                "formatting": {"font": {"bold": True}},
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_format_range_of_cells(self, temp_dir):
        """When cell_range returns a tuple of tuples, each cell is formatted."""
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        cell_a = MagicMock()
        cell_b = MagicMock()
        mock_ws = MagicMock()
        # Return a tuple (indicating a range) so the isinstance(cell, tuple) branch fires
        mock_ws.__getitem__ = MagicMock(return_value=[(cell_a, cell_b)])

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "format",
                "file_path": str(xlsx_file),
                "range": "A1:B1",
                "formatting": {"fill": {"color": "FF0000"}},
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_format_exception(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        with patch("openpyxl.load_workbook", side_effect=RuntimeError("oops")):
            tool = _make_tool()
            result = await tool.execute({
                "action": "format",
                "file_path": str(xlsx_file),
                "formatting": {},
            })
            assert result["success"] is False
            assert "Formatting error" in result["error"]


# ---------------------------------------------------------------------------
# _apply_cell_formatting helper
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestApplyCellFormatting:

    def test_apply_font(self):
        tool = _make_tool()
        cell = MagicMock()

        with patch("openpyxl.styles.Font") as MockFont:
            tool._apply_cell_formatting(cell, {
                "font": {"name": "Arial", "size": 14, "bold": True, "italic": False, "color": "0000FF"},
            })
            MockFont.assert_called_once_with(
                name="Arial", size=14, bold=True, italic=False, color="0000FF"
            )

    def test_apply_fill(self):
        tool = _make_tool()
        cell = MagicMock()

        with patch("openpyxl.styles.PatternFill") as MockFill:
            tool._apply_cell_formatting(cell, {
                "fill": {"color": "FF0000"},
            })
            MockFill.assert_called_once_with(
                start_color="FF0000", end_color="FF0000", fill_type="solid"
            )

    def test_apply_alignment(self):
        tool = _make_tool()
        cell = MagicMock()

        with patch("openpyxl.styles.Alignment") as MockAlign:
            tool._apply_cell_formatting(cell, {
                "alignment": {"horizontal": "center", "vertical": "middle", "wrap": True},
            })
            MockAlign.assert_called_once_with(
                horizontal="center", vertical="middle", wrap_text=True
            )

    def test_apply_border(self):
        tool = _make_tool()
        cell = MagicMock()

        with patch("openpyxl.styles.Border") as MockBorder, \
             patch("openpyxl.styles.Side") as MockSide:
            tool._apply_cell_formatting(cell, {
                "border": {"style": "thick"},
            })
            assert MockSide.call_count == 4  # left, right, top, bottom
            MockBorder.assert_called_once()

    def test_apply_all_formatting_at_once(self):
        tool = _make_tool()
        cell = MagicMock()

        with patch("openpyxl.styles.Font"), \
             patch("openpyxl.styles.PatternFill"), \
             patch("openpyxl.styles.Alignment"), \
             patch("openpyxl.styles.Border"), \
             patch("openpyxl.styles.Side"):
            tool._apply_cell_formatting(cell, {
                "font": {"bold": True},
                "fill": {"color": "FF0000"},
                "alignment": {"horizontal": "center"},
                "border": {"style": "thin"},
            })
            # If no exception, all branches ran successfully
            assert True

    def test_no_formatting_keys(self):
        tool = _make_tool()
        cell = MagicMock()
        # Should not raise even with empty dict
        tool._apply_cell_formatting(cell, {})


# ---------------------------------------------------------------------------
# Add chart
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestAddChart:

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        tool = _make_tool()
        result = await tool.execute({
            "action": "add_chart",
            "file_path": str(temp_dir / "nope.xlsx"),
        })
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_sheet_not_found(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Data"]

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(xlsx_file),
                "sheet_name": "Missing",
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_add_bar_chart(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_ws = MagicMock()
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)

        with patch("openpyxl.load_workbook", return_value=mock_wb), \
             patch("openpyxl.chart.BarChart"), \
             patch("openpyxl.chart.Reference"):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(xlsx_file),
                "chart_type": "bar",
                "range": "A1:B5",
            })
            assert result["success"] is True
            assert result["result"]["chart_added"] == "bar"

    @pytest.mark.asyncio
    async def test_add_line_chart(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_ws = MagicMock()
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)

        with patch("openpyxl.load_workbook", return_value=mock_wb), \
             patch("openpyxl.chart.LineChart"), \
             patch("openpyxl.chart.Reference"):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(xlsx_file),
                "chart_type": "line",
            })
            assert result["success"] is True
            assert result["result"]["chart_added"] == "line"

    @pytest.mark.asyncio
    async def test_add_pie_chart(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_ws = MagicMock()
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)

        with patch("openpyxl.load_workbook", return_value=mock_wb), \
             patch("openpyxl.chart.PieChart"), \
             patch("openpyxl.chart.Reference"):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(xlsx_file),
                "chart_type": "pie",
            })
            assert result["success"] is True
            assert result["result"]["chart_added"] == "pie"

    @pytest.mark.asyncio
    async def test_unknown_chart_type(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        mock_ws = MagicMock()
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(xlsx_file),
                "chart_type": "radar",
            })
            assert result["success"] is False
            assert "Unknown chart type" in result["error"]

    @pytest.mark.asyncio
    async def test_add_chart_exception(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")

        with patch("openpyxl.load_workbook", side_effect=RuntimeError("oops")):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(xlsx_file),
            })
            assert result["success"] is False
            assert "Chart error" in result["error"]
