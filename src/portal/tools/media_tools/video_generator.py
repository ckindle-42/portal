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
VIDEO_BACKEND = os.getenv("VIDEO_BACKEND", "wan22")  # "wan22" or "cogvideox"

# Wan2.2 T2V workflow — uses UNETLoader, CLIPLoader, VAELoader, EmptyHunyuanLatentVideo
_WAN22_T2V_WORKFLOW: dict = {
    "1": {
        "inputs": {"model_name": "wan2.2_ti2v_5B_fp16.safetensors"},
        "class_type": "UNETLoader",
    },
    "2": {
        "inputs": {"model_name": "clip_l.safetensors"},
        "class_type": "CLIPLoader",
    },
    "3": {
        "inputs": {"model_name": "wan2.2_vae.safetensors"},
        "class_type": "VAELoader",
    },
    "4": {
        "inputs": {"text": "", "clip": ["2", 1]},
        "class_type": "CLIPTextEncode",
    },
    "5": {
        "inputs": {"text": "", "clip": ["2", 1]},
        "class_type": "CLIPTextEncode",
    },
    "6": {
        "inputs": {
            "width": 832,
            "height": 480,
            "video_frames": 81,
            "batch_size": 1,
        },
        "class_type": "EmptyHunyuanLatentVideo",
    },
    "7": {
        "inputs": {
            "model": ["1", 0],
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["6", 0],
            "seed": 42,
            "steps": 20,
            "cfg": 6.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
        },
        "class_type": "KSampler",
    },
    "8": {
        "inputs": {"samples": ["7", 0], "vae": ["3", 0]},
        "class_type": "VAEDecode",
    },
    "9": {
        "inputs": {
            "filename_prefix": "portal_video_",
            "images": ["8", 0],
            "fps": 16,
            "format": "video/h264-mp4",
        },
        "class_type": "VHS_VideoCombine",
    },
}

# CogVideoX fallback workflow — works with cogvideox_5b.safetensors
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


def _get_workflow() -> dict:
    """Get the workflow based on VIDEO_BACKEND setting."""
    if VIDEO_BACKEND == "wan22":
        return _WAN22_T2V_WORKFLOW.copy()
    return _COGVIDEOX_WORKFLOW.copy()


@dataclass
class VideoGenResult:
    success: bool
    video_path: str | None = None
    error: str | None = None


async def generate_video(
    prompt: str,
    output_dir: str = "data/generated",
    width: int = 832,
    height: int = 480,
    frames: int = 81,
    fps: int = 16,
    steps: int = 20,
    model: str = "wan2.2_ti2v_5B_fp16.safetensors",
    seed: int = -1,
) -> VideoGenResult:
    """Generate a video via ComfyUI video workflow.

    Requires ComfyUI running with a video generation model (Wan2.2, CogVideoX, etc.).
    Set COMFYUI_URL env var if ComfyUI is not at localhost:8188.
    Set VIDEO_BACKEND=wan22 (default) or VIDEO_BACKEND=cogvideox.

    Args:
        prompt: Text description of the video to generate
        output_dir: Local directory to save the video (used if ComfyUI output is accessible)
        width: Video width in pixels (default 832 for Wan2.2)
        height: Video height in pixels (default 480)
        frames: Number of frames (default 81 ≈ 5s at 16fps)
        fps: Frames per second for output video (default 16)
        steps: Diffusion steps (default 20)
        model: ComfyUI model name (default wan2.2_ti2v_5B_fp16.safetensors)
        seed: Random seed, -1 for random

    Returns:
        VideoGenResult with success status and video path, or error message
    """
    if seed == -1:
        seed = int(time.time() * 1000) % (2**32)

    workflow = _get_workflow()

    # Update workflow based on parameters
    if VIDEO_BACKEND == "wan22":
        workflow["1"]["inputs"]["model_name"] = model
        workflow["2"]["inputs"]["model_name"] = os.getenv("VIDEO_TEXT_ENCODER", "clip_l.safetensors")
        workflow["3"]["inputs"]["model_name"] = os.getenv("VIDEO_VAE", "wan2.2_vae.safetensors")
        workflow["4"]["inputs"]["text"] = prompt
        workflow["5"]["inputs"]["text"] = ""  # negative prompt
        workflow["6"]["inputs"]["width"] = width
        workflow["6"]["inputs"]["height"] = height
        workflow["6"]["inputs"]["video_frames"] = frames
        workflow["7"]["inputs"]["seed"] = seed
        workflow["7"]["inputs"]["steps"] = steps
        workflow["9"]["inputs"]["fps"] = fps
    else:
        # CogVideoX
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
                "Ensure ComfyUI is running with a video model (Wan2.2, CogVideoX, Mochi)."
            ),
        )
    except Exception as e:
        logger.exception("Video generation failed")
        return VideoGenResult(success=False, error=str(e))


def _ensure_output_dir(output_dir: str) -> Path:
    path = Path(os.path.expanduser(output_dir))
    path.mkdir(parents=True, exist_ok=True)
    return path
