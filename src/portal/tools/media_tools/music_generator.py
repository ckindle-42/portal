"""Music generation tool — wraps Meta AudioCraft/MusicGen for local music generation."""

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MusicGenResult:
    success: bool
    audio_path: str | None = None
    duration: float | None = None
    error: str | None = None


async def _check_audiocraft_available() -> tuple[bool, str]:
    """Check if AudioCraft is installed."""
    try:
        import audiocraft  # noqa: F401

        return True, ""
    except ImportError:
        return False, "AudioCraft not installed. Run: pip install audiocraft"


async def generate_music(
    prompt: str,
    duration: float = 10.0,
    model_size: str = "medium",
    output_dir: str = "~/AI_Output/music",
    top_k: int = 250,
    top_p: float = 0.0,
    temperature: float = 1.0,
    cfg_coef: float = 3.0,
) -> MusicGenResult:
    """Generate music via Meta AudioCraft MusicGen.

    Requires AudioCraft installation: pip install audiocraft
    Models are downloaded automatically on first use (~300MB–3.3GB depending on size).

    Args:
        prompt: Text description of the music to generate (e.g., "upbeat jazz piano solo")
        duration: Duration in seconds (default 10.0, max ~30s for medium model)
        model_size: MusicGen model size — small (300M), medium (1.5B), large (3.3B)
        output_dir: Directory to save the generated audio file
        top_k: Top-k sampling parameter (default 250)
        top_p: Top-p (nucleus) sampling; 0 disables it (default 0.0)
        temperature: Sampling temperature (default 1.0)
        cfg_coef: Classifier-free guidance coefficient (default 3.0)

    Returns:
        MusicGenResult with success status, audio path, duration, or error message
    """
    available, error_msg = await _check_audiocraft_available()
    if not available:
        return MusicGenResult(success=False, error=error_msg)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _generate_music_sync,
        prompt,
        duration,
        model_size,
        output_dir,
        top_k,
        top_p,
        temperature,
        cfg_coef,
    )
    return result


def _generate_music_sync(
    prompt: str,
    duration: float,
    model_size: str,
    output_dir: str,
    top_k: int,
    top_p: float,
    temperature: float,
    cfg_coef: float,
) -> MusicGenResult:
    """Synchronous music generation using AudioCraft MusicGen."""
    try:
        import torch
        import torchaudio
        from audiocraft.models import MusicGen

        output_path = Path(os.path.expanduser(output_dir))
        output_path.mkdir(parents=True, exist_ok=True)

        model_name = f"facebook/musicgen-{model_size}"
        logger.info("Loading MusicGen model: %s", model_name)
        model = MusicGen.get_pretrained(model_name)

        model.set_generation_params(
            duration=duration,
            top_k=top_k,
            top_p=top_p,
            temperature=temperature,
            cfg_coef=cfg_coef,
        )

        logger.info("Generating music for prompt: %s", prompt[:80])
        with torch.no_grad():
            wav = model.generate([prompt])  # shape: (batch, channels, samples)

        sample_rate = model.sample_rate
        audio_data = wav[0].cpu()  # first in batch, shape (channels, samples)

        # Create a safe filename from the prompt
        safe_prompt = "".join(c if c.isalnum() or c in (" ", "_") else "_" for c in prompt[:40])
        safe_prompt = safe_prompt.strip().replace(" ", "_")
        output_file = output_path / f"music_{safe_prompt}_{int(duration)}s.wav"

        torchaudio.save(str(output_file), audio_data, sample_rate)

        actual_duration = audio_data.shape[-1] / sample_rate
        logger.info("Music generated: %s (%.1fs)", output_file, actual_duration)

        return MusicGenResult(
            success=True,
            audio_path=str(output_file),
            duration=actual_duration,
        )

    except Exception as e:
        logger.exception("Music generation failed")
        return MusicGenResult(success=False, error=str(e))
