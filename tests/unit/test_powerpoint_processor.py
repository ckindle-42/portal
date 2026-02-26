"""
Comprehensive tests for PowerPointProcessorTool.

Covers: metadata, create, add_slide, add_image, add_chart, read, save,
        unknown action, pptx-not-available fallback, and error handling.
"""

import importlib.util
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from portal.core.interfaces.tool import ToolCategory

_has_pptx = importlib.util.find_spec("pptx") is not None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool():
    """Instantiate PowerPointProcessorTool (pptx may or may not be installed)."""
    from portal.tools.document_processing.powerpoint_processor import (
        PowerPointProcessorTool,
    )
    return PowerPointProcessorTool()


def _mock_pptx_module():
    """Return a fake `pptx` package suitable for sys.modules patching."""
    pptx = ModuleType("pptx")
    pptx_util = ModuleType("pptx.util")
    pptx_chart = ModuleType("pptx.chart")
    pptx_chart_data = ModuleType("pptx.chart.data")
    pptx_enum = ModuleType("pptx.enum")
    pptx_enum_chart = ModuleType("pptx.enum.chart")

    pptx_util.Inches = lambda v: int(v * 914400)

    class FakeCategoryChartData:
        categories = []
        def add_series(self, name, values):
            pass

    pptx_chart_data.CategoryChartData = FakeCategoryChartData

    class FakeChartTypes:
        COLUMN_CLUSTERED = 1
        LINE = 2
        PIE = 3

    pptx_enum_chart.XL_CHART_TYPE = FakeChartTypes

    # Presentation mock is set per-test so leave as a basic callable
    pptx.Presentation = MagicMock

    return {
        "pptx": pptx,
        "pptx.util": pptx_util,
        "pptx.chart": pptx_chart,
        "pptx.chart.data": pptx_chart_data,
        "pptx.enum": pptx_enum,
        "pptx.enum.chart": pptx_enum_chart,
    }


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPowerPointProcessorMetadata:

    def test_metadata_name_and_category(self):
        tool = _make_tool()
        meta = tool.metadata
        assert meta.name == "powerpoint_processor"
        assert meta.category == ToolCategory.UTILITY

    def test_metadata_version(self):
        tool = _make_tool()
        assert tool.metadata.version == "1.0.0"

    def test_metadata_has_required_action_parameter(self):
        tool = _make_tool()
        action_param = next(
            (p for p in tool.metadata.parameters if p.name == "action"), None
        )
        assert action_param is not None
        assert action_param.required is True

    def test_metadata_has_file_path_parameter(self):
        tool = _make_tool()
        fp = next(
            (p for p in tool.metadata.parameters if p.name == "file_path"), None
        )
        assert fp is not None
        assert fp.required is True

    def test_metadata_parameters_count(self):
        """All documented parameters are declared."""
        tool = _make_tool()
        names = {p.name for p in tool.metadata.parameters}
        expected = {
            "action", "file_path", "layout", "title", "content",
            "bullet_points", "image_path", "image_position",
            "chart_data", "chart_type", "theme",
        }
        assert expected == names

    def test_layouts_dict(self):
        from portal.tools.document_processing.powerpoint_processor import (
            PowerPointProcessorTool,
        )
        assert "title" in PowerPointProcessorTool.LAYOUTS
        assert "blank" in PowerPointProcessorTool.LAYOUTS


# ---------------------------------------------------------------------------
# PPTX not available
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPptxNotAvailable:

    @pytest.mark.asyncio
    async def test_execute_returns_error_when_pptx_missing(self):
        """When PPTX_AVAILABLE is False the tool should return an error."""
        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            False,
        ):
            tool = _make_tool()
            result = await tool.execute({"action": "create", "file_path": "/tmp/x.pptx"})
            assert result["success"] is False
            assert "python-pptx" in result["error"]


# ---------------------------------------------------------------------------
# Unknown action
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPowerPointUnknownAction:

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({"action": "destroy", "file_path": "/tmp/x.pptx"})
            assert result["success"] is False
            assert "Unknown action" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_action(self):
        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({"file_path": "/tmp/x.pptx"})
            assert result["success"] is False
            assert "Unknown action" in result["error"]


# ---------------------------------------------------------------------------
# Create presentation
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_pptx, reason="python-pptx not installed")
class TestCreatePresentation:

    @pytest.mark.asyncio
    async def test_create_success(self, temp_dir):
        """Create a new presentation with title and subtitle."""
        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slide_layouts.__getitem__ = MagicMock(return_value=MagicMock())
        mock_prs.slides.add_slide.return_value = mock_slide
        mock_slide.shapes.title.text = ""
        mock_slide.placeholders.__len__ = lambda self: 2
        mock_slide.placeholders.__getitem__ = MagicMock(return_value=MagicMock())

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ):
            tool = _make_tool()
            out_path = temp_dir / "out.pptx"
            result = await tool.execute({
                "action": "create",
                "file_path": str(out_path),
                "title": "My Deck",
                "content": "Subtitle here",
            })

            assert result["success"] is True
            assert result["result"]["slides"] == 1
            mock_prs.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_without_subtitle(self, temp_dir):
        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slide_layouts.__getitem__ = MagicMock(return_value=MagicMock())
        mock_prs.slides.add_slide.return_value = mock_slide
        mock_slide.shapes.title.text = ""
        mock_slide.placeholders.__len__ = lambda self: 1  # No subtitle placeholder

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "create",
                "file_path": str(temp_dir / "no_sub.pptx"),
                "title": "Title Only",
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_handles_exception(self, temp_dir):
        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            side_effect=OSError("disk full"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "create",
                "file_path": str(temp_dir / "fail.pptx"),
            })
            assert result["success"] is False
            assert "Creation error" in result["error"]


# ---------------------------------------------------------------------------
# Add slide
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_pptx, reason="python-pptx not installed")
class TestAddSlide:

    @pytest.mark.asyncio
    async def test_add_slide_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_slide",
                "file_path": str(temp_dir / "nonexistent.pptx"),
                "title": "Slide 2",
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_add_slide_with_bullet_points(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slide_layouts.__getitem__ = MagicMock(return_value=MagicMock())
        mock_prs.slides.add_slide.return_value = mock_slide
        mock_prs.slides.__len__ = lambda self: 2

        # Simulate a body placeholder
        body_ph = MagicMock()
        body_ph.placeholder_format.type = 2
        body_ph.text_frame = MagicMock()
        mock_slide.placeholders = [body_ph]
        mock_slide.shapes.title = MagicMock()

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_slide",
                "file_path": str(pptx_file),
                "title": "Points",
                "bullet_points": ["A", "B", "C"],
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_add_slide_with_content_text(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slide_layouts.__getitem__ = MagicMock(return_value=MagicMock())
        mock_prs.slides.add_slide.return_value = mock_slide
        mock_prs.slides.__len__ = lambda self: 2

        body_ph = MagicMock()
        body_ph.placeholder_format.type = 2
        body_ph.text_frame = MagicMock()
        mock_slide.placeholders = [body_ph]
        mock_slide.shapes.title = MagicMock()

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_slide",
                "file_path": str(pptx_file),
                "title": "Text Slide",
                "content": "Some paragraph text",
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_add_slide_exception(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            side_effect=ValueError("bad file"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_slide",
                "file_path": str(pptx_file),
            })
            assert result["success"] is False
            assert "Add slide error" in result["error"]


# ---------------------------------------------------------------------------
# Add image
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_pptx, reason="python-pptx not installed")
class TestAddImage:

    @pytest.mark.asyncio
    async def test_add_image_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_image",
                "file_path": str(temp_dir / "no.pptx"),
                "image_path": str(temp_dir / "img.png"),
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_add_image_missing_image(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_image",
                "file_path": str(pptx_file),
                "image_path": str(temp_dir / "nope.png"),
            })
            assert result["success"] is False
            assert "Image not found" in result["error"]

    @pytest.mark.asyncio
    async def test_add_image_success_last_slide(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        img_file = temp_dir / "img.png"
        img_file.write_bytes(b"PNG")

        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slides.__getitem__ = MagicMock(return_value=mock_slide)
        mock_prs.slides.__len__ = lambda self: 1

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Inches",
            side_effect=lambda v: int(v * 914400),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_image",
                "file_path": str(pptx_file),
                "image_path": str(img_file),
            })
            assert result["success"] is True
            assert "image_added" in result["result"]

    @pytest.mark.asyncio
    async def test_add_image_explicit_slide_index(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        img_file = temp_dir / "img.png"
        img_file.write_bytes(b"PNG")

        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slides.__getitem__ = MagicMock(return_value=mock_slide)
        mock_prs.slides.__len__ = lambda self: 3

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Inches",
            side_effect=lambda v: int(v * 914400),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_image",
                "file_path": str(pptx_file),
                "image_path": str(img_file),
                "slide_index": 1,
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_add_image_slide_index_out_of_range(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        img_file = temp_dir / "img.png"
        img_file.write_bytes(b"PNG")

        mock_prs = MagicMock()
        mock_prs.slides.__len__ = lambda self: 1

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Inches",
            side_effect=lambda v: int(v * 914400),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_image",
                "file_path": str(pptx_file),
                "image_path": str(img_file),
                "slide_index": 99,
            })
            assert result["success"] is False
            assert "out of range" in result["error"]

    @pytest.mark.asyncio
    async def test_add_image_exception(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")
        img_file = temp_dir / "img.png"
        img_file.write_bytes(b"PNG")

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            side_effect=RuntimeError("oops"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_image",
                "file_path": str(pptx_file),
                "image_path": str(img_file),
            })
            assert result["success"] is False
            assert "Add image error" in result["error"]


# ---------------------------------------------------------------------------
# Add chart
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_pptx, reason="python-pptx not installed")
class TestAddChart:

    @pytest.mark.asyncio
    async def test_add_chart_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(temp_dir / "no.pptx"),
                "chart_data": {"categories": ["A"], "series": [{"name": "s", "values": [1]}]},
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_add_chart_no_data(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(pptx_file),
            })
            assert result["success"] is False
            assert "No chart data" in result["error"]

    @pytest.mark.asyncio
    async def test_add_chart_bar_success(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slides.__getitem__ = MagicMock(return_value=mock_slide)
        mock_prs.slides.__len__ = lambda self: 1

        mock_chart_data_cls = MagicMock()

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.CategoryChartData",
            return_value=mock_chart_data_cls,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Inches",
            side_effect=lambda v: int(v * 914400),
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.XL_CHART_TYPE",
        ) as mock_chart_type:
            mock_chart_type.COLUMN_CLUSTERED = 1
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(pptx_file),
                "chart_type": "bar",
                "chart_data": {
                    "categories": ["Q1", "Q2"],
                    "series": [{"name": "Rev", "values": [100, 200]}],
                },
            })
            assert result["success"] is True
            assert result["result"]["chart_added"] == "bar"

    @pytest.mark.asyncio
    async def test_add_chart_line_type(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slides.__getitem__ = MagicMock(return_value=mock_slide)

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.CategoryChartData",
            return_value=MagicMock(),
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Inches",
            side_effect=lambda v: int(v * 914400),
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.XL_CHART_TYPE",
        ) as mock_ct:
            mock_ct.LINE = 2
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(pptx_file),
                "chart_type": "line",
                "chart_data": {"categories": ["A"], "series": [{"name": "s", "values": [1]}]},
            })
            assert result["success"] is True
            assert result["result"]["chart_added"] == "line"

    @pytest.mark.asyncio
    async def test_add_chart_pie_type(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slides.__getitem__ = MagicMock(return_value=mock_slide)

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.CategoryChartData",
            return_value=MagicMock(),
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Inches",
            side_effect=lambda v: int(v * 914400),
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.XL_CHART_TYPE",
        ) as mock_ct:
            mock_ct.PIE = 3
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(pptx_file),
                "chart_type": "pie",
                "chart_data": {"categories": ["A"], "series": [{"name": "s", "values": [1]}]},
            })
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_add_chart_unknown_type(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        mock_prs = MagicMock()
        mock_slide = MagicMock()
        mock_prs.slides.__getitem__ = MagicMock(return_value=mock_slide)

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.CategoryChartData",
            return_value=MagicMock(),
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Inches",
            side_effect=lambda v: int(v * 914400),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(pptx_file),
                "chart_type": "radar",
                "chart_data": {"categories": ["A"], "series": [{"name": "s", "values": [1]}]},
            })
            assert result["success"] is False
            assert "Unknown chart type" in result["error"]

    @pytest.mark.asyncio
    async def test_add_chart_exception(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            side_effect=RuntimeError("oops"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "add_chart",
                "file_path": str(pptx_file),
                "chart_data": {"categories": ["A"], "series": [{"name": "s", "values": [1]}]},
            })
            assert result["success"] is False
            assert "Add chart error" in result["error"]


# ---------------------------------------------------------------------------
# Read presentation
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.skipif(not _has_pptx, reason="python-pptx not installed")
class TestReadPresentation:

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(temp_dir / "no.pptx"),
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_read_success(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        # Build mock slide with title, text shapes, and notes
        mock_title_shape = MagicMock()
        mock_title_shape.text = "Title Text"

        mock_other_shape = MagicMock()
        mock_other_shape.text = "Body content"

        mock_slide = MagicMock()
        mock_slide.shapes.title = mock_title_shape
        mock_slide.shapes.__iter__ = lambda self: iter([mock_title_shape, mock_other_shape])
        mock_slide.has_notes_slide = True
        mock_slide.notes_slide.notes_text_frame.text = "Speaker notes"

        mock_slides = MagicMock()
        mock_slides.__iter__ = MagicMock(return_value=iter([mock_slide]))
        mock_slides.__len__ = MagicMock(return_value=1)

        mock_prs = MagicMock()
        mock_prs.slides = mock_slides
        mock_prs.slide_width = 9144000
        mock_prs.slide_height = 6858000

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(pptx_file),
            })
            assert result["success"] is True
            slides = result["result"]["slides"]
            assert len(slides) == 1
            assert slides[0]["title"] == "Title Text"
            assert slides[0]["notes"] == "Speaker notes"

    @pytest.mark.asyncio
    async def test_read_slide_without_notes(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        mock_slide = MagicMock()
        mock_slide.shapes.title = None
        mock_slide.shapes.__iter__ = lambda self: iter([])
        mock_slide.has_notes_slide = False

        mock_slides = MagicMock()
        mock_slides.__iter__ = MagicMock(return_value=iter([mock_slide]))
        mock_slides.__len__ = MagicMock(return_value=1)

        mock_prs = MagicMock()
        mock_prs.slides = mock_slides

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            return_value=mock_prs,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(pptx_file),
            })
            assert result["success"] is True
            assert result["result"]["slides"][0]["title"] == ""
            assert result["result"]["slides"][0]["notes"] == ""

    @pytest.mark.asyncio
    async def test_read_exception(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ), patch(
            "portal.tools.document_processing.powerpoint_processor.Presentation",
            side_effect=RuntimeError("corrupt"),
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "read",
                "file_path": str(pptx_file),
            })
            assert result["success"] is False
            assert "Read error" in result["error"]


# ---------------------------------------------------------------------------
# Save presentation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSavePresentation:

    @pytest.mark.asyncio
    async def test_save_file_not_found(self, temp_dir):
        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "save",
                "file_path": str(temp_dir / "no.pptx"),
            })
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_save_success(self, temp_dir):
        pptx_file = temp_dir / "test.pptx"
        pptx_file.write_bytes(b"placeholder")

        with patch(
            "portal.tools.document_processing.powerpoint_processor.PPTX_AVAILABLE",
            True,
        ):
            tool = _make_tool()
            result = await tool.execute({
                "action": "save",
                "file_path": str(pptx_file),
            })
            assert result["success"] is True
            assert "saved" in result["result"]
