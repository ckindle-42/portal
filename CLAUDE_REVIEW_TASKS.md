# Code Agent Task List - Portal Review Issues

## Issues Identified

### 1. ~~**HIGH PRIORITY: ComfyUI MCP Health Check Endpoint**~~
- ~~**File**: `portal_mcp/generation/comfyui_mcp.py`~~
- ~~**Issue**: ComfyUI MCP may not have a `/health` endpoint configured~~
- ~~**Task**: Verify health check works at port 8910, add `/health` endpoint if missing~~
- **Status**: FIXED - Added /health endpoints to all 7 MCP servers

### 2. **HIGH PRIORITY: Video MCP Backend Dependency**
- **File**: `portal_mcp/generation/video_mcp.py`
- **Issue**: Video generation requires ComfyUI running with Wan2.2/CogVideoX workflows
- **Task**: Document that ComfyUI must be running, verify workflow paths exist

### 2b. **HIGH PRIORITY: Music/Whisper MCP require MLX on Apple Silicon**
- **Files**: `portal_mcp/generation/music_mcp.py`, `portal_mcp/generation/whisper_mcp.py`
- **Issue**: Audio generation and transcription require MLX on Apple Silicon
- **Task**: Ensure ENABLE_MLX=true in .env for M4 Mac

### 3. **MEDIUM PRIORITY: TTS MCP Voice Cloning**
- **File**: `portal_mcp/generation/tts_mcp.py`
- **Issue**: Voice cloning requires reference audio files
- **Task**: Create sample reference audio files or document expected format/location

### 4. **MEDIUM PRIORITY: Shell Safety Tool**
- **File**: `src/portal/tools/automation_tools/shell_safety.py`
- **Issue**: Shell commands are disabled by default (allowed_commands empty)
- **Task**: Either configure a safe whitelist or document how to enable

### 5. **MEDIUM PRIORITY: Docker Sandbox**
- **File**: `src/portal/security/sandbox/docker_sandbox.py`
- **Issue**: Sandbox is disabled by default (`sandbox_enabled: false`)
- **Task**: Document how to enable Docker sandbox for code execution

### 6. **LOW PRIORITY: Scrapling MCP Optional**
- **File**: `portal_mcp/scrapling/launch_scrapling.sh`
- **Issue**: Scrapling is optional but not documented
- **Task**: Add documentation for enabling web research

### 7. **LOW PRIORITY: External MCP Servers**
- **File**: `portal_mcp/core/mcp_servers.json`
- **Issue**: Filesystem and fetch MCP servers require external packages (`mcp-filesystem`, `mcp-fetch`)
- **Task**: Document installation requirements or remove if not supported

### 8. **CONFIG: Missing Environment Variables**
- **Issue**: Multiple services use env vars without defaults
- **Task**: Ensure `.env.example` is complete with all required variables

---

## Verification Tasks (Run These First)

```bash
# 1. Check all tools load correctly
cd /Users/chris/portal
python -c "from portal.tools import ToolRegistry; tr = ToolRegistry(); loaded, failed = tr.discover_and_load(); print(f'Loaded: {loaded}, Failed: {failed}')"

# 2. Run the doctor command
./hardware/m4-mac/launch.sh doctor

# 3. Check MCP servers are responding
curl -s http://localhost:8910/health || echo "comfyui-mcp not responding"
curl -s http://localhost:8911/health || echo "video-mcp not responding"
curl -s http://localhost:8912/health || echo "music-mcp not responding"
curl -s http://localhost:8913/health || echo "documents-mcp not responding"
curl -s http://localhost:8915/health || echo "whisper-mcp not responding"
curl -s http://localhost:8916/health || echo "tts-mcp not responding"
```

## Priority Order

1. Run doctor checks to identify actual issues
2. Fix any MCP servers not responding
3. Configure shell_safety if shell commands needed
4. Enable sandbox if code execution needed
5. Document feature requirements