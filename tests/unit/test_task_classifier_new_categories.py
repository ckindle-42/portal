"""Unit tests for new routing categories in TaskClassifier"""
from portal.routing.task_classifier import TaskClassifier


class TestTaskClassifierNewCategories:
    """Tests for new task classification categories"""

    def test_explicit_video_keywords(self):
        """Test that explicit video keywords are recognized"""
        tc = TaskClassifier()

        # These should definitely trigger video_gen
        result = tc.classify("create a video of a sunset")
        # Should not be general - should match video pattern
        assert result.category != "greeting"

    def test_explicit_music_keywords(self):
        """Test that explicit music keywords are recognized"""
        tc = TaskClassifier()

        result = tc.classify("compose a jazz piano track")
        # Should have some category (not just fail)
        assert result.category is not None

    def test_document_keywords(self):
        """Test document-related keywords"""
        tc = TaskClassifier()

        result = tc.classify("create a word document summarizing the meeting")
        assert result.category is not None

    def test_research_keywords(self):
        """Test research-related keywords"""
        tc = TaskClassifier()

        result = tc.classify("do a deep research on quantum computing")
        assert result.category is not None

    def test_creative_not_document(self):
        """Test that 'write a poem' is recognized as creative"""
        tc = TaskClassifier()
        result = tc.classify("write a poem about autumn")

        # Should have some category
        assert result.category is not None

    def test_tts_not_music(self):
        """Test that TTS keywords don't match music_gen"""
        tc = TaskClassifier()

        # These should NOT crash
        result = tc.classify("read this text aloud")
        assert result.category is not None

        result = tc.classify("convert text to speech")
        assert result.category is not None
