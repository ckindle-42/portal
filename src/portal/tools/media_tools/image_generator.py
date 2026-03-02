"""Image generation tool — wraps mflux/Flux.2 CLI for local image gen."""

import logging
import shutil
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ImageGenResult:
    success: bool
    image_path: str | None = None
    error: str | None = None


async def generate_image(
    prompt: str,
    output_dir: str = "~/AI_Output/images",
    steps: int = 20,
    model: str = "dev",
) -> ImageGenResult:
    """Generate image via mflux CLI. Requires `pip install mflux`."""
    try:
        if not shutil.which("mflux-generate"):
            return ImageGenResult(
                success=False, error="mflux not installed. Run: pip install mflux"
            )

        # TODO: Implement actual mflux invocation
        # subprocess.run(["mflux-generate", "--prompt", prompt, ...])
        logger.info("Image generation requested: %s", prompt[:80])
        return ImageGenResult(
            success=False, error="Image generation not yet implemented — stub only"
        )
    except Exception as e:
        return ImageGenResult(success=False, error=str(e))
