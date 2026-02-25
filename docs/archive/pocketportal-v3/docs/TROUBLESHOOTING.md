# Troubleshooting Guide

Quick solutions to common issues.

---

## Bot Issues

### Bot not responding
```bash
# Check process
ps aux | grep telegram_agent

# Check logs
tail -50 logs/agent.log

# Restart
pkill -f telegram_agent_v3.py
source venv/bin/activate
python telegram_agent_v3.py
```

### "Unauthorized" errors
- Verify `TELEGRAM_USER_ID` in `.env` matches your ID
- Get your ID: Message @userinfobot on Telegram

### Rate limited
```bash
# Increase limits in .env
RATE_LIMIT_MESSAGES=50
RATE_LIMIT_WINDOW=60
```

---

## Ollama Issues

### Ollama not running
```bash
# Start Ollama
ollama serve

# Check status
curl http://localhost:11434/api/tags
```

### Model not found
```bash
# List models
ollama list

# Pull required model
ollama pull qwen2.5:7b
ollama pull llava:7b  # for vision
```

### Slow responses
```bash
# Use smaller model for simple tasks
FAST_MODEL=qwen2.5:0.5b

# Check GPU usage
sudo powermetrics --samplers gpu_power
```

---

## Tool Issues

### Tools not loading
```bash
# Check tool discovery
python -c "from telegram_agent_tools import registry; print(registry.discover_and_load())"

# View failed tools
python -c "from telegram_agent_tools import registry; registry.discover_and_load(); print(registry.failed_tools)"
```

### Browser tool fails
```bash
# Install Playwright browsers
playwright install chromium

# Test browser
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); print('OK'); b.close(); p.stop()"
```

### Whisper fails
```bash
# Check backend
pip show faster-whisper

# Test transcription
python -c "from faster_whisper import WhisperModel; m = WhisperModel('base'); print('OK')"
```

---

## Configuration Issues

### Invalid config
```bash
# Validate configuration
python -c "from config_validator import load_and_validate_config; print(load_and_validate_config())"
```

### Missing .env
```bash
cp .env.example .env
# Edit with your values
nano .env
```

---

## macOS Issues

### LaunchAgent not starting
```bash
# Check plist
launchctl list | grep telegram

# View errors
cat ~/telegram_agent_v3/logs/launchd_error.log

# Reload
launchctl unload ~/Library/LaunchAgents/com.telegram.agent.plist
launchctl load ~/Library/LaunchAgents/com.telegram.agent.plist
```

### File limit errors
```bash
# Increase limits
ulimit -n 10240

# Make persistent (add to ~/.zshrc)
echo "ulimit -n 10240" >> ~/.zshrc
```

---

## Verification

Run full system check:
```bash
python verify_system.py
```

Expected output:
```
âœ“ Python version: 3.11.x
âœ“ Ollama running: localhost:11434
âœ“ Models available: 5+
âœ“ Tools registered: 11
âœ“ Security module: OK
âœ“ Configuration: Valid
```
