"""Tests for ExcelProcessorTool."""

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

from portal.core.interfaces.tool import ToolCategory

_has_openpyxl = importlib.util.find_spec("openpyxl") is not None


def _make_tool():
    from portal.tools.document_processing.excel_processor import ExcelProcessorTool
    return ExcelProcessorTool()


def _selective_import_error(blocked_module):
    real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
    def _import(name, *args, **kwargs):
        if name == blocked_module:
            raise ImportError(f"No module named '{blocked_module}'")
        return real_import(name, *args, **kwargs)
    return _import


@pytest.mark.unit
class TestExcelProcessorMetadata:
    def test_metadata(self):
        meta = _make_tool().metadata
        assert meta.name == "excel_processor"
        assert meta.category == ToolCategory.DATA
        assert meta.version == "1.0.0"
        names = {p.name for p in meta.parameters}
        assert {"action", "file_path", "chart_type"} <= names
        assert next(p for p in meta.parameters if p.name == "action").required is True


@pytest.mark.unit
class TestOpenpyxlNotAvailable:
    @pytest.mark.asyncio
    async def test_returns_error_when_openpyxl_missing(self):
        with patch.dict("sys.modules", {"openpyxl": None}):
            with patch("builtins.__import__", side_effect=_selective_import_error("openpyxl")):
                result = await _make_tool().execute({"action": "read", "file_path": "/tmp/test.xlsx"})
        assert result["success"] is False
        assert "openpyxl" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestExcelUnknownAction:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", ["destroy", ""])
    async def test_unknown_action(self, action):
        result = await _make_tool().execute({"action": action, "file_path": "/tmp/test.xlsx"})
        assert result["success"] is False
        assert "Unknown action" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestReadExcel:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        result = await _make_tool().execute({"action": "read", "file_path": str(temp_dir / "nope.xlsx")})
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_sheet_not_found(self, temp_dir):
        (temp_dir / "test.xlsx").write_bytes(b"PK")
        mock_wb = MagicMock(sheetnames=["Data"])
        with patch("openpyxl.load_workbook", return_value=mock_wb):
            result = await _make_tool().execute(
                {"action": "read", "file_path": str(temp_dir / "test.xlsx"), "sheet_name": "Missing"})
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_read_all_rows(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")
        mock_ws = MagicMock(max_row=1, max_column=2)
        mock_ws.iter_rows.return_value = [[MagicMock(value="Name", data_type="s"),
                                            MagicMock(value="Age", data_type="s")]]
        mock_wb = MagicMock(sheetnames=["Sheet1"])
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)
        with patch("openpyxl.load_workbook", return_value=mock_wb):
            result = await _make_tool().execute({"action": "read", "file_path": str(xlsx_file)})
        assert result["success"] is True
        assert "data" in result["result"]

    @pytest.mark.asyncio
    async def test_read_exception(self, temp_dir):
        (temp_dir / "test.xlsx").write_bytes(b"PK")
        with patch("openpyxl.load_workbook", side_effect=RuntimeError("corrupt")):
            result = await _make_tool().execute({"action": "read", "file_path": str(temp_dir / "test.xlsx")})
        assert result["success"] is False
        assert "Read error" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestWriteExcel:
    @pytest.mark.asyncio
    async def test_no_data(self):
        result = await _make_tool().execute({"action": "write", "file_path": "/tmp/out.xlsx"})
        assert result["success"] is False
        assert "No data" in result["error"]

    @pytest.mark.asyncio
    async def test_write_list_data(self, temp_dir):
        mock_ws = MagicMock(columns=[])
        mock_wb = MagicMock(active=mock_ws)
        with patch("openpyxl.Workbook", return_value=mock_wb):
            result = await _make_tool().execute({
                "action": "write", "file_path": str(temp_dir / "out.xlsx"),
                "data": [["Alice", 30], ["Bob", 25]],
            })
        assert result["success"] is True
        assert result["metadata"]["rows_written"] == 2

    @pytest.mark.asyncio
    async def test_write_with_headers(self, temp_dir):
        mock_ws = MagicMock(columns=[])
        mock_wb = MagicMock(active=mock_ws)
        with patch("openpyxl.Workbook", return_value=mock_wb), \
             patch("openpyxl.styles.Font"), patch("openpyxl.styles.PatternFill"):
            result = await _make_tool().execute({
                "action": "write", "file_path": str(temp_dir / "out.xlsx"),
                "data": [["Alice", 30]], "headers": ["Name", "Age"],
            })
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_write_with_formulas(self, temp_dir):
        mock_ws = MagicMock(columns=[])
        mock_wb = MagicMock(active=mock_ws)
        with patch("openpyxl.Workbook", return_value=mock_wb):
            result = await _make_tool().execute({
                "action": "write", "file_path": str(temp_dir / "out.xlsx"),
                "data": [[1, 2]], "formulas": [{"cell": "C1", "formula": "=A1+B1"}],
            })
        assert result["success"] is True
        assert result["metadata"]["formulas_added"] == 1

    @pytest.mark.asyncio
    async def test_write_exception(self, temp_dir):
        with patch("openpyxl.Workbook", side_effect=RuntimeError("bad")):
            result = await _make_tool().execute({
                "action": "write", "file_path": str(temp_dir / "out.xlsx"), "data": [[1]]})
        assert result["success"] is False
        assert "Write error" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestAnalyzeExcel:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        result = await _make_tool().execute({"action": "analyze", "file_path": str(temp_dir / "nope.xlsx")})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_analyze_success(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")
        mock_df = MagicMock()
        mock_df.__len__ = lambda self: 5
        mock_df.columns = ["name", "value"]
        mock_df.dtypes.astype.return_value.to_dict.return_value = {"name": "object", "value": "float64"}
        mock_df.isnull.return_value.sum.return_value.to_dict.return_value = {"name": 0, "value": 1}
        mock_numeric = MagicMock(columns=["value"])
        mock_df.select_dtypes.return_value = mock_numeric
        mock_col = MagicMock()
        mock_col.mean.return_value = 10.0
        mock_col.median.return_value = 9.0
        mock_col.std.return_value = 2.0
        mock_col.min.return_value = 5.0
        mock_col.max.return_value = 15.0
        mock_df.__getitem__ = MagicMock(return_value=mock_col)
        mock_df.head.return_value.to_dict.return_value = [{"name": "A", "value": 10}]
        with patch("pandas.read_excel", return_value=mock_df):
            result = await _make_tool().execute({"action": "analyze", "file_path": str(xlsx_file)})
        assert result["success"] is True
        assert result["result"]["shape"]["rows"] == 5

    @pytest.mark.asyncio
    async def test_analyze_exception(self, temp_dir):
        (temp_dir / "test.xlsx").write_bytes(b"PK")
        with patch("pandas.read_excel", side_effect=RuntimeError("bad file")):
            result = await _make_tool().execute({"action": "analyze", "file_path": str(temp_dir / "test.xlsx")})
        assert result["success"] is False
        assert "Analysis error" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestFormatExcel:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        result = await _make_tool().execute({"action": "format", "file_path": str(temp_dir / "nope.xlsx")})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_sheet_not_found(self, temp_dir):
        (temp_dir / "test.xlsx").write_bytes(b"PK")
        mock_wb = MagicMock(sheetnames=["Data"])
        with patch("openpyxl.load_workbook", return_value=mock_wb):
            result = await _make_tool().execute({
                "action": "format", "file_path": str(temp_dir / "test.xlsx"), "sheet_name": "Missing"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_format_success(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")
        mock_cell = MagicMock()
        mock_ws = MagicMock()
        mock_ws.__getitem__ = MagicMock(return_value=mock_cell)
        mock_wb = MagicMock(sheetnames=["Sheet1"])
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)
        with patch("openpyxl.load_workbook", return_value=mock_wb):
            result = await _make_tool().execute({
                "action": "format", "file_path": str(xlsx_file), "formatting": {"font": {"bold": True}}})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_format_exception(self, temp_dir):
        (temp_dir / "test.xlsx").write_bytes(b"PK")
        with patch("openpyxl.load_workbook", side_effect=RuntimeError("oops")):
            result = await _make_tool().execute({
                "action": "format", "file_path": str(temp_dir / "test.xlsx"), "formatting": {}})
        assert result["success"] is False
        assert "Formatting error" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_openpyxl, reason="openpyxl not installed")
class TestAddChart:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        result = await _make_tool().execute({"action": "add_chart", "file_path": str(temp_dir / "nope.xlsx")})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_sheet_not_found(self, temp_dir):
        (temp_dir / "test.xlsx").write_bytes(b"PK")
        mock_wb = MagicMock(sheetnames=["Data"])
        with patch("openpyxl.load_workbook", return_value=mock_wb):
            result = await _make_tool().execute({
                "action": "add_chart", "file_path": str(temp_dir / "test.xlsx"), "sheet_name": "Missing"})
        assert result["success"] is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("chart_type,chart_class", [
        ("bar", "BarChart"), ("line", "LineChart"), ("pie", "PieChart"),
    ])
    async def test_add_chart_types(self, temp_dir, chart_type, chart_class):
        xlsx_file = temp_dir / f"test_{chart_type}.xlsx"
        xlsx_file.write_bytes(b"PK")
        mock_ws = MagicMock()
        mock_wb = MagicMock(sheetnames=["Sheet1"])
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)
        with patch("openpyxl.load_workbook", return_value=mock_wb), \
             patch(f"openpyxl.chart.{chart_class}"), patch("openpyxl.chart.Reference"):
            result = await _make_tool().execute({
                "action": "add_chart", "file_path": str(xlsx_file), "chart_type": chart_type})
        assert result["success"] is True
        assert result["result"]["chart_added"] == chart_type

    @pytest.mark.asyncio
    async def test_unknown_chart_type(self, temp_dir):
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.write_bytes(b"PK")
        mock_ws = MagicMock()
        mock_wb = MagicMock(sheetnames=["Sheet1"])
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)
        with patch("openpyxl.load_workbook", return_value=mock_wb):
            result = await _make_tool().execute(
                {"action": "add_chart", "file_path": str(xlsx_file), "chart_type": "radar"})
        assert result["success"] is False
        assert "Unknown chart type" in result["error"]

    @pytest.mark.asyncio
    async def test_add_chart_exception(self, temp_dir):
        (temp_dir / "test.xlsx").write_bytes(b"PK")
        with patch("openpyxl.load_workbook", side_effect=RuntimeError("oops")):
            result = await _make_tool().execute(
                {"action": "add_chart", "file_path": str(temp_dir / "test.xlsx")})
        assert result["success"] is False
        assert "Chart error" in result["error"]
