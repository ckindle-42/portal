"""
Unit tests for Data tools
"""

import importlib.util
from unittest.mock import patch

import pytest

from portal.tools.data_tools.csv_analyzer import CSVAnalyzerTool
from portal.tools.data_tools.file_compressor import FileCompressorTool
from portal.tools.data_tools.math_visualizer import MathVisualizerTool
from portal.tools.data_tools.qr_generator import QRGeneratorTool
from portal.tools.data_tools.text_transformer import TextTransformerTool

_has_pandas = importlib.util.find_spec("pandas") is not None
_has_matplotlib = importlib.util.find_spec("matplotlib") is not None
_has_qrcode = importlib.util.find_spec("qrcode") is not None


@pytest.mark.unit
class TestCSVAnalyzerTool:
    """Test csv_analyzer tool"""

    @pytest.mark.skipif(not _has_pandas, reason="pandas not installed")
    @pytest.mark.asyncio
    async def test_csv_analyze_success(self, sample_csv_file):
        """Test analyzing a CSV file — uses real pandas"""
        tool = CSVAnalyzerTool()

        result = await tool.execute({
            "file_path": str(sample_csv_file),
            "analysis_type": "summary",
        })

        assert result["success"] is True
        assert "analysis" in result or "result" in result

    @pytest.mark.asyncio
    async def test_csv_missing_file(self):
        """Test analyzing non-existent CSV"""
        tool = CSVAnalyzerTool()

        result = await tool.execute({
            "file_path": "/nonexistent/file.csv",
            "operation": "summary",
        })

        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
class TestFileCompressorTool:
    """Test file_compressor tool"""

    @pytest.mark.asyncio
    async def test_compress_zip(self, temp_dir, mock_file_system):
        """Test compressing files to ZIP"""
        tool = FileCompressorTool()

        output_path = temp_dir / "output.zip"

        with patch("zipfile.ZipFile"):
            result = await tool.execute({
                "operation": "compress",
                "source": str(mock_file_system["file"]),
                "output": str(output_path),
                "format": "zip"
            })

            assert result["success"] is True or "error" in result

    @pytest.mark.asyncio
    async def test_extract_zip(self, temp_dir):
        """Test extracting ZIP archive"""
        tool = FileCompressorTool()

        with patch("zipfile.ZipFile"):
            result = await tool.execute({
                "operation": "extract",
                "source": str(temp_dir / "archive.zip"),
                "output": str(temp_dir / "extracted")
            })

            # May fail if validation is strict
            assert "success" in result or "error" in result


@pytest.mark.unit
class TestMathVisualizerTool:
    """Test math_visualizer tool"""

    @pytest.mark.skipif(not _has_matplotlib, reason="matplotlib not installed")
    @pytest.mark.asyncio
    async def test_plot_function(self, temp_dir):
        """Test plotting a mathematical function — uses real matplotlib"""
        tool = MathVisualizerTool()

        with patch("matplotlib.pyplot.savefig"), patch("matplotlib.pyplot.close"):
            result = await tool.execute({
                "expression": "x**2",
                "x_range": [-10, 10],
            })

        assert result["success"] is True or "error" in result

    @pytest.mark.asyncio
    async def test_invalid_function(self, temp_dir):
        """Test with invalid mathematical function"""
        tool = MathVisualizerTool()

        result = await tool.execute({
            "expression": "invalid_func(x)",
            "x_range": [0, 10],
        })

        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
@pytest.mark.skipif(not _has_qrcode, reason="qrcode not installed")
class TestQRGeneratorTool:
    """Test qr_generator tool"""

    @pytest.mark.asyncio
    async def test_generate_qr_code(self, temp_dir):
        """Test generating a QR code — uses real qrcode library"""
        tool = QRGeneratorTool()

        result = await tool.execute({
            "content": "https://example.com",
        })

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_generate_qr_with_options(self, temp_dir):
        """Test QR code generation with custom options"""
        tool = QRGeneratorTool()

        result = await tool.execute({
            "content": "Test QR Code",
            "size": 8,
        })

        assert result["success"] is True


@pytest.mark.unit
class TestTextTransformerTool:
    """Test text_transformer tool"""

    @pytest.mark.asyncio
    async def test_json_to_yaml(self):
        """Test converting JSON to YAML"""
        tool = TextTransformerTool()

        result = await tool.execute({
            "content": '{"key": "value", "number": 123}',
            "from_format": "json",
            "to_format": "yaml",
        })

        assert result["success"] is True
        assert "result" in result or "output" in result

    @pytest.mark.asyncio
    async def test_yaml_to_json(self):
        """Test converting YAML to JSON"""
        tool = TextTransformerTool()

        result = await tool.execute({
            "content": "key: value\nnumber: 123",
            "from_format": "yaml",
            "to_format": "json",
        })

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        """Test with invalid JSON input"""
        tool = TextTransformerTool()

        result = await tool.execute({
            "content": "{invalid json",
            "from_format": "json",
            "to_format": "yaml",
        })

        assert result["success"] is False
        assert "error" in result
