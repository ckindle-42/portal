"""Audio generation tool — wraps CosyVoice2/MOSS-TTS for local TTS and voice clone."""

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger(__name__)


@dataclass
class AudioGenResult:
    success: bool
    audio_path: str | None = None
    error: str | None = None


# CosyVoice speaker options
COSYVOICE_SPEAKERS = {
    # Chinese voices
    "中文女": "Chinese female",
    "中文男": "Chinese male",
    # English voices
    "英文女": "English female",
    "英文男": "English male",
    # Japanese voices
    "日文女": "Japanese female",
    "日文男": "Japanese male",
}


def _get_output_path(output_dir: str, prefix: str = "audio") -> Path:
    """Get output path, creating directory if needed."""
    output_path = Path(os.path.expanduser(output_dir))
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


async def _check_cosyvoice_available() -> tuple[bool, str]:
    """Check if CosyVoice is available and return status."""
    try:
        # Check if cosyvoice module is available
        import cosyvoice  # noqa: F401
        import torchaudio  # noqa: F401

        return True, ""
    except ImportError as e:
        missing = str(e).split("'")[-2] if "'" in str(e) else str(e)
        return False, f"Missing dependency: {missing}. Run: pip install cosyvoice torchaudio"


async def generate_audio(
    text: str,
    voice: str = "中文女",
    output_dir: str = "~/AI_Output/audio",
    sample_rate: int = 22050,
) -> AudioGenResult:
    """Generate audio via CosyVoice TTS. Requires CosyVoice installation.

    Args:
        text: Text to synthesize into speech
        voice: Speaker voice to use (default "中文女"). Options: 中文女, 中文男, 英文女, 英文男, 日文女, 日文男
        output_dir: Directory to save the generated audio
        sample_rate: Audio sample rate (default 22050)

    Returns:
        AudioGenResult with success status and audio path, or error message
    """
    try:
        available, error = await _check_cosyvoice_available()
        if not available:
            return AudioGenResult(success=False, error=error)

        # Validate voice
        if voice not in COSYVOICE_SPEAKERS:
            return AudioGenResult(
                success=False,
                error=f"Invalid voice '{voice}'. Valid options: {', '.join(COSYVOICE_SPEAKERS.keys())}",
            )

        # Run audio generation in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        audio_path = await loop.run_in_executor(
            None,
            _generate_audio_sync,
            text,
            voice,
            output_dir,
            sample_rate,
        )

        if audio_path:
            logger.info("Audio generated: %s", audio_path)
            return AudioGenResult(success=True, audio_path=audio_path)
        else:
            return AudioGenResult(success=False, error="Audio generation failed")

    except Exception as e:
        logger.exception("Audio generation failed")
        return AudioGenResult(success=False, error=str(e))


def _generate_audio_sync(
    text: str,
    voice: str,
    output_dir: str,
    sample_rate: int,
) -> str | None:
    """Synchronous audio generation using CosyVoice."""
    try:
        import torchaudio
        from cosyvoice.cli.cosyvoice import CosyVoice

        output_path = _get_output_path(output_dir)
        output_file = output_path / f"tts_{voice}_{hash(text) % 10000}.wav"

        # Load CosyVoice model (this may take a while)
        logger.info("Loading CosyVoice model...")
        cosyvoice = CosyVoice("pretrained_models/CosyVoice-300M-SFT")

        # Generate speech
        logger.info("Generating speech for: %s", text[:50])
        for output in cosyvoice.inference_sft(text, voice):
            # Save the generated audio
            torchaudio.save(str(output_file), output["tts_speech"], sample_rate)
            break  # Only need first result

        if output_file.exists():
            return str(output_file)
        return None

    except Exception as e:
        logger.error("CosyVoice generation failed: %s", e)
        return None


async def clone_voice(
    text: str,
    reference_audio: str | BinaryIO,
    output_dir: str = "~/AI_Output/audio",
    sample_rate: int = 22050,
) -> AudioGenResult:
    """Clone voice from reference audio and generate speech.

    Args:
        text: Text to synthesize into speech
        reference_audio: Path to reference audio file or file-like object
        output_dir: Directory to save the generated audio
        sample_rate: Audio sample rate (default 22050)

    Returns:
        AudioGenResult with success status and audio path, or error message
    """
    try:
        available, error = await _check_cosyvoice_available()
        if not available:
            return AudioGenResult(success=False, error=error)

        # Run voice cloning in thread pool
        loop = asyncio.get_event_loop()
        audio_path = await loop.run_in_executor(
            None,
            _clone_voice_sync,
            text,
            reference_audio,
            output_dir,
            sample_rate,
        )

        if audio_path:
            logger.info("Voice cloned audio generated: %s", audio_path)
            return AudioGenResult(success=True, audio_path=audio_path)
        else:
            return AudioGenResult(success=False, error="Voice cloning failed")

    except Exception as e:
        logger.exception("Voice cloning failed")
        return AudioGenResult(success=False, error=str(e))


def _clone_voice_sync(
    text: str,
    reference_audio: str | BinaryIO,
    output_dir: str,
    sample_rate: int,
) -> str | None:
    """Synchronous voice cloning using CosyVoice zero-shot mode."""
    try:
        import torchaudio
        from cosyvoice.cli.cosyvoice import CosyVoice

        output_path = _get_output_path(output_dir)
        output_file = output_path / f"clone_{hash(str(reference_audio)) % 10000}.wav"

        # Load CosyVoice model
        logger.info("Loading CosyVoice model for voice cloning...")
        cosyvoice = CosyVoice("pretrained_models/CosyVoice-300M-ZeroShot")

        # Handle reference audio
        if isinstance(reference_audio, str):
            # Load reference audio
            reference, sr = torchaudio.load(reference_audio)
            if sr != sample_rate:
                import torchaudio.functional as F

                reference = F.resample(reference, sr, sample_rate)
        else:
            # Already a file-like object
            reference, sr = torchaudio.load(reference_audio)

        # Generate speech with voice cloning
        logger.info("Cloning voice and generating speech for: %s", text[:50])
        for output in cosyvoice.inference_zero_shot(text, reference, "中文女"):
            torchaudio.save(str(output_file), output["tts_speech"], sample_rate)
            break

        if output_file.exists():
            return str(output_file)
        return None

    except Exception as e:
        logger.error("CosyVoice voice cloning failed: %s", e)
        return None
