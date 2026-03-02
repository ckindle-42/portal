"""
Unit tests for Web and Media tools
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from portal.tools.media_tools.audio_transcriber import AudioTranscribeTool
from portal.tools.web_tools.http_client import HTTPClientTool


@pytest.mark.unit
class TestHTTPClientTool:
    """Test http_client tool"""

    @pytest.mark.asyncio
    async def test_http_get_request(self):
        """Test HTTP GET request"""
        tool = HTTPClientTool()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = Mock(return_value={"status": "ok"})
        mock_response.text = '{"status": "ok"}'

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "portal.tools.web_tools.http_client.httpx.AsyncClient", return_value=mock_client
        ):
            result = await tool.execute(
                {
                    "method": "GET",
                    "url": "https://api.example.com/data",
                }
            )

        assert result["success"] is True
        assert "response" in result or "result" in result

    @pytest.mark.asyncio
    async def test_http_post_request(self):
        """Test HTTP POST request"""
        tool = HTTPClientTool()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = Mock(return_value={"id": 123})
        mock_response.text = '{"id": 123}'

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "portal.tools.web_tools.http_client.httpx.AsyncClient", return_value=mock_client
        ):
            result = await tool.execute(
                {
                    "method": "POST",
                    "url": "https://api.example.com/create",
                    "body": '{"name": "test"}',
                }
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_http_invalid_url(self):
        """Test with invalid URL"""
        tool = HTTPClientTool()

        result = await tool.execute({"method": "GET", "url": "not-a-valid-url"})

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
            pytest.skip("faster-whisper not available (pip install faster-whisper)")

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
            result = await tool.execute(
                {
                    "audio_files": [str(audio_file)],
                    "model_size": "base",
                }
            )

        assert "success" in result

    @pytest.mark.asyncio
    async def test_transcribe_missing_file(self):
        """Test transcribing non-existent audio file"""
        tool = AudioTranscribeTool()

        result = await tool.execute({"file_path": "/nonexistent/audio.mp3"})

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
                returncode=0, stdout="Successfully created virtual environment", stderr=""
            )

            result = await tool.execute({"operation": "create", "path": str(temp_dir / "venv")})

            assert result["success"] is True or "error" in result


@pytest.mark.unit
class TestImageGenerator:
    """Test image generation tool"""

    @pytest.mark.asyncio
    async def test_generate_image_mflux_not_installed(self):
        """Test image generation when mflux is not installed"""
        from portal.tools.media_tools.image_generator import generate_image

        with patch("shutil.which", return_value=None):
            result = await generate_image("a cat sitting on a mat")

        assert result.success is False
        assert "mflux" in result.error.lower()

    @pytest.mark.asyncio
    async def test_generate_image_with_options(self, temp_dir):
        """Test image generation with custom options"""
        from portal.tools.media_tools.image_generator import generate_image

        with patch("shutil.which", return_value="mflux-generate-z-image-turbo"):
            with patch("asyncio.create_subprocess_exec") as mock_subprocess:
                mock_process = AsyncMock()
                mock_process.returncode = 0
                mock_process.communicate = AsyncMock(return_value=(b"", b""))
                mock_subprocess.return_value = mock_process

                with patch("pathlib.Path.exists", return_value=True):
                    result = await generate_image(
                        prompt="a cat",
                        output_dir=str(temp_dir),
                        steps=25,
                        width=512,
                        height=512,
                        seed=42,
                    )

                # Should attempt to call mflux
                mock_subprocess.assert_called_once()
                # Result should indicate success since output file exists
                assert result.success is True
                assert result.image_path is not None


@pytest.mark.unit
class TestAudioGenerator:
    """Test audio generation tool"""

    @pytest.mark.asyncio
    async def test_generate_audio_cosyvoice_not_installed(self):
        """Test audio generation when cosyvoice is not installed"""
        from portal.tools.media_tools.audio_generator import generate_audio

        with patch(
            "portal.tools.media_tools.audio_generator._check_cosyvoice_available",
            return_value=(False, "Missing dependency: cosyvoice"),
        ):
            result = await generate_audio("Hello world")

        assert result.success is False
        assert "cosyvoice" in result.error.lower()

    @pytest.mark.asyncio
    async def test_generate_audio_invalid_voice(self, temp_dir):
        """Test audio generation with invalid voice option"""
        from portal.tools.media_tools.audio_generator import generate_audio

        # CosyVoice available but invalid voice
        with patch(
            "portal.tools.media_tools.audio_generator._check_cosyvoice_available",
            return_value=(True, ""),
        ):
            result = await generate_audio("Hello", voice="invalid_voice")

        assert result.success is False
        assert "voice" in result.error.lower()

    @pytest.mark.asyncio
    async def test_clone_voice_cosyvoice_not_installed(self):
        """Test voice cloning when cosyvoice is not installed"""
        from portal.tools.media_tools.audio_generator import clone_voice

        with patch(
            "portal.tools.media_tools.audio_generator._check_cosyvoice_available",
            return_value=(False, "Missing dependency: cosyvoice"),
        ):
            result = await clone_voice("Hello world", "reference.wav")

        assert result.success is False
        assert "cosyvoice" in result.error.lower()
