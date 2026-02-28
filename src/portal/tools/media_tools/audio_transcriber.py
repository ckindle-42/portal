"""Audio Transcriber Tool - Local Whisper transcription"""

import os
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory


class AudioTranscribeTool(BaseTool):
    """Transcribe audio files using local Whisper"""

    METADATA = {
        "name": "audio_transcribe",
        "description": "Transcribe audio files using local Whisper model",
        "category": ToolCategory.AUDIO,
        "version": "1.0.0",
        "requires_confirmation": False,
        "parameters": [
            {"name": "audio_files", "param_type": "list", "description": "List of audio file paths", "required": True},
            {"name": "model_size", "param_type": "string", "description": "Model size: tiny, base, small, medium, large", "required": False, "default": "base"},
            {"name": "language", "param_type": "string", "description": "Language code (e.g., 'en', 'es') or 'auto'", "required": False, "default": "auto"},
        ],
        "examples": ["Transcribe audio.mp3"],
    }

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Transcribe audio files"""
        try:
            audio_files = parameters.get("audio_files", [])
            model_size = parameters.get("model_size", "base")
            language = parameters.get("language", "auto")

            if not audio_files:
                return self._error_response("No audio files provided")

            # Try to use faster-whisper first
            try:
                from faster_whisper import WhisperModel

                model = WhisperModel(model_size, device="cpu", compute_type="int8")

                results = []
                for audio_path in audio_files:
                    if not os.path.exists(audio_path):
                        results.append(
                            {"file": audio_path, "success": False, "error": "File not found"}
                        )
                        continue

                    segments, info = model.transcribe(
                        audio_path, language=None if language == "auto" else language, beam_size=5
                    )

                    text = " ".join([segment.text for segment in segments])

                    results.append(
                        {
                            "file": audio_path,
                            "success": True,
                            "text": text,
                            "language": info.language,
                            "duration": info.duration,
                        }
                    )

                return self._success_response(results)

            except ImportError:
                # Try MLX Whisper for Apple Silicon
                try:
                    import mlx_whisper

                    results = []
                    for audio_path in audio_files:
                        if not os.path.exists(audio_path):
                            results.append(
                                {"file": audio_path, "success": False, "error": "File not found"}
                            )
                            continue

                        result = mlx_whisper.transcribe(audio_path)

                        results.append(
                            {
                                "file": audio_path,
                                "success": True,
                                "text": result.get("text", ""),
                                "language": result.get("language", "unknown"),
                            }
                        )

                    return self._success_response(results)

                except ImportError:
                    return self._error_response(
                        "No transcription library available. Install either:\n"
                        "- pip install faster-whisper\n"
                        "- pip install mlx-whisper (Apple Silicon)"
                    )

        except Exception as e:
            return self._error_response(str(e))
