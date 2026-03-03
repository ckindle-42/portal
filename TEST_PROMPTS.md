# Portal Feature Test Prompts

This document provides test prompts for each feature across all available interfaces (Open WebUI, Telegram, Slack).

---

## 1. General Chat (All Interfaces)

### Test Basic Chat
```
Hello, how are you?
```
**Expected**: Friendly response from default model (auto)

### Test Workspace Selection via @model
**Open WebUI**: Select workspace from dropdown
**Telegram/Slack**:
```
@model:auto-coding What is 2+2?
@model:auto-reasoning What is 2+2?
```
**Expected**: Different models respond based on workspace

---

## 2. Image Generation (FLUX.1-schnell)

### Test Prompt (All Interfaces)
```
Create an orange cat sitting on a windowsill, photorealistic, sunny day
```
**Via Open WebUI**: Use auto-video workspace or describe image
**Via Telegram/Slack**:
```
@model:auto Create an image of an orange cat
```

### Test SDXL Alternative
```
Set IMAGE_BACKEND=sdxl and create a fantasy landscape
```

---

## 3. Video Generation

### Test Prompt (All Interfaces)
```
Create a video of ocean waves crashing on a beach, looped, 3 seconds
```

### Test Via Workspace
```
Use auto-video workspace to create a short animation of a bird flying
```

---

## 4. Music Generation

### Test Prompt (All Interfaces)
```
Compose a mystical, mythical beat with ethereal pads and drums
```

### Test Continuation
```
Continue this melody pattern: C4, E4, G4, B4
```

---

## 5. Text-to-Speech (TTS)

### Test Prompt (All Interfaces)
```
Speak this text: Hello, this is a test of the text to speech system
```

### Test Voice Selection
```
Speak using voice: female_zhang
Speak using voice: male_yun
```

### Test Voice Cloning
```
Clone voice from reference audio file at /path/to/reference.wav
Then speak: This is cloned voice
```

---

## 6. Audio Transcription (Whisper)

### Test Prompt
```
Transcribe the audio file at /path/to/audio.mp3
```

### Test With Language
```
Transcribe this audio file with language set to English
```

---

## 7. Document Generation

### Test Word Document
```
Create a Word document with a report about AI trends 2024
```

### Test PowerPoint
```
Create a presentation about machine learning basics, 5 slides
```

### Test Excel
```
Create an Excel spreadsheet with monthly sales data for Q1
```

### Test Workspace
```
Use auto-documents workspace to generate a quarterly report
```

---

## 8. Code Execution (Sandbox)

### Prerequisites
- Enable `SANDBOX_ENABLED=true` in `.env`
- Set `SANDBOX_MCP_PORT=8914`

### Test Python Code
```
Execute Python code that prints "Hello from sandbox"
```

### Test Node.js
```
Run Node.js code: console.log("Hello from Node")
```

---

## 9. Web Research (Scrapling)

### Prerequisites
- Enable MCP_ENABLED=true
- Scrapling MCP must be running on port 8900

### Test Web Search
```
Research the latest developments in quantum computing
```

### Test URL Fetch
```
Fetch and summarize https://example.com
```

---

## 10. Knowledge Base / RAG

### Test Add Knowledge
```
Remember that the project deadline is March 15, 2024
```

### Test Query Knowledge
```
What is the project deadline?
```

### Test Local Knowledge
```
Search the knowledge base for information about neural networks
```

---

## 11. Internal Tools Testing

### Data Tools

#### CSV Analyzer
```
Analyze the CSV file at /path/to/data.csv and give me statistics
```

#### QR Generator
```
Generate a QR code for https://example.com
```

#### Math Visualizer
```
Plot the function y = sin(x) from 0 to 2π
```

#### Text Transformer
```
Transform this text to ROT13: HELLO WORLD
```

### System Tools

#### System Stats
```
Show me the current system stats
```

#### Process Monitor
```
List the top 5 processes by CPU usage
```

#### Clipboard Manager
```
Read the current clipboard contents
```

### Docker Tools

#### Docker Status
```
List all running Docker containers
```

#### Docker Compose
```
Show the status of Docker Compose services
```

### Document Processing

#### PDF OCR
```
Extract text from /path/to/document.pdf
```

#### Word Processor
```
Read the document at /path/to/file.docx
```

#### Excel Processor
```
Read the spreadsheet at /path/to/data.xlsx and summarize
```

### Web Tools

#### HTTP Client
```
GET https://httpbin.org/get
```

### Git Tools

#### Git Status
```
What is the status of the git repository?
```

#### Git Log
```
Show me the last 5 commits
```

### Dev Tools

#### Python Env Manager
```
List installed Python packages in the current environment
```

### Automation Tools

#### Job Scheduler
```
Schedule a task to run every day at 9am
```

---

## 12. Multi-Step Orchestration

### Test Chain
```
First, get the system CPU usage. Then create a QR code containing that information.
```

### Test Complex Chain
```
Step 1: Search for information about climate change
Step 2: Summarize the findings
Step 3: Create a Word document with the summary
```

---

## 13. Security/Red Team Features

### Prerequisites
- Use `auto-security` workspace

### Test Prompt
```
Explain the concept of SQL injection for educational purposes
```

---

## Interface-Specific Tests

### Telegram-Specific

#### Inline Mode
```
@yourbot search for AI news
```

#### Group Chat (if enabled)
```
@yourbot What time is it?
```

#### File Upload
```
[Upload audio file] Transcribe this
```

### Slack-Specific

#### Direct Message
```
@portal What is 2+2?
```

#### Channel Message
```
@portal Summarize this document
```

#### File Upload
```
[Upload file] Analyze this
```

### Open WebUI-Specific

#### Image Upload
```
[Upload image] Describe what's in this image
```

#### Multimodal
```
[Upload image + text] What's in the image and what do you think about this?
```

---

## Workspace Selection Reference

| Workspace | Purpose | Default Model |
|-----------|---------|---------------|
| auto | General chat | dolphin-llama3:8b |
| auto-coding | Code generation | qwen3-coder-next:30b-q5 |
| auto-reasoning | Deep reasoning | tongyi-deepresearch:30b |
| auto-security | Security/Red team | xploiter/the-xploiter |
| auto-creative | Creative writing | dolphin-llama3:70b |
| auto-multimodal | Image/video understanding | qwen3-omni:30b |
| auto-fast | Quick responses | dolphin-llama3:8b |
| auto-documents | Document generation | qwen3-coder-next:30b-q5 |
| auto-video | Video generation | dolphin-llama3:8b |
| auto-music | Music generation | dolphin-llama3:8b |
| auto-research | Research/investigation | tongyi-deepresearch:30b |

---

## Quick Test Checklist

- [ ] Test basic chat on all 3 interfaces
- [ ] Test image generation (FLUX)
- [ ] Test video generation
- [ ] Test music generation
- [ ] Test TTS with voice selection
- [ ] Test Whisper transcription
- [ ] Test document creation (Word, PPT, Excel)
- [ ] Test code sandbox (if enabled)
- [ ] Test web research
- [ ] Test knowledge base
- [ ] Test internal tools (at least 3)
- [ ] Test multi-step orchestration
- [ ] Test workspace switching
- [ ] Test routing rules (security, coding, reasoning, etc.)