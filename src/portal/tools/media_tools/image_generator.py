"""Image generation tool — wraps mflux/Flux.2 CLI for local image gen."""

import asyncio
import logging
import os
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ImageGenResult:
    success: bool
    image_path: str | None = None
    error: str | None = None


def _get_mflux_command() -> str | None:
    """Find available mflux command."""
    # Try different mflux commands
    commands = [
        "mflux-generate-z-image-turbo",
        "mflux-generate-flux-2",
        "mflux-generate",
    ]
    for cmd in commands:
        if shutil.which(cmd):
            return cmd
    return None


def _get_output_path(output_dir: str) -> Path:
    """Get output path, creating directory if needed."""
    output_path = Path(os.path.expanduser(output_dir))
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


async def generate_image(
    prompt: str,
    output_dir: str = os.getenv("GENERATED_FILES_DIR", "data/generated"),
    steps: int = 20,
    model: str = "dev",
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
) -> ImageGenResult:
    """Generate image via mflux CLI. Requires `uv tool install mflux`.

    Args:
        prompt: Text description of the image to generate
        output_dir: Directory to save the generated image
        steps: Number of inference steps (default 20)
        model: Model variant to use (default "dev")
        width: Image width (default 1024)
        height: Image height (default 1024)
        seed: Random seed for reproducibility (random if None)

    Returns:
        ImageGenResult with success status and image path, or error message
    """
    try:
        mflux_cmd = _get_mflux_command()
        if not mflux_cmd:
            return ImageGenResult(
                success=False,
                error="mflux not installed. Run: uv tool install --upgrade mflux",
            )

        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        output_path = _get_output_path(output_dir)
        output_file = output_path / f"mflux_{seed}.png"

        # Build mflux command
        cmd = [
            mflux_cmd,
            "--prompt",
            prompt,
            "--width",
            str(width),
            "--height",
            str(height),
            "--seed",
            str(seed),
            "--steps",
            str(steps),
            "-q",
            "8",  # Quantization level
            "--output",
            str(output_file),
        ]

        logger.info("Generating image: %s", prompt[:80])
        logger.debug("Running: %s", " ".join(cmd))

        # Run mflux CLI
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error("mflux failed: %s", error_msg)
            return ImageGenResult(success=False, error=f"mflux failed: {error_msg}")

        if not output_file.exists():
            return ImageGenResult(success=False, error="Output file not created")

        logger.info("Image generated: %s", output_file)
        return ImageGenResult(success=True, image_path=str(output_file))

    except FileNotFoundError:
        return ImageGenResult(
            success=False,
            error="mflux not found. Run: uv tool install --upgrade mflux",
        )
    except Exception as e:
        logger.exception("Image generation failed")
        return ImageGenResult(success=False, error=str(e))
