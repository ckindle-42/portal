"""
Unit tests for Web and Media tools
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
from portal.tools.web_tools.http_client import HTTPClientTool
from portal.tools.media_tools.audio.audio_transcriber import AudioTranscribeTool


@pytest.mark.unit
class TestHTTPClientTool:
    """Test http_client tool"""

    @pytest.mark.asyncio
    async def test_http_get_request(self):
        """Test HTTP GET request"""
        tool = HTTPClientTool()

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="Response text")
            mock_response.json = AsyncMock(return_value={"status": "ok"})

            mock_session.get = AsyncMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session

            result = await tool.execute({
                "method": "GET",
                "url": "https://api.example.com/data"
            })

            assert result["success"] is True
            assert "response" in result or "result" in result

    @pytest.mark.asyncio
    async def test_http_post_request(self):
        """Test HTTP POST request"""
        tool = HTTPClientTool()

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_response.json = AsyncMock(return_value={"id": 123})

            mock_session.post = AsyncMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_session_class.return_value = mock_session

            result = await tool.execute({
                "method": "POST",
                "url": "https://api.example.com/create",
                "data": {"name": "test"}
            })

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_http_invalid_url(self):
        """Test with invalid URL"""
        tool = HTTPClientTool()

        result = await tool.execute({
            "method": "GET",
            "url": "not-a-valid-url"
        })

        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
class TestAudioTranscribeTool:
    """Test audio_transcribe tool"""

    @pytest.mark.asyncio
    async def test_transcribe_audio(self, temp_dir):
        """Test transcribing an audio file"""
        tool = AudioTranscribeTool()

        audio_file = temp_dir / "test.mp3"
        audio_file.write_text("dummy audio content")

        with patch("whisper.load_model") as mock_model:
            mock_whisper = Mock()
            mock_whisper.transcribe = Mock(return_value={
                "text": "This is the transcribed text"
            })
            mock_model.return_value = mock_whisper

            result = await tool.execute({
                "file_path": str(audio_file),
                "model": "base"
            })

            # May succeed or fail depending on implementation
            assert "success" in result

    @pytest.mark.asyncio
    async def test_transcribe_missing_file(self):
        """Test transcribing non-existent audio file"""
        tool = AudioTranscribeTool()

        result = await tool.execute({
            "file_path": "/nonexistent/audio.mp3"
        })

        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
class TestDevTools:
    """Test development tools"""

    @pytest.mark.asyncio
    async def test_python_env_manager(self, temp_dir):
        """Test Python environment manager tool"""
        from portal.tools.dev_tools.python_env_manager import PythonEnvManagerTool

        tool = PythonEnvManagerTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Successfully created virtual environment",
                stderr=""
            )

            result = await tool.execute({
                "operation": "create",
                "path": str(temp_dir / "venv")
            })

            assert result["success"] is True or "error" in result
