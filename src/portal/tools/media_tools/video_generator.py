"""Video generation tool — wraps ComfyUI video workflows for local video generation."""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://localhost:8188")

# Minimal CogVideoX workflow template — replace checkpoint name as needed
_COGVIDEOX_WORKFLOW: dict = {
    "1": {
        "inputs": {"ckpt_name": "cogvideox_5b.safetensors"},
        "class_type": "CheckpointLoaderSimple",
    },
    "2": {
        "inputs": {
            "text": "",
            "clip": ["1", 1],
        },
        "class_type": "CLIPTextEncode",
    },
    "3": {
        "inputs": {
            "width": 720,
            "height": 480,
            "video_frames": 49,
            "batch_size": 1,
        },
        "class_type": "EmptyLatentVideo",
    },
    "4": {
        "inputs": {
            "model": ["1", 0],
            "conditioning": ["2", 0],
            "latent_image": ["3", 0],
            "noise_seed": 42,
            "steps": 20,
            "cfg": 6,
            "sampler_name": "euler",
            "scheduler": "linear",
            "denoise": 1,
        },
        "class_type": "KSampler",
    },
    "5": {
        "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
        "class_type": "VAEDecode",
    },
    "6": {
        "inputs": {
            "filename_prefix": "portal_video_",
            "images": ["5", 0],
            "fps": 8,
            "format": "video/h264-mp4",
        },
        "class_type": "VHS_VideoCombine",
    },
}


@dataclass
class VideoGenResult:
    success: bool
    video_path: str | None = None
    error: str | None = None


async def generate_video(
    prompt: str,
    output_dir: str = "~/AI_Output/video",
    width: int = 720,
    height: int = 480,
    frames: int = 49,
    fps: int = 8,
    steps: int = 20,
    model: str = "cogvideox_5b.safetensors",
    seed: int = -1,
) -> VideoGenResult:
    """Generate a video via ComfyUI video workflow.

    Requires ComfyUI running with a video generation model (CogVideoX, Wan2.1, etc.).
    Set COMFYUI_URL env var if ComfyUI is not at localhost:8188.

    Args:
        prompt: Text description of the video to generate
        output_dir: Local directory to save the video (used if ComfyUI output is accessible)
        width: Video width in pixels (default 720)
        height: Video height in pixels (default 480)
        frames: Number of frames (default 49 ≈ 6s at 8fps)
        fps: Frames per second for output video (default 8)
        steps: Diffusion steps (default 20)
        model: ComfyUI checkpoint name (default cogvideox_5b.safetensors)
        seed: Random seed, -1 for random

    Returns:
        VideoGenResult with success status and video path, or error message
    """
    import json

    if seed == -1:
        seed = int(time.time() * 1000) % (2**32)

    workflow = json.loads(json.dumps(_COGVIDEOX_WORKFLOW))
    workflow["1"]["inputs"]["ckpt_name"] = model
    workflow["2"]["inputs"]["text"] = prompt
    workflow["3"]["inputs"]["width"] = width
    workflow["3"]["inputs"]["height"] = height
    workflow["3"]["inputs"]["video_frames"] = frames
    workflow["4"]["inputs"]["noise_seed"] = seed
    workflow["4"]["inputs"]["steps"] = steps
    workflow["6"]["inputs"]["fps"] = fps

    client_id = str(uuid.uuid4())

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{COMFYUI_URL}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            if resp.status_code != 200:
                return VideoGenResult(
                    success=False,
                    error=f"ComfyUI not available at {COMFYUI_URL}. Is it running with a video model?",
                )
            prompt_id = resp.json()["prompt_id"]

            # Poll for completion (video gen can take several minutes)
            for _ in range(300):  # 300 × 2s = 10 min max
                await asyncio.sleep(2)
                history_resp = await client.get(f"{COMFYUI_URL}/history/{prompt_id}")
                history = history_resp.json()

                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_output in outputs.values():
                        gifs = node_output.get("gifs", [])
                        if gifs:
                            filename = gifs[0]["filename"]
                            return VideoGenResult(
                                success=True,
                                video_path=f"{COMFYUI_URL}/view?filename={filename}&type=output",
                            )
                    return VideoGenResult(
                        success=False, error="Video generation completed but no output found"
                    )

        return VideoGenResult(success=False, error="Video generation timed out after 10 minutes")

    except httpx.ConnectError:
        return VideoGenResult(
            success=False,
            error=(
                f"Cannot connect to ComfyUI at {COMFYUI_URL}. "
                "Ensure ComfyUI is running with a video model (CogVideoX, Wan2.1, Mochi)."
            ),
        )
    except Exception as e:
        logger.exception("Video generation failed")
        return VideoGenResult(success=False, error=str(e))


def _ensure_output_dir(output_dir: str) -> Path:
    path = Path(os.path.expanduser(output_dir))
    path.mkdir(parents=True, exist_ok=True)
    return path
