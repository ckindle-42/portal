"""Tests for PowerPointProcessorTool."""

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

from portal.core.interfaces.tool import ToolCategory

_has_pptx = importlib.util.find_spec("pptx") is not None
_P = "portal.tools.document_processing.powerpoint_processor"


def _make_tool():
    from portal.tools.document_processing.powerpoint_processor import PowerPointProcessorTool

    return PowerPointProcessorTool()


def _pptx_patches(available=True, prs=None, prs_exc=None):
    """Return a list of patches for PPTX_AVAILABLE and optionally Presentation."""
    result = [patch(f"{_P}.PPTX_AVAILABLE", available)]
    if prs_exc:
        result.append(patch(f"{_P}.Presentation", side_effect=prs_exc))
    elif prs is not None:
        result.append(patch(f"{_P}.Presentation", return_value=prs))
    return result


@pytest.mark.unit
class TestPowerPointProcessorMetadata:
    def test_metadata(self):
        from portal.tools.document_processing.powerpoint_processor import PowerPointProcessorTool

        meta = _make_tool().metadata
        assert meta.name == "powerpoint_processor"
        assert meta.category == ToolCategory.UTILITY
        assert meta.version == "1.0.0"
        assert {"action", "file_path", "chart_data", "chart_type"} <= {
            p.name for p in meta.parameters
        }
        assert "title" in PowerPointProcessorTool.LAYOUTS
        assert "blank" in PowerPointProcessorTool.LAYOUTS


@pytest.mark.unit
class TestPptxNotAvailable:
    @pytest.mark.asyncio
    async def test_returns_error(self):
        with patch(f"{_P}.PPTX_AVAILABLE", False):
            result = await _make_tool().execute({"action": "create", "file_path": "/tmp/x.pptx"})
        assert result["success"] is False
        assert "python-pptx" in result["error"]


@pytest.mark.unit
class TestPowerPointUnknownAction:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", ["destroy", ""])
    async def test_unknown_action(self, action):
        with patch(f"{_P}.PPTX_AVAILABLE", True):
            result = await _make_tool().execute({"action": action, "file_path": "/tmp/x.pptx"})
        assert result["success"] is False
        assert "Unknown action" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_pptx, reason="python-pptx not installed")
class TestCreatePresentation:
    def _mock_prs(self, num_placeholders=2):
        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slide_layouts.__getitem__ = MagicMock(return_value=MagicMock())
        mock_prs.slides.add_slide.return_value = mock_slide
        mock_slide.shapes.title.text = ""
        mock_slide.placeholders.__len__ = lambda self: num_placeholders
        mock_slide.placeholders.__getitem__ = MagicMock(return_value=MagicMock())
        return mock_prs

    @pytest.mark.asyncio
    async def test_create_success(self, temp_dir):
        mock_prs = self._mock_prs()
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", return_value=mock_prs),
        ):
            result = await _make_tool().execute(
                {
                    "action": "create",
                    "file_path": str(temp_dir / "out.pptx"),
                    "title": "My Deck",
                    "content": "Subtitle",
                }
            )
        assert result["success"] is True
        assert result["result"]["slides"] == 1
        mock_prs.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_without_subtitle(self, temp_dir):
        mock_prs = self._mock_prs(num_placeholders=1)
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", return_value=mock_prs),
        ):
            result = await _make_tool().execute(
                {
                    "action": "create",
                    "file_path": str(temp_dir / "no_sub.pptx"),
                    "title": "Title Only",
                }
            )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_exception(self, temp_dir):
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", side_effect=OSError("disk full")),
        ):
            result = await _make_tool().execute(
                {"action": "create", "file_path": str(temp_dir / "fail.pptx")}
            )
        assert result["success"] is False
        assert "Creation error" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_pptx, reason="python-pptx not installed")
class TestAddSlide:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(f"{_P}.PPTX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "add_slide", "file_path": str(temp_dir / "nope.pptx"), "title": "Slide"}
            )
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_add_slide_success(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slide_layouts.__getitem__ = MagicMock(return_value=MagicMock())
        mock_prs.slides.add_slide.return_value = mock_slide
        mock_prs.slides.__len__ = lambda self: 2
        body_ph = MagicMock()
        body_ph.placeholder_format.type = 2
        mock_slide.placeholders = [body_ph]
        mock_slide.shapes.title = MagicMock()
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", return_value=mock_prs),
        ):
            result = await _make_tool().execute(
                {
                    "action": "add_slide",
                    "file_path": str(pptx_file),
                    "title": "Points",
                    "bullet_points": ["A", "B"],
                }
            )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_add_slide_exception(self, temp_dir):
        (temp_dir / "test.pptx").write_bytes(b"placeholder")
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", side_effect=ValueError("bad")),
        ):
            result = await _make_tool().execute(
                {"action": "add_slide", "file_path": str(temp_dir / "test.pptx")}
            )
        assert result["success"] is False
        assert "Add slide error" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_pptx, reason="python-pptx not installed")
class TestAddImage:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(f"{_P}.PPTX_AVAILABLE", True):
            result = await _make_tool().execute(
                {
                    "action": "add_image",
                    "file_path": str(temp_dir / "no.pptx"),
                    "image_path": str(temp_dir / "img.png"),
                }
            )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_image_not_found(self, temp_dir):
        (temp_dir / "test.pptx").write_bytes(b"placeholder")
        with patch(f"{_P}.PPTX_AVAILABLE", True):
            result = await _make_tool().execute(
                {
                    "action": "add_image",
                    "file_path": str(temp_dir / "test.pptx"),
                    "image_path": str(temp_dir / "nope.png"),
                }
            )
        assert result["success"] is False
        assert "Image not found" in result["error"]

    @pytest.mark.asyncio
    async def test_add_image_success(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        img_file = temp_dir / "img.png"
        img_file.write_bytes(b"PNG")
        mock_prs = MagicMock()
        mock_prs.slides.__len__ = lambda self: 1
        mock_prs.slides.__getitem__ = MagicMock(return_value=MagicMock())
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", return_value=mock_prs),
            patch(f"{_P}.Inches", side_effect=lambda v: int(v * 914400)),
        ):
            result = await _make_tool().execute(
                {"action": "add_image", "file_path": str(pptx_file), "image_path": str(img_file)}
            )
        assert result["success"] is True
        assert "image_added" in result["result"]

    @pytest.mark.asyncio
    async def test_slide_index_out_of_range(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        img_file = temp_dir / "img.png"
        img_file.write_bytes(b"PNG")
        mock_prs = MagicMock()
        mock_prs.slides.__len__ = lambda self: 1
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", return_value=mock_prs),
            patch(f"{_P}.Inches", side_effect=lambda v: int(v * 914400)),
        ):
            result = await _make_tool().execute(
                {
                    "action": "add_image",
                    "file_path": str(pptx_file),
                    "image_path": str(img_file),
                    "slide_index": 99,
                }
            )
        assert result["success"] is False
        assert "out of range" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_pptx, reason="python-pptx not installed")
class TestAddChart:
    _chart_data = {"categories": ["Q1", "Q2"], "series": [{"name": "Rev", "values": [100, 200]}]}

    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(f"{_P}.PPTX_AVAILABLE", True):
            result = await _make_tool().execute(
                {
                    "action": "add_chart",
                    "file_path": str(temp_dir / "no.pptx"),
                    "chart_data": self._chart_data,
                }
            )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_no_data(self, temp_dir):
        (temp_dir / "test.pptx").write_bytes(b"placeholder")
        with patch(f"{_P}.PPTX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "add_chart", "file_path": str(temp_dir / "test.pptx")}
            )
        assert result["success"] is False
        assert "No chart data" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("chart_type", ["bar", "line", "pie"])
    async def test_add_chart_types(self, temp_dir, chart_type):
        pptx_file = temp_dir / f"test_{chart_type}.pptx"
        pptx_file.write_bytes(b"placeholder")
        mock_prs = MagicMock()
        mock_prs.slides.__len__ = lambda self: 1
        mock_prs.slides.__getitem__ = MagicMock(return_value=MagicMock())
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", return_value=mock_prs),
            patch(f"{_P}.CategoryChartData", return_value=MagicMock()),
            patch(f"{_P}.Inches", side_effect=lambda v: int(v * 914400)),
            patch(f"{_P}.XL_CHART_TYPE") as mock_ct,
        ):
            mock_ct.COLUMN_CLUSTERED = 1
            mock_ct.LINE = 2
            mock_ct.PIE = 3
            result = await _make_tool().execute(
                {
                    "action": "add_chart",
                    "file_path": str(pptx_file),
                    "chart_type": chart_type,
                    "chart_data": self._chart_data,
                }
            )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_unknown_chart_type(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        mock_prs = MagicMock()
        mock_prs.slides.__getitem__ = MagicMock(return_value=MagicMock())
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", return_value=mock_prs),
            patch(f"{_P}.CategoryChartData", return_value=MagicMock()),
            patch(f"{_P}.Inches", side_effect=lambda v: int(v * 914400)),
        ):
            result = await _make_tool().execute(
                {
                    "action": "add_chart",
                    "file_path": str(pptx_file),
                    "chart_type": "radar",
                    "chart_data": {"categories": ["A"], "series": [{"name": "s", "values": [1]}]},
                }
            )
        assert result["success"] is False
        assert "Unknown chart type" in result["error"]


@pytest.mark.unit
@pytest.mark.skipif(not _has_pptx, reason="python-pptx not installed")
class TestReadPresentation:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(f"{_P}.PPTX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "read", "file_path": str(temp_dir / "no.pptx")}
            )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_read_success(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        title_shape = MagicMock(text="Title Text")
        body_shape = MagicMock(text="Body content")
        mock_slide = MagicMock()
        mock_slide.shapes.title = title_shape
        mock_slide.shapes.__iter__ = lambda self: iter([title_shape, body_shape])
        mock_slide.has_notes_slide = True
        mock_slide.notes_slide.notes_text_frame.text = "Speaker notes"
        mock_prs = MagicMock()
        mock_prs.slides.__iter__ = MagicMock(return_value=iter([mock_slide]))
        mock_prs.slides.__len__ = MagicMock(return_value=1)
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", return_value=mock_prs),
        ):
            result = await _make_tool().execute({"action": "read", "file_path": str(pptx_file)})
        assert result["success"] is True
        assert result["result"]["slides"][0]["title"] == "Title Text"
        assert result["result"]["slides"][0]["notes"] == "Speaker notes"

    @pytest.mark.asyncio
    async def test_slide_without_notes(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        mock_slide = MagicMock()
        mock_slide.shapes.title = None
        mock_slide.shapes.__iter__ = lambda self: iter([])
        mock_slide.has_notes_slide = False
        mock_prs = MagicMock()
        mock_prs.slides.__iter__ = MagicMock(return_value=iter([mock_slide]))
        mock_prs.slides.__len__ = MagicMock(return_value=1)
        with (
            patch(f"{_P}.PPTX_AVAILABLE", True),
            patch(f"{_P}.Presentation", return_value=mock_prs),
        ):
            result = await _make_tool().execute({"action": "read", "file_path": str(pptx_file)})
        assert result["success"] is True
        assert result["result"]["slides"][0]["notes"] == ""


@pytest.mark.unit
class TestSavePresentation:
    @pytest.mark.asyncio
    async def test_file_not_found(self, temp_dir):
        with patch(f"{_P}.PPTX_AVAILABLE", True):
            result = await _make_tool().execute(
                {"action": "save", "file_path": str(temp_dir / "no.pptx")}
            )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_save_success(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        with patch(f"{_P}.PPTX_AVAILABLE", True):
            result = await _make_tool().execute({"action": "save", "file_path": str(pptx_file)})
        assert result["success"] is True
        assert "saved" in result["result"]
