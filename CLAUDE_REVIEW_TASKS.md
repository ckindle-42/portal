# Code Agent Task List - Portal Review Issues

## Completed Items (Verified)

| ID | Issue | Status |
|----|-------|--------|
| 1 | ComfyUI MCP Health Check Endpoint | **FIXED** - All 9 MCP servers have /health and /tools endpoints |
| - | All env vars in .env.example | **FIXED** - VIDEO_BACKEND, IMAGE_BACKEND, TTS_BACKEND, etc. all present |

## Remaining Items

### 2. Video MCP Backend Dependency (MEDIUM)
- **File**: `mcp/generation/video_mcp.py`
- **Issue**: Video generation requires ComfyUI running with Wan2.2/CogVideoX workflows
- **Status**: Documented in PORTAL_HOW_IT_WORKS.md Section 5.4
- **Note**: Wan2.2 setup commands added to documentation

### 2b. Music/Whisper MLX Requirement (MEDIUM)
- **Files**: `mcp/generation/music_mcp.py`, `mcp/generation/whisper_mcp.py`
- **Issue**: Audio generation and transcription require MLX on Apple Silicon
- **Note**: ENABLE_MLX=true should be set in .env for M4 Mac

### 3. TTS MCP Voice Cloning (MEDIUM)
- **File**: `mcp/generation/tts_mcp.py`
- **Issue**: Voice cloning requires reference audio files
- **Status**: Documented in PORTAL_HOW_IT_WORKS.md Section 5.6

### 4. Shell Safety Tool (MEDIUM)
- **File**: `src/portal/tools/automation_tools/shell_safety.py`
- **Issue**: Shell commands are disabled by default (allowed_commands empty)
- **Status**: Documented - safe by design, configure whitelist if needed

### 5. Docker Sandbox (MEDIUM)
- **File**: `src/portal/security/sandbox/docker_sandbox.py`
- **Issue**: Sandbox is disabled by default (`sandbox_enabled: false`)
- **Status**: Documented in PORTAL_HOW_IT_WORKS.md Section 5.9

### 6. Scrapling MCP Optional (LOW)
- **File**: `mcp/scrapling/launch_scrapling.sh`
- **Issue**: Scrapling is optional but not documented
- **Status**: Documented in PORTAL_HOW_IT_WORKS.md Section 5.14

### 7. External MCP Servers (LOW)
- **File**: `mcp/core/mcp_servers.json`
- **Issue**: Filesystem and fetch MCP servers require external packages
- **Status**: Part of MCP configuration, documented in setup

---

## Verification Commands

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

---

*Last Updated: 2026-03-03 (post Phase 0-6 + personas + health endpoints + integration tests)*