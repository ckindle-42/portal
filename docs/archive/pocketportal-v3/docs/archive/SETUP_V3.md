# Quick Installation Guide - PocketPortal 4.1

**Deploy in 30 minutes** - Complete privacy-first AI agent

---

## ☑️ Prerequisites Check

Before starting, verify:

```bash
# 1. Python version
python3 --version
# Required: 3.11.x or 3.12.x

# 2. Disk space
df -h ~
# Required: 50GB+ free

# 3. Memory
sysctl hw.memsize  # macOS
# or
free -h  # Linux
# Required: 16GB+ (128GB recommended)
```

---

## 🚀 Installation Steps

### Step 1: Extract Bundle (1 min)
```bash
cd ~
tar -xzf telegram_agent_complete_bundle.tar.gz
cd telegram-agent
```

### Step 2: Run Setup Script (10-15 min)
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

This installs:
- Python virtual environment
- All Python dependencies
- Ollama (if not present)
- Default model (qwen2.5:7b)

### Step 3: Get Telegram Bot Token (2 min)
1. Open Telegram on your phone
2. Message **@BotFather**
3. Send: `/newbot`
4. Follow prompts (choose name and username)
5. **Copy the token** (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
6. Get your user ID from **@userinfobot**

### Step 4: Configure (2 min)
```bash
cp .env.example .env
nano .env  # or use: code .env, vim .env, etc.
```

Edit these two lines:
```bash
TELEGRAM_BOT_TOKEN=paste_your_token_here
TELEGRAM_USER_ID=paste_your_user_id_here
```

Save and exit (Ctrl+X, Y, Enter in nano)

### Step 5: Verify System (2 min)
```bash
source venv/bin/activate
python verify_system.py
```

Expected output:
```
✅ All 13 checks passed
System ready for deployment!
```

### Step 6: Start Agent (1 min)
```bash
python telegram_agent_v3.py
```

You should see:
```
INFO - Bot started successfully
INFO - Loaded 11 tools
INFO - Waiting for messages...
```

### Step 7: Test in Telegram (5 min)
Open Telegram and message your bot:

```
/start
→ Should welcome you

Hello!
→ Should respond conversationally

What's 2+2?
→ Should answer: 4

Generate a QR code for https://example.com
→ Should generate and send QR code image

Show system stats
→ Should display CPU, RAM, disk usage
```

---

## ✅ Success Checklist

Your installation succeeded if:
- [ ] `verify_system.py` shows all checks passed
- [ ] Agent starts without errors
- [ ] Telegram bot responds to messages
- [ ] QR code generates
- [ ] System stats display
- [ ] No error messages in terminal

---

## 🎯 What's Next?

### Option A: Use Immediately
Your agent is ready! You have:
- 11 core tools working
- Intelligent routing active
- Production-ready deployment

### Option B: Add MCP Integration (1-2 hours)
Add 400+ service connectors:
```bash
# Follow: docs/PART_6_MCP_INTEGRATION.md
pip install mcp==0.9.0
brew install node
# Configure authentication
```

### Option C: Complete Setup (8-10 hours)
Follow full deployment guide:
```bash
# Read: docs/DEPLOYMENT_GUIDE_MASTER_V3.1.md
# Follow: Parts 0-7 sequentially
```

---

## 🆘 Troubleshooting

### Issue: "python: command not found"
```bash
# Use python3 instead
python3 --version
# Update scripts to use python3
```

### Issue: "Ollama connection refused"
```bash
# Start Ollama
brew services start ollama

# Or on Linux
systemctl start ollama

# Verify
ollama list
```

### Issue: "No module named telegram"
```bash
source venv/bin/activate
pip install python-telegram-bot==20.7
```

### Issue: Bot doesn't respond
```bash
# Check bot token is correct
grep TELEGRAM_BOT_TOKEN .env

# Check user ID is correct
grep TELEGRAM_USER_ID .env

# Restart agent
python telegram_agent_v3.py
```

### More Help
See `docs/TROUBLESHOOTING.md` for comprehensive troubleshooting.

---

## 📊 Performance Tuning

### Recommended Models by Use Case

**Fast & Light (Default)**
```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
# ~5GB, 80 tokens/sec, good for most queries
```

**Balanced**
```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
# ~9GB, 45 tokens/sec, better reasoning
```

**High Quality**
```bash
ollama pull qwen2.5:32b-instruct-q4_K_M
# ~20GB, 25 tokens/sec, best quality
```

**Code Specialist**
```bash
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
# ~5GB, optimized for programming
```

Update `.env` to use different model:
```bash
OLLAMA_MODEL=qwen2.5:14b-instruct-q4_K_M
```

---

## 🔧 Production Deployment

### Auto-Start on Boot (macOS)
```bash
cp scripts/com_telegram_agent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com_telegram_agent.plist
```

### Auto-Start on Boot (Linux)
```bash
# Create systemd service
sudo nano /etc/systemd/system/telegram-agent.service

# Add:
[Unit]
Description=PocketPortal AI Agent
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/telegram-agent
ExecStart=/home/your_username/telegram-agent/venv/bin/python telegram_agent_v3.py
Restart=always

[Install]
WantedBy=multi-user.target

# Enable
sudo systemctl enable telegram-agent
sudo systemctl start telegram-agent
```

---

## 📈 Usage Examples

### Basic Queries
```
What's the weather like?
→ Responds conversationally

Calculate 15% tip on $87.50
→ Shows calculation

Explain quantum computing
→ Provides explanation
```

### Tool Usage
```
Create a QR code for wifi: SSID=MyNetwork, password=secret123
→ Generates WiFi QR code

Convert this JSON to YAML: {"name": "John", "age": 30}
→ Converts and returns YAML

Compress files in ~/Documents/reports as backup.zip
→ Creates compressed archive

Show me CPU and memory usage
→ Displays system stats
```

### Voice Messages
```
Send a voice message via Telegram
→ Agent transcribes and responds
```

---

## 🎓 Learning Path

### Week 1: Core Functionality
- Use basic tools (QR, text transform, etc.)
- Understand routing system
- Try different query types

### Week 2: Advanced Features
- Setup MCP integration
- Configure authentication
- Use Git and Docker tools

### Week 3: Customization
- Create custom tools
- Build workflows
- Optimize for your needs

### Week 4: Production
- Setup monitoring
- Configure backups
- Scale deployment

---

## 🎉 Congratulations!

You've successfully deployed a **privacy-first, production-grade AI agent**!

### What You Have
- ✅ Fully functional AI assistant
- ✅ 11 production-ready tools
- ✅ Intelligent routing (10-20x faster)
- ✅ 100% local processing
- ✅ No cloud dependencies
- ✅ Complete control over your data

### What You Can Do
- Answer questions conversationally
- Generate QR codes
- Process files
- Analyze data
- Execute commands safely
- Transcribe voice messages
- Monitor system resources
- And much more!

---

## 📚 Documentation

- **README.md** - This directory overview
- **docs/DEPLOYMENT_GUIDE_MASTER_V3.1.md** - Complete guide
- **docs/PART_0_QUICK_START.md** - Prerequisites
- **docs/PART_1_ROUTING_SYSTEM.md** - Routing setup
- **docs/TROUBLESHOOTING.md** - Problem solving

---

## 🚀 Ready for More?

### Add MCP Integration
**Adds 400+ service connectors**
```bash
# Follow: docs/PART_6_MCP_INTEGRATION.md
```

### Complete All Addons
**Adds Git, Docker, system tools**
```bash
# Follow: docs/PART_7_ADDON_TOOLS.md
```

### Build Custom Tools
**Extend for your needs**
```bash
# Use: scripts/generate_addon_tools.py
```

---

**Need help?** Check `docs/TROUBLESHOOTING.md` or review completed tool implementations as examples.

**Ready to customize?** Read `docs/TOOL_ADDONS_MASTER_PLAN.md` for extension strategies.

---

**Version:** 3.1.0  
**Install Time:** ~30 minutes  
**Difficulty:** Beginner-friendly  

**Welcome to your new AI assistant!** 🤖
