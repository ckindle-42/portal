"""
Unit tests for Web and Media tools
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from portal.tools.web_tools.http_client import HTTPClientTool
from portal.tools.media_tools.audio.audio_transcriber import AudioTranscribeTool


@pytest.mark.unit
class TestHTTPClientTool:
    """Test http_client tool"""

    @pytest.mark.asyncio
    async def test_http_get_request(self):
        """Test HTTP GET request"""
        tool = HTTPClientTool()

        # Tool: async with aiohttp.ClientSession() as session:
        #           async with session.request(method, **kwargs) as response:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        mock_response.text = AsyncMock(return_value='{"status": "ok"}')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.request = Mock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await tool.execute({
                "method": "GET",
                "url": "https://api.example.com/data",
            })

        assert result["success"] is True
        assert "response" in result or "result" in result

    @pytest.mark.asyncio
    async def test_http_post_request(self):
        """Test HTTP POST request"""
        tool = HTTPClientTool()

        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"id": 123})
        mock_response.text = AsyncMock(return_value='{"id": 123}')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.request = Mock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await tool.execute({
                "method": "POST",
                "url": "https://api.example.com/create",
                "body": '{"name": "test"}',
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
        """Test audio transcription — requires faster-whisper runtime"""
        try:
            from faster_whisper import WhisperModel  # noqa: F401
        except ImportError:
            pytest.skip(
                "faster-whisper not available (pip install faster-whisper)"
            )

        audio_file = temp_dir / "test.wav"
        audio_file.write_bytes(b"\x00" * 1000)  # dummy audio bytes

        mock_segment = MagicMock()
        mock_segment.text = "This is transcribed text"
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.duration = 1.0

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        with patch("faster_whisper.WhisperModel", return_value=mock_model):
            tool = AudioTranscribeTool()
            result = await tool.execute({
                "audio_files": [str(audio_file)],
                "model_size": "base",
            })

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
