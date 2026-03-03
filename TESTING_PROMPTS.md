# Portal Feature Testing Prompts

Comprehensive prompts to test each feature via each interface method (Open WebUI, Telegram, Slack).

---

## 1. Basic Chat / General Conversation

### Open WebUI
```
Hello! What's the current time?
```

### Telegram
```
/start
Hello! What's the current time?
```

### Slack
```
@portal Hello! What's the current time?
```

---

## 2. Image Generation

### Open WebUI
```
Generate an image of an orange cat sitting on a windowsill
```

### Telegram
```
Generate an image of an orange cat sitting on a windowsill
```

### Slack
```
@portal Generate an image of an orange cat sitting on a windowsill
```

**Expected:** Returns image file path from ComfyUI MCP

---

## 3. Video Generation

### Open WebUI
```
Create a video of a mythical dragon flying over mountains
```

### Telegram
```
Create a video of a mythical dragon flying over mountains
```

### Slack
```
@portal Create a video of a mythical dragon flying over mountains
```

**Expected:** Returns video file path from Video MCP (Wan2.2/CogVideoX)

---

## 4. Music/Audio Generation

### Open WebUI
```
Generate a mythical beat with epic orchestral sounds
Create a relaxing lo-fi music track
```

### Telegram
```
Generate a mythical beat with epic orchestral sounds
```

### Slack
```
@portal Generate a mythical beat with epic orchestral sounds
```

**Expected:** Returns audio file from Music MCP

---

## 5. Text-to-Speech (TTS)

### Open WebUI
```
Speak this message: Hello, I am your AI assistant
Create a Chinese TTS message: 你好世界
Create a Japanese TTS message: こんにちは世界
```

### Telegram
```
Speak: Hello, I am your AI assistant
中文: 你好
日本語: こんにちは
```

### Slack
```
@portal Speak: Hello, I am your AI assistant
```

**Expected:** Returns audio file from TTS MCP (CosyVoice2)

---

## 6. Audio Transcription

### Open WebUI
```
Transcribe the audio file at /path/to/audio.mp3
```

### Telegram
```
Transcribe this audio [send audio file]
```

### Slack
```
@portal Transcribe [upload audio file]
```

**Expected:** Returns transcribed text from Whisper MCP

---

## 7. Code Execution (via Code Sandbox)

### Open WebUI
```
Write a Python function to calculate fibonacci numbers and execute it
```

### Telegram
```
Execute: print("Hello from code sandbox")
```

### Slack
```
@portal Run this Python code:
print("Hello from code sandbox")
```

**Expected:** Returns execution result from Code Sandbox MCP

---

## 8. Git Operations

### Open WebUI
```
Show me git status of /path/to/repo
Show git log with 5 entries for /path/to/repo
```

### Telegram
```
git status /path/to/repo
git log 5 /path/to/repo
```

### Slack
```
@portal git status /path/to/repo
@portal git log 5 /path/to/repo
```

**Expected:** Returns git command output

---

## 9. System Stats

### Open WebUI
```
Show me system stats
What is the current CPU and memory usage?
```

### Telegram
```
system stats
cpu usage
```

### Slack
```
@portal system stats
@portal CPU and memory usage
```

**Expected:** Returns CPU, memory, disk, temperature info

---

## 10. Document Processing (PDF/Word/Excel)

### Open WebUI
```
Extract text from this PDF: /path/to/document.pdf
Analyze this Excel file: /path/to/spreadsheet.xlsx
```

### Telegram
```
Extract text from [upload PDF]
Analyze [upload Excel]
```

### Slack
```
@portal Extract text from [upload PDF]
```

**Expected:** Returns extracted text/data from Document MCP

---

## 11. QR Code Generation

### Open WebUI
```
Generate a QR code for https://example.com
```

### Telegram
```
QR code for https://example.com
```

### Slack
```
@portal Generate QR code: https://example.com
```

**Expected:** Returns QR code image

---

## 12. File Compression

### Open WebUI
```
Compress these files into a ZIP: file1.txt, file2.txt
```

### Telegram
```
compress file1.txt file2.txt
```

### Slack
```
@portal Compress: file1.txt, file2.txt
```

**Expected:** Returns compressed archive

---

## 13. Math Visualization

### Open WebUI
```
Plot the function y = sin(x)
Graph the equation y = x^2
```

### Telegram
```
plot sin(x)
graph y = x^2
```

### Slack
```
@portal Plot y = sin(x)
```

**Expected:** Returns graph/plot image

---

## 14. Web HTTP Client

### Open WebUI
```
GET request to https://httpbin.org/get
POST to https://httpbin.org/post with JSON {"test": "value"}
```

### Telegram
```
GET https://httpbin.org/get
POST https://httpbin.org/post {"test": "value"}
```

### Slack
```
@portal GET https://httpbin.org/get
```

**Expected:** Returns HTTP response

---

## 15. Docker Tools

### Open WebUI
```
List running Docker containers
Show logs for container my-app
```

### Telegram
```
docker ps
docker logs my-app
```

### Slack
```
@portal docker ps
@portal docker logs my-app
```

**Expected:** Returns Docker command output

---

## 16. Knowledge Base / Local Knowledge

### Open WebUI
```
Search my knowledge base for information about Python
Add this to my knowledge base: Python is a programming language
```

### Telegram
```
search knowledge Python
add: Python is a programming language
```

### Slack
```
@portal search knowledge Python
@portal add: Python is great
```

**Expected:** Returns search results or confirmation

---

## 17. Task Scheduling

### Open WebUI
```
Schedule a task to run every Monday at 9am
List all scheduled tasks
```

### Telegram
```
schedule: backup every day at midnight
list schedules
```

### Slack
```
@portal Schedule daily backup
@portal list schedules
```

**Expected:** Returns schedule info or confirmation

---

## 18. Process Monitor

### Open WebUI
```
Show running processes
Kill process with PID 12345
```

### Telegram
```
process list
kill 12345
```

### Slack
```
@portal process list
@portal kill 12345
```

**Expected:** Returns process list or confirmation

---

## 19. Clipboard Manager

### Open WebUI
```
Copy "Hello World" to clipboard
Show clipboard contents
```

### Telegram
```
copy to clipboard: test message
show clipboard
```

### Slack
```
@portal copy: test message
@portal clipboard
```

**Expected:** Returns clipboard content

---

## 20. Persona Selection

### Open WebUI
```
Use the Code Reviewer persona to review this code: [paste code]
Act as a Linux terminal and run: ls -la
```

### Telegram
```
@code-reviewer [paste code]
@linux ls -la
```

### Slack
```
@portal act as DataAnalyst: analyze this data
```

**Expected:** Uses selected persona system prompt

---

## 21. Multi-step Orchestration

### Open WebUI
```
Step 1: Generate an image of a cat
Step 2: Transcribe this audio file
Then create a video from the results
```

### Telegram
```
first generate image of cat then show system stats
do both: list processes and show disk usage
```

### Slack
```
@portal first generate image of cat, then show system stats
```

**Expected:** Executes multiple steps in sequence using TaskOrchestrator

---

## 22. Rate Limiting

### Open WebUI
```
Send 25 rapid requests in 1 minute
```

### Telegram
```
[Send 25 messages rapidly]
```

### Slack
```
[Send 25 messages rapidly]
```

**Expected:** Returns 429 Too Many Requests after limit exceeded

---

## 23. Model Selection / Routing

### Open WebUI
```
Use the reasoning model to solve this logic puzzle: [puzzle]
Use the creative model to write a poem about AI
```

### Telegram
```
@reasoning solve: [puzzle]
@creative write poem
```

### Slack
```
@portal reasoning: [puzzle]
@portal creative: write poem
```

**Expected:** Routes to appropriate model (qwen2.5, llama3.3, etc.)

---

## 24. Health Check

### Open WebUI
```
GET /health
GET /health/live
GET /health/ready
```

### Telegram
```
/health
```

### Slack
```
@portal health status
```

**Expected:** Returns health status with component details

---

## 25. Metrics

### Open WebUI
```
curl http://localhost:8081/metrics
```

**Expected:** Returns Prometheus metrics (TOKENS_PER_SECOND, TTFT_MS, etc.)

---

## 26. File Upload/Download

### Open WebUI
```
Upload a PDF file via /v1/files endpoint
Download the file: my-document.pdf
```

### Telegram
```
[Upload file to chat]
```

### Slack
```
[Upload file to chat]
```

**Expected:** File stored and accessible

---

## 27. Context/Memory

### Open WebUI
```
Remember that my favorite color is blue
What is my favorite color?
```

### Telegram
```
Remember: my name is John
What's my name?
```

### Slack
```
@portal Remember: I prefer dark mode
What do you know about my preferences?
```

**Expected:** Stores and retrieves from MemoryManager

---

## 28. Error Handling

### Open WebUI
```
Generate a video with invalid parameters
Execute code with syntax error
```

### Telegram
```
invalid command xyz
broken request
```

### Slack
```
@portal invalid request xyz
```

**Expected:** Returns proper error message with details

---

## 29. Tool Confirmation (HITL)

### Open WebUI
```
Execute a high-risk shell command: rm -rf /
```

### Telegram
```
run dangerous command
```

### Slack
```
@portal run shell: rm -rf /
```

**Expected:** Triggers human-in-the-loop approval workflow (if enabled)

---

## 30. Streaming Response

### Open WebUI
```
Write a long story about a magical kingdom
[Check streaming response]
```

### Telegram
```
Tell me a long story
```

### Slack
```
@portal Tell me a long story
```

**Expected:** Response streams token by token via SSE

---

## Testing Matrix

| Feature | Open WebUI | Telegram | Slack |
|---------|------------|----------|-------|
| Basic Chat | ✅ | ✅ | ✅ |
| Image Gen | ✅ | ✅ | ✅ |
| Video Gen | ✅ | ✅ | ✅ |
| Music Gen | ✅ | ✅ | ✅ |
| TTS | ✅ | ✅ | ✅ |
| Transcription | ✅ | ✅ | ✅ |
| Code Exec | ✅ | ✅ | ✅ |
| Git Ops | ✅ | ✅ | ✅ |
| System Stats | ✅ | ✅ | ✅ |
| Documents | ✅ | ✅ | ✅ |
| QR Code | ✅ | ✅ | ✅ |
| Compression | ✅ | ✅ | ✅ |
| Math Plot | ✅ | ✅ | ✅ |
| HTTP Client | ✅ | ✅ | ✅ |
| Docker | ✅ | ✅ | ✅ |
| Knowledge | ✅ | ✅ | ✅ |
| Scheduling | ✅ | ✅ | ✅ |
| Processes | ✅ | ✅ | ✅ |
| Clipboard | ✅ | ✅ | ✅ |
| Personas | ✅ | ✅ | ✅ |
| Orchestration | ✅ | ✅ | ✅ |
| Rate Limit | ✅ | ✅ | ✅ |
| Routing | ✅ | ✅ | ✅ |
| Health | ✅ | ✅ | ✅ |
| Metrics | ✅ | ❌ | ❌ |
| File Upload | ✅ | ✅ | ✅ |
| Memory | ✅ | ✅ | ✅ |
| Streaming | ✅ | ✅ | ✅ |

---

## MCP Server Health Verification

```bash
# Check all MCP servers are healthy
curl http://localhost:8081/health | jq '.mcp_servers'

# Individual MCP checks
curl http://localhost:8000/comfyui/health  # Image
curl http://localhost:8000/video/health   # Video
curl http://localhost:8000/music/health   # Music
curl http://localhost:8000/tts/health      # TTS
curl http://localhost:8000/whisper/health # Transcription
curl http://localhost:8000/code-sandbox/health # Code
curl http://localhost:8000/documents/health # Documents
```

---

## Key Test Scenarios for Video Generation

Since the user specifically mentioned "create a video of a orange cat" and "create a beat that is mythical":

### Orange Cat Video
```
Generate a video of an orange cat playing with a ball of yarn
Create video: orange cat running in a garden
```

### Mythical Beat
```
Create a mythical beat with drums and synths
Generate an epic fantasy music track
Make a mythical orchestral beat
```

### Keylogger (Educational/Diagnostic)
*Note: Only for legitimate security testing with explicit authorization*

```
Monitor keyboard input for diagnostic purposes (security research)
Show all active keyboard event listeners
```

---

## Quick Smoke Test Commands

```bash
# 1. Health check
curl http://localhost:8081/health

# 2. List models
curl http://localhost:8081/v1/models

# 3. List personas
curl http://localhost:8081/v1/personas

# 4. List tools
curl http://localhost:8081/tools

# 5. Basic chat
curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "auto", "messages": [{"role": "user", "content": "Hello"}]}'

# 6. Streaming chat
curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "auto", "messages": [{"role": "user", "content": "Hello"}], "stream": true}'
```
