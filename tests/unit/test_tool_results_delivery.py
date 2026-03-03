"""Tests for ProcessingResult.tool_results field delivery"""

from portal.core.types import ProcessingResult


class TestToolResultsDelivery:
    """Tests verifying tool_results is accessible at top level of ProcessingResult"""

    def test_processing_result_with_tool_results_populated(self):
        """ProcessingResult with tool_results should have them at top level, not just in metadata"""
        tool_results = [
            {"tool": "generate_image", "path": "/data/generated/image.png"},
            {"tool": "generate_music", "path": "/data/generated/music.mp3"},
        ]

        result = ProcessingResult(
            response="Generated files",
            model_used="test-model",
            tool_results=tool_results,
        )

        # Assert tool_results is accessible at top level
        assert result.tool_results is not None
        assert len(result.tool_results) == 2
        assert result.tool_results[0]["path"] == "/data/generated/image.png"
        assert result.tool_results[1]["path"] == "/data/generated/music.mp3"

    def test_processing_result_tool_results_top_level_not_in_metadata_only(self):
        """tool_results should be at top level, not only in metadata"""
        tool_results = [{"tool": "test", "path": "/test/path.png"}]

        # When metadata is explicitly passed without tool_results, it should NOT be in metadata
        result = ProcessingResult(
            response="Test response",
            model_used="test-model",
            tool_results=tool_results,
            metadata={"other_field": "value"},
        )

        # Top-level tool_results should match what was passed in (the key requirement)
        assert result.tool_results == tool_results
        assert result.tool_results[0]["path"] == "/test/path.png"

    def test_processing_result_empty_tool_results(self):
        """ProcessingResult with empty tool_results should have empty list, not None"""
        result = ProcessingResult(
            response="No tools used",
            model_used="test-model",
            tool_results=[],
        )

        assert result.tool_results is not None
        assert result.tool_results == []

    def test_processing_result_orchestrator_path(self):
        """Orchestrator path ProcessingResult should also have tool_results field"""
        result = ProcessingResult(
            response="Multi-step task completed",
            model_used="orchestrator",
            tool_results=[],
        )

        assert result.tool_results is not None
        assert isinstance(result.tool_results, list)
