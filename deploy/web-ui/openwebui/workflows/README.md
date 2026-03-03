# ComfyUI Workflow Exports for Open WebUI

This directory contains pre-built ComfyUI workflow definitions in API format for use with Open WebUI's image generation feature.

## Files

- `flux_schnell_api.json` - FLUX Schnell image generation (fast, 4-step)
- `sdxl_api.json` - SDXL 1.0 image generation (quality)
- `wan22_video_api.json` - Wan2.2 video generation (M4 optimized)

## Node ID Mappings

### FLUX Schnell (flux_schnell_api.json)
| Node ID | Type | Description |
|---------|------|-------------|
| 1 | CheckpointLoaderSimple | Load FLUX model |
| 2 | CLIPTextEncode | Positive prompt |
| 3 | CLIPTextEncode | Negative prompt |
| 8 | EmptyLatentImage | Latent dimensions (512x512 default) |
| 9 | KSampler | Sampling settings |
| 10 | VAEDecode | Decode latent to image |
| 11 | SaveImage | Output filename |

### SDXL (sdxl_api.json)
| Node ID | Type | Description |
|---------|------|-------------|
| 1 | CheckpointLoader | Load SDXL model |
| 2 | CLIPTextEncode | Positive prompt |
| 3 | CLIPTextEncode | Negative prompt |
| 4 | EmptyLatentImage | Latent (1024x1024) |
| 5 | KSampler | Sampling (20 steps) |
| 6 | VAEDecode | Decode to image |
| 7 | SaveImage | Output filename |

### Wan2.2 Video (wan22_video_api.json)
| Node ID | Type | Description |
|---------|------|-------------|
| 1 | CheckpointLoader | Load Wan2.2 model |
| 2 | CLIPTextEncode | Video prompt |
| 3 | CLIPTextEncode | Negative prompt |
| 4 | EmptyVideoLatent | Video latent (16 frames, 720p) |
| 5 | KSampler | Video sampling (30 steps) |
| 6 | VideoDecode | Decode to video |
| 7 | SaveVideo | Output .mp4 |

## Usage in Open WebUI

1. Start ComfyUI with API enabled (`python main.py --api`)
2. In Open WebUI: Admin > Settings > Images
3. Upload the workflow JSON file
4. Map node IDs if prompted (use values from tables above)
5. Test with a prompt like "a beautiful sunset"

## Customization

Edit the JSON files to:
- Change default dimensions
- Adjust sampling steps
- Modify model filenames
- Add LoRA loaders

After editing, re-upload to Open WebUI.
