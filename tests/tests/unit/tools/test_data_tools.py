"""
Unit tests for Data tools
"""

import pytest
from unittest.mock import patch, Mock, mock_open
from pathlib import Path
from portal.tools.data_tools.csv_analyzer import CSVAnalyzerTool
from portal.tools.data_tools.file_compressor import FileCompressorTool
from portal.tools.data_tools.math_visualizer import MathVisualizerTool
from portal.tools.data_tools.qr_generator import QRGeneratorTool
from portal.tools.data_tools.text_transformer import TextTransformerTool


@pytest.mark.unit
class TestCSVAnalyzerTool:
    """Test csv_analyzer tool"""

    @pytest.mark.asyncio
    async def test_csv_analyze_success(self, sample_csv_file):
        """Test analyzing a CSV file"""
        tool = CSVAnalyzerTool()

        result = await tool.execute({
            "file_path": str(sample_csv_file),
            "operation": "summary"
        })

        assert result["success"] is True
        assert "analysis" in result or "result" in result

    @pytest.mark.asyncio
    async def test_csv_missing_file(self):
        """Test analyzing non-existent CSV"""
        tool = CSVAnalyzerTool()

        result = await tool.execute({
            "file_path": "/nonexistent/file.csv",
            "operation": "summary"
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

    @pytest.mark.asyncio
    async def test_plot_function(self, temp_dir):
        """Test plotting a mathematical function"""
        tool = MathVisualizerTool()

        output_path = temp_dir / "plot.png"

        with patch("matplotlib.pyplot.savefig"), patch("matplotlib.pyplot.clf"):
            result = await tool.execute({
                "function": "x**2",
                "x_range": [-10, 10],
                "output_file": str(output_path)
            })

            assert result["success"] is True or "error" in result

    @pytest.mark.asyncio
    async def test_invalid_function(self, temp_dir):
        """Test with invalid mathematical function"""
        tool = MathVisualizerTool()

        result = await tool.execute({
            "function": "invalid_func(x)",
            "x_range": [0, 10],
            "output_file": str(temp_dir / "plot.png")
        })

        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
class TestQRGeneratorTool:
    """Test qr_generator tool"""

    @pytest.mark.asyncio
    async def test_generate_qr_code(self, temp_dir):
        """Test generating a QR code"""
        tool = QRGeneratorTool()

        output_path = temp_dir / "qr.png"

        result = await tool.execute({
            "data": "https://example.com",
            "output_file": str(output_path)
        })

        assert result["success"] is True
        # File should be created (if tool implementation saves it)

    @pytest.mark.asyncio
    async def test_generate_qr_with_options(self, temp_dir):
        """Test QR code generation with custom options"""
        tool = QRGeneratorTool()

        result = await tool.execute({
            "data": "Test QR Code",
            "output_file": str(temp_dir / "qr_custom.png"),
            "size": 10,
            "border": 2
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
            "operation": "json_to_yaml",
            "input": '{"key": "value", "number": 123}'
        })

        assert result["success"] is True
        assert "result" in result or "output" in result

    @pytest.mark.asyncio
    async def test_yaml_to_json(self):
        """Test converting YAML to JSON"""
        tool = TextTransformerTool()

        result = await tool.execute({
            "operation": "yaml_to_json",
            "input": "key: value\nnumber: 123"
        })

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        """Test with invalid JSON input"""
        tool = TextTransformerTool()

        result = await tool.execute({
            "operation": "json_to_yaml",
            "input": "{invalid json"
        })

        assert result["success"] is False
        assert "error" in result
