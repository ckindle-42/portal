"""
ComfyUI MCP Server
Wraps the ComfyUI workflow API as MCP tools.
Exposes: generate_image, list_workflows, get_generation_status

Requires: ComfyUI running at COMFYUI_URL (default :8188)
Start with: python -m mcp.generation.comfyui_mcp
"""
import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("comfyui-generation")

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://localhost:8188")
OUTPUT_DIR = Path.home() / "AI_Output" / "images"

# Default FLUX.1-schnell workflow template
FLUX_WORKFLOW = {
    "6": {"inputs": {"text": "", "clip": ["30", 1]}, "class_type": "CLIPTextEncode"},
    "8": {"inputs": {"samples": ["31", 0], "vae": ["30", 2]}, "class_type": "VAEDecode"},
    "9": {"inputs": {"filename_prefix": "portal_", "images": ["8", 0]}, "class_type": "SaveImage"},
    "27": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}, "class_type": "EmptySD3LatentImage"},
    "30": {"inputs": {"ckpt_name": "flux1-schnell.safetensors"}, "class_type": "CheckpointLoaderSimple"},
    "31": {"inputs": {
        "model": ["30", 0], "conditioning": ["6", 0], "latent_image": ["27", 0],
        "noise_seed": 42, "steps": 4, "cfg": 1, "sampler_name": "euler",
        "scheduler": "simple", "denoise": 1,
    }, "class_type": "KSampler"},
}


@mcp.tool()
async def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    seed: int = -1,
) -> dict:
    """
    Generate an image using FLUX.1-schnell via ComfyUI.
    Returns a URL to the generated image file.

    Args:
        prompt: Text description of the image to generate
        width: Image width in pixels (default 1024)
        height: Image height in pixels (default 1024)
        steps: Number of diffusion steps (default 4, range 1-20)
        seed: Random seed, -1 for random
    """
    if seed == -1:
        seed = int(time.time() * 1000) % (2**32)

    workflow = json.loads(json.dumps(FLUX_WORKFLOW))  # deep copy
    workflow["6"]["inputs"]["text"] = prompt
    workflow["27"]["inputs"]["width"] = width
    workflow["27"]["inputs"]["height"] = height
    workflow["31"]["inputs"]["noise_seed"] = seed
    workflow["31"]["inputs"]["steps"] = min(max(steps, 1), 20)

    client_id = str(uuid.uuid4())

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Queue the prompt
        resp = await client.post(
            f"{COMFYUI_URL}/prompt",
            json={"prompt": workflow, "client_id": client_id},
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        # Poll for completion
        for _ in range(120):  # 120 × 1s = 2 min max
            await asyncio.sleep(1)
            history_resp = await client.get(f"{COMFYUI_URL}/history/{prompt_id}")
            history = history_resp.json()

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_id, node_output in outputs.items():
                    images = node_output.get("images", [])
                    if images:
                        filename = images[0]["filename"]
                        return {
                            "success": True,
                            "filename": filename,
                            "url": f"http://localhost:8080/images/{filename}",
                            "prompt": prompt,
                            "seed": seed,
                        }

        return {"success": False, "error": "Generation timed out after 2 minutes"}


@mcp.tool()
async def list_workflows() -> list[str]:
    """List available ComfyUI workflow checkpoints."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{COMFYUI_URL}/object_info/CheckpointLoaderSimple")
        data = resp.json()
        checkpoints = data.get("CheckpointLoaderSimple", {}) \
                         .get("input", {}) \
                         .get("required", {}) \
                         .get("ckpt_name", [[]])[0]
        return checkpoints


if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=int(os.getenv("COMFYUI_MCP_PORT", "8910")))
