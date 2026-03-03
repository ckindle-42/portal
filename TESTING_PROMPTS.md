# Portal Test Prompts - Every Feature, Every Interface

For Telegram prefix with @model:workspace-name. For Slack @portal then @model:workspace-name. For Open WebUI select workspace from dropdown.

## 1. Text Chat (auto)
Web: What are the three laws of thermodynamics?
Telegram: What are the three laws of thermodynamics?
Slack: @portal What are the three laws of thermodynamics?

## 2. Code (auto-coding)
Web: Write a Python FastAPI endpoint validating JSON with Pydantic
Web auto: Write a Python function returning top 3 frequent list elements
Telegram: @model:auto-coding Write bash disk monitor alerting at 90%
Slack: @portal @model:auto-coding Debug: def fib(n): return fib(n-1) + fib(n-2)

## 3. Image (needs ComfyUI)
Web: Generate an image of an orange cat on a windowsill watching rain
Web: Create photorealistic cyberpunk city at night with neon
Telegram: Generate an image of a medieval castle at sunset
Slack: @portal Generate an image of a robot reading a book

## 4. Video (auto-video, needs ComfyUI+Wan2.2)
Web: Create a video of an orange cat chasing a butterfly in a garden
Web: Generate video of ocean waves on rocky cliffs at golden hour
Telegram: @model:auto-video Create video of dragon flying over mountains
Slack: @portal @model:auto-video Create video of fireworks over city

## 5. Music (auto-music, needs AudioCraft)
Web: Create a beat that is mythical - epic orchestral tribal drums ethereal choir
Web: Compose 10-second upbeat jazz piano solo with walking bass
Web: Generate dark ambient electronic with deep bass atmospheric pads
Telegram: @model:auto-music Compose lo-fi hip hop with vinyl crackle
Slack: @portal @model:auto-music Create cinematic orchestral building tension

## 6. TTS (needs Fish Speech)
Web: Speak aloud: Welcome to Portal. All AI runs locally.
Telegram: Say out loud: Portal is your private AI assistant
Slack: @portal Speak: All your models are belong to us

## 7. Documents (auto-documents)
Web: Create Word doc Project Status Report with Summary Progress Risks
Web: Create PowerPoint AI security 5 slides
Web: Create Excel monthly expenses Date Category Description Amount
Telegram: @model:auto-documents Create Word doc on cybersecurity frameworks
Slack: @portal @model:auto-documents Create DevOps presentation

## 8. Code Sandbox (needs Docker)
Web: Run Python: print(sum(range(100)))
Web: Execute: import math; print(math.factorial(20))

## 9. Red Team (auto-security)
Web: Write Kerberoasting attack chain for AD targeting domain admin
Web: Generate Python reverse shell evading AV with process hollowing
Web: Code a keylogger in Python for authorized security testing
Web: Create pentest report template for web app
Web auto: Write a reverse shell exploit (auto-routes via regex)
Telegram: @model:auto-security Explain LLMNR poisoning and relay attacks
Slack: @portal @model:auto-security Write YARA rule for Cobalt Strike beacons

## 10. Blue Team (routes via regex)
Web: Write Splunk SPL brute force detection 5+ failed logins same IP 10 min
Web auto: Create Sigma rule detecting mimikatz (routes via keyword)
Web auto: Write Splunk tstats query notable events last 24h by source
Telegram: @model:auto-reasoning Threat hunt hypothesis Splunk query PsExec lateral
Slack: @portal Create YARA rule encoded PowerShell network traffic

## 11. Creative (auto-creative)
Web: Write dark fantasy necromancer discovers healing powers atmospheric complex
Web: Write hardboiled detective noir cyberpunk vivid dialogue
Web auto: Write creative fantasy about dragon librarian (auto-routes)
Telegram: @model:auto-creative Write haiku about code at midnight
Slack: @portal @model:auto-creative Write limerick sysadmin never sleeps

## 12. Reasoning (auto-reasoning/auto-research)
Web: Analyze zero-trust vs perimeter security pros cons
Web: Deep research OT network security in energy sector
Web auto: Explain step by step why transformers replaced RNNs (routes via regex)
Telegram: @model:auto-reasoning Compare NERC CIP v6 vs v7 implications

## 13. Web Research (needs internet)
Web: Research latest Log4j CVEs 2025-2026
Web: Latest MCP protocol specification updates?
Telegram: Current Bitcoin price?

## 14. Orchestration (explicit structure only)
TRIGGER: Step 1: Research quantum computing. Step 2: Create summary document.
TRIGGER: 1) Write Fibonacci 2) Create tests 3) Document API
NO TRIGGER: Write a function that generates CSV data
NO TRIGGER: First let me explain quantum computing

## 15. Multimodal (auto-multimodal, needs qwen3-omni)
Web: [upload image] Describe in detail
Telegram: @model:auto-multimodal [photo] What is this?

## 16. Personas (select dropdown)
cybersecurityspecialist: Review network for security gaps
codereviewer: Review code for bugs [paste]
linuxterminal: ls -la /var/log

## 17. Health
curl http://localhost:8081/health
curl http://localhost:8081/v1/models
curl http://localhost:8081/v1/files
curl http://localhost:8081/metrics
curl http://localhost:8911/health (video)
curl http://localhost:8912/health (music)
curl http://localhost:8913/health (docs)
curl http://localhost:8916/health (tts)
bash launch.sh doctor

## 18. Telegram Commands
/start /help /tools /stats /health

## 19. Model Override
Telegram: @model:auto-creative Write sonnet about code
Telegram: @model:auto-security Write Metasploit module
Slack: @portal @model:auto-coding Write Dockerfile for FastAPI

## Smoke Test
curl -s http://localhost:8081/health | python3 -m json.tool
curl -s http://localhost:8081/v1/models | python3 -m json.tool | head -50
curl -s localhost:8081/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"auto","messages":[{"role":"user","content":"hello"}]}'
curl -s http://localhost:8081/v1/files | python3 -m json.tool
for port in 8910 8911 8912 8913 8915 8916; do echo -n "Port $port: "; curl -s http://localhost:$port/health || echo "NOT RUNNING"; done
bash launch.sh doctor