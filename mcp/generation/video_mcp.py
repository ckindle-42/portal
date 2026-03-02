"""
Video Generation MCP Server
Wraps ComfyUI video workflows for local video generation.
Exposes: generate_video, list_video_models

Requires: ComfyUI running at COMFYUI_URL with a video model installed
          (CogVideoX, Wan2.1, or Mochi via ComfyUI Manager)
Start with: python -m mcp.generation.video_mcp
"""

import asyncio
import json
import os
import time
import uuid

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("video-generation")

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://localhost:8188")

# CogVideoX workflow template — works with cogvideox_5b.safetensors
_VIDEO_WORKFLOW: dict = {
    "1": {
        "inputs": {"ckpt_name": "cogvideox_5b.safetensors"},
        "class_type": "CheckpointLoaderSimple",
    },
    "2": {
        "inputs": {"text": "", "clip": ["1", 1]},
        "class_type": "CLIPTextEncode",
    },
    "3": {
        "inputs": {"width": 720, "height": 480, "video_frames": 49, "batch_size": 1},
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


@mcp.tool()
async def generate_video(
    prompt: str,
    width: int = 720,
    height: int = 480,
    frames: int = 49,
    fps: int = 8,
    steps: int = 20,
    model: str = "cogvideox_5b.safetensors",
    seed: int = -1,
) -> dict:
    """
    Generate a video using ComfyUI with a local video model (CogVideoX, Wan2.1, Mochi).

    Returns a URL to the generated video served by ComfyUI.

    Args:
        prompt: Text description of the video to generate
        width: Video width in pixels (default 720)
        height: Video height in pixels (default 480)
        frames: Number of frames (default 49, ≈6s at 8fps)
        fps: Output frames per second (default 8)
        steps: Diffusion inference steps (default 20)
        model: ComfyUI checkpoint filename (default cogvideox_5b.safetensors)
        seed: Random seed, -1 for random
    """
    if seed == -1:
        seed = int(time.time() * 1000) % (2**32)

    workflow = json.loads(json.dumps(_VIDEO_WORKFLOW))
    workflow["1"]["inputs"]["ckpt_name"] = model
    workflow["2"]["inputs"]["text"] = prompt
    workflow["3"]["inputs"]["width"] = width
    workflow["3"]["inputs"]["height"] = height
    workflow["3"]["inputs"]["video_frames"] = frames
    workflow["4"]["inputs"]["noise_seed"] = seed
    workflow["4"]["inputs"]["steps"] = steps
    workflow["6"]["inputs"]["fps"] = fps

    client_id = str(uuid.uuid4())

    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            resp = await client.post(
                f"{COMFYUI_URL}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.HTTPStatusError) as e:
            return {
                "success": False,
                "error": (
                    f"ComfyUI not available at {COMFYUI_URL}: {e}. "
                    "Install a video model via ComfyUI Manager (CogVideoX, Wan2.1, or Mochi)."
                ),
            }

        prompt_id = resp.json()["prompt_id"]

        # Poll for completion (video generation takes 2–10 minutes)
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
                        return {
                            "success": True,
                            "filename": filename,
                            "url": f"{COMFYUI_URL}/view?filename={filename}&type=output",
                            "prompt": prompt,
                            "seed": seed,
                            "frames": frames,
                            "fps": fps,
                        }
                return {
                    "success": False,
                    "error": "Generation completed but no video output found. Check ComfyUI logs.",
                }

    return {"success": False, "error": "Video generation timed out after 10 minutes"}


@mcp.tool()
async def list_video_models() -> list[str]:
    """List available video model checkpoints in ComfyUI."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{COMFYUI_URL}/object_info/CheckpointLoaderSimple")
            data = resp.json()
            checkpoints: list[str] = (
                data.get("CheckpointLoaderSimple", {})
                .get("input", {})
                .get("required", {})
                .get("ckpt_name", [[]])[0]
            )
            # Filter to likely video models by common name patterns
            video_keywords = ("cogvideo", "mochi", "wan2", "wan_2", "video")
            video_models = [c for c in checkpoints if any(k in c.lower() for k in video_keywords)]
            return video_models if video_models else checkpoints
        except Exception as e:
            return [f"Error listing models: {e}"]


if __name__ == "__main__":
    port = int(os.getenv("VIDEO_MCP_PORT", "8911"))
    mcp.run(transport="streamable-http", port=port)
