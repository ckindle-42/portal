# Portal — Model Expansion & Uncensored Routing Action Prompt
# Target: Replace censored defaults with abliterated/uncensored model stack
# Generated: 2026-03-01 | Based on Portal v1.4.5 (commit latest on main)

---

## Project Context

Portal is a local-first AI platform (Python 3.11 / FastAPI / async) at v1.4.5. The routing stack consists of 6 files that must be updated in coordination:

| File | What it does |
|------|-------------|
| `src/portal/routing/model_registry.py` | `ModelCapability` enum + `ModelMetadata` dataclass + `ModelRegistry` class |
| `src/portal/routing/default_models.json` | Static model catalog (loaded at registry init) |
| `src/portal/routing/task_classifier.py` | `TaskCategory` enum + regex pattern matching for <10ms classification |
| `src/portal/routing/llm_classifier.py` | `LLMCategory` enum + Ollama-based classification with regex fallback |
| `src/portal/routing/router_rules.json` | Default/warm models, workspace configs, classifier categories, regex rules |
| `src/portal/routing/intelligent_router.py` | Strategy-based routing using both classifiers + model registry |

**Non-negotiable:** OpenAI-compatible API contract unchanged. No external cloud deps. All models must run locally via Ollama.

---

## Session Bootstrap — Run Before Any Task

```bash
cd portal  # or wherever the repo is
source .venv/bin/activate 2>/dev/null || { python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[all,dev,test]"; }
python3 -c "import portal; print('OK')"
make ci  # or: ruff check src/ tests/ && mypy src/portal && pytest tests/ -v --tb=short
```

Do not start TASK-1 until baseline is green.

---

## TASK-1: Expand ModelCapability enum
Tier: 1
File: `src/portal/routing/model_registry.py`
Lines: 15-24

**Current:**
```python
class ModelCapability(Enum):
    GENERAL = "general"
    CODE = "code"
    MATH = "math"
    REASONING = "reasoning"
    SPEED = "speed"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
```

**Action:** Add new capabilities:
```python
class ModelCapability(Enum):
    GENERAL = "general"
    CODE = "code"
    MATH = "math"
    REASONING = "reasoning"
    SPEED = "speed"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    SECURITY = "security"           # Red team, exploit gen, pentest, blue team
    CREATIVE = "creative"           # Stories, roleplay, uncensored creative writing
    IMAGE_GENERATION = "image_generation"  # Flux/mflux prompt routing
    AUDIO = "audio"                 # TTS, voice clone, sound effects
    MULTIMODAL = "multimodal"       # Native text/image/audio/video reasoning
```

**Risk:** LOW — additive change, existing code only references existing enum values.
**Parity:** Existing capability lookups unchanged. New values only used by new model entries.
**Acceptance:** `python3 -c "from portal.routing.model_registry import ModelCapability; print(ModelCapability.SECURITY)"`

---

## TASK-2: Add security_quality to ModelMetadata
Tier: 1
File: `src/portal/routing/model_registry.py`
Lines: 37-73

**Why:** `get_best_quality_model()` at line 145 maps capabilities to quality score lambdas. Without `security_quality`, SECURITY-capable models fall back to `general_quality` for ranking — which means The-Xploiter (a security specialist with maybe average general quality) gets ranked by the wrong score.

**Action:** Add field to dataclass:
```python
    # Quality scores (0.0-1.0)
    general_quality: float = 0.7
    code_quality: float = 0.5
    reasoning_quality: float = 0.5
    security_quality: float = 0.3      # NEW — offensive/defensive security tasks
```

Then update `quality_map` in `get_best_quality_model()` (line 145):
```python
        quality_map = {
            ModelCapability.GENERAL: lambda m: m.general_quality,
            ModelCapability.CODE: lambda m: m.code_quality,
            ModelCapability.REASONING: lambda m: m.reasoning_quality,
            ModelCapability.SECURITY: lambda m: m.security_quality,
        }
```

**Risk:** LOW — new field has default value, existing model entries unaffected.
**Acceptance:** `mypy src/portal/routing/model_registry.py` passes. Existing tests pass.

---

## TASK-3: Replace default_models.json
Tier: 1
File: `src/portal/routing/default_models.json`

**Action:** Replace entire file contents. Keep the JSON schema identical — the registry loader at line 91 does `ModelMetadata(**m, capabilities=caps, speed_class=speed)`.

New model catalog mapped from the CSV:

```json
[
  {
    "model_id": "ollama_dolphin_llama3_8b",
    "backend": "ollama",
    "display_name": "Dolphin 3.0 Llama3 8B",
    "parameters": "8B",
    "quantization": "Q6_K",
    "capabilities": ["general", "function_calling", "creative"],
    "speed_class": "fast",
    "context_window": 8192,
    "tokens_per_second": 90,
    "ram_required_gb": 8,
    "general_quality": 0.85,
    "code_quality": 0.7,
    "reasoning_quality": 0.7,
    "security_quality": 0.6,
    "cost": 0.25,
    "available": true,
    "api_model_name": "dolphin-llama3:8b"
  },
  {
    "model_id": "ollama_dolphin_llama3_70b",
    "backend": "ollama",
    "display_name": "Dolphin 3.0 Llama3 70B",
    "parameters": "70B",
    "quantization": "Q4_K_M",
    "capabilities": ["general", "function_calling", "creative", "reasoning"],
    "speed_class": "very_slow",
    "context_window": 8192,
    "tokens_per_second": 15,
    "ram_required_gb": 45,
    "general_quality": 0.95,
    "code_quality": 0.85,
    "reasoning_quality": 0.9,
    "security_quality": 0.75,
    "cost": 0.9,
    "available": true,
    "api_model_name": "dolphin-llama3:70b"
  },
  {
    "model_id": "ollama_the_xploiter",
    "backend": "ollama",
    "display_name": "The-Xploiter",
    "parameters": "9.2B",
    "quantization": "Q4_K_M",
    "capabilities": ["security", "code", "reasoning"],
    "speed_class": "fast",
    "context_window": 8192,
    "tokens_per_second": 75,
    "ram_required_gb": 12,
    "general_quality": 0.6,
    "code_quality": 0.8,
    "reasoning_quality": 0.8,
    "security_quality": 0.95,
    "cost": 0.4,
    "available": true,
    "api_model_name": "xploiter/the-xploiter"
  },
  {
    "model_id": "ollama_whiterabbitneo_8b",
    "backend": "ollama",
    "display_name": "WhiteRabbitNeo Llama3 8B v2",
    "parameters": "8B",
    "quantization": "Q4_0",
    "capabilities": ["security", "code"],
    "speed_class": "fast",
    "context_window": 8192,
    "tokens_per_second": 80,
    "ram_required_gb": 6,
    "general_quality": 0.55,
    "code_quality": 0.75,
    "reasoning_quality": 0.7,
    "security_quality": 0.9,
    "cost": 0.2,
    "available": true,
    "api_model_name": "lazarevtill/Llama-3-WhiteRabbitNeo-8B-v2.0:q4_0"
  },
  {
    "model_id": "ollama_baronllm_abliterated",
    "backend": "ollama",
    "display_name": "BaronLLM Abliterated",
    "parameters": "8B",
    "quantization": "Q4_K_M",
    "capabilities": ["security", "general"],
    "speed_class": "fast",
    "context_window": 8192,
    "tokens_per_second": 80,
    "ram_required_gb": 6,
    "general_quality": 0.65,
    "code_quality": 0.6,
    "reasoning_quality": 0.6,
    "security_quality": 0.85,
    "cost": 0.2,
    "available": true,
    "api_model_name": "huihui_ai/baronllm-abliterated"
  },
  {
    "model_id": "ollama_tongyi_deepresearch_30b",
    "backend": "ollama",
    "display_name": "Tongyi DeepResearch 30B Abliterated",
    "parameters": "30B-A3B",
    "quantization": "Q4_K_M",
    "capabilities": ["security", "reasoning", "general"],
    "speed_class": "slow",
    "context_window": 32768,
    "tokens_per_second": 30,
    "ram_required_gb": 22,
    "general_quality": 0.85,
    "code_quality": 0.8,
    "reasoning_quality": 0.92,
    "security_quality": 0.9,
    "cost": 0.65,
    "available": true,
    "api_model_name": "huihui_ai/tongyi-deepresearch-abliterated:30b"
  },
  {
    "model_id": "ollama_qwen3_coder_30b",
    "backend": "ollama",
    "display_name": "Qwen3 Coder Next 30B",
    "parameters": "30B",
    "quantization": "Q5_K_M",
    "capabilities": ["code", "general", "reasoning"],
    "speed_class": "medium",
    "context_window": 32768,
    "tokens_per_second": 40,
    "ram_required_gb": 24,
    "general_quality": 0.8,
    "code_quality": 0.95,
    "reasoning_quality": 0.85,
    "security_quality": 0.5,
    "cost": 0.65,
    "available": true,
    "api_model_name": "qwen3-coder-next:30b-q5"
  },
  {
    "model_id": "ollama_qwen3_omni_30b",
    "backend": "ollama",
    "display_name": "Qwen3 Omni 30B",
    "parameters": "30B-A3B",
    "quantization": "Q4_K_M",
    "capabilities": ["multimodal", "general", "vision", "audio", "creative", "reasoning"],
    "speed_class": "slow",
    "context_window": 32768,
    "tokens_per_second": 30,
    "ram_required_gb": 30,
    "general_quality": 0.88,
    "code_quality": 0.75,
    "reasoning_quality": 0.85,
    "security_quality": 0.5,
    "cost": 0.7,
    "available": true,
    "api_model_name": "qwen3-omni:30b"
  },
  {
    "model_id": "ollama_devstral_24b",
    "backend": "ollama",
    "display_name": "Devstral 24B",
    "parameters": "24B",
    "quantization": "Q6_K",
    "capabilities": ["code", "general"],
    "speed_class": "medium",
    "context_window": 32768,
    "tokens_per_second": 45,
    "ram_required_gb": 20,
    "general_quality": 0.78,
    "code_quality": 0.92,
    "reasoning_quality": 0.8,
    "security_quality": 0.4,
    "cost": 0.55,
    "available": true,
    "api_model_name": "devstral:24b"
  }
]
```

**Note:** Flux.2, CosyVoice, MOSS-TTS, Mochi-1 are NOT Ollama models — they are CLI/API tools. They go in `src/portal/tools/media_tools/` (TASK-7), not in this JSON.

**Risk:** MEDIUM — this changes every default model. Ollama auto-discovery (`discover_from_ollama`) will still register anything pulled that's not in the JSON, so models not listed here still work.
**Parity:** `/v1/models` endpoint returns whatever Ollama has pulled + virtual workspaces. The JSON only affects which models have curated metadata vs auto-discovered defaults.
**Acceptance:** `python3 -c "from portal.routing.model_registry import ModelRegistry; r = ModelRegistry(); print([m.display_name for m in r.get_all_models()])"` shows new model names.

---

## TASK-4: Add SECURITY and IMAGE_GEN categories to task_classifier.py
Tier: 1
File: `src/portal/routing/task_classifier.py`

**Action — Step 1:** Add to `TaskCategory` enum (line 21):
```python
class TaskCategory(Enum):
    GREETING = "greeting"
    QUESTION = "question"
    CODE = "code"
    MATH = "math"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    TOOL_USE = "tool_use"
    GENERAL = "general"
    SECURITY = "security"           # NEW
    IMAGE_GEN = "image_gen"         # NEW
    AUDIO_GEN = "audio_gen"         # NEW
```

**Action — Step 2:** Add pattern lists (after TOOL_PATTERNS, ~line 117):
```python
    # Security / offensive / defensive patterns
    SECURITY_PATTERNS = [
        r"\b(exploit|payload|bypass|nmap|shellcode|pentest|pentesting)\b",
        r"\b(red\s*team|blue\s*team|attack\s*chain|lateral\s*movement)\b",
        r"\b(cve|vulnerability|vuln|privilege\s*escalation|priv\s*esc)\b",
        r"\b(reverse\s*shell|bind\s*shell|meterpreter|cobalt\s*strike)\b",
        r"\b(active\s*directory|ad\s*attack|kerberoast|mimikatz|bloodhound)\b",
        r"\b(malware|ransomware|rootkit|backdoor|c2|command\s*and\s*control)\b",
        r"\b(osint|reconnaissance|recon|enumeration|footprint)\b",
        r"\b(buffer\s*overflow|heap\s*spray|rop\s*chain|format\s*string)\b",
        r"\b(waf\s*bypass|edr\s*bypass|amsi\s*bypass|etw\s*patch)\b",
    ]

    # Image generation patterns
    IMAGE_PATTERNS = [
        r"\b(draw|sketch|illustrate|paint|render)\b",
        r"\b(generate\s+(an?\s+)?image|create\s+(an?\s+)?image)\b",
        r"\b(flux|stable\s*diffusion|lora|img2img|txt2img)\b",
        r"\b(portrait|landscape|concept\s*art|illustration)\b",
    ]

    # Audio generation patterns
    AUDIO_PATTERNS = [
        r"\b(tts|text\s*to\s*speech|voice\s*clone|voice\s*synthesis)\b",
        r"\b(sing|singing|music\s*gen|sound\s*effect|audio\s*gen)\b",
        r"\b(cosyvoice|fish\s*speech|bark|tortoise)\b",
    ]
```

**Action — Step 3:** Compile them in `__init__` (line 126-134):
```python
        self._security_re = [re.compile(p, re.IGNORECASE) for p in self.SECURITY_PATTERNS]
        self._image_re = [re.compile(p, re.IGNORECASE) for p in self.IMAGE_PATTERNS]
        self._audio_re = [re.compile(p, re.IGNORECASE) for p in self.AUDIO_PATTERNS]
```

**Action — Step 4:** Update `_match_all_patterns` (line 136) to include new groups:
```python
    def _match_all_patterns(self, query: str) -> dict[str, int]:
        return {
            "code": sum(1 for p in self._code_re if p.search(query)),
            "math": sum(1 for p in self._math_re if p.search(query)),
            "analysis": sum(1 for p in self._analysis_re if p.search(query)),
            "creative": sum(1 for p in self._creative_re if p.search(query)),
            "tool": sum(1 for p in self._tool_re if p.search(query)),
            "security": sum(1 for p in self._security_re if p.search(query)),
            "image": sum(1 for p in self._image_re if p.search(query)),
            "audio": sum(1 for p in self._audio_re if p.search(query)),
        }
```

**Action — Step 5:** Update `_detect_category` (line 194) — security takes highest priority (before code):
```python
    def _detect_category(self, counts: dict, query: str) -> TaskCategory:
        if counts.get("security", 0) >= 1:
            return TaskCategory.SECURITY
        if counts.get("image", 0) >= 1:
            return TaskCategory.IMAGE_GEN
        if counts.get("audio", 0) >= 1:
            return TaskCategory.AUDIO_GEN
        if counts["code"] >= 2:
            return TaskCategory.CODE
        # ... rest unchanged
```

**Risk:** LOW — additive. Existing categories still match as before. New categories only fire on new patterns.
**Acceptance:** `python3 -c "from portal.routing.task_classifier import TaskClassifier; c = TaskClassifier(); print(c.classify('write a reverse shell exploit').category)"` → `TaskCategory.SECURITY`

---

## TASK-5: Update LLM classifier categories
Tier: 1
File: `src/portal/routing/llm_classifier.py`

**Action — Step 1:** Add to `LLMCategory` enum (line 20):
```python
class LLMCategory(Enum):
    GENERAL = "general"
    CODE = "code"
    REASONING = "reasoning"
    CREATIVE = "creative"
    TOOL_USE = "tool_use"
    SECURITY = "security"       # NEW
    IMAGE_GEN = "image_gen"     # NEW
    AUDIO_GEN = "audio_gen"     # NEW
```

**Action — Step 2:** Update the classification prompt (line 48):
```python
    CLASSIFY_PROMPT = """Classify this query into one of these categories:
- general: Simple questions, greetings, casual conversation
- code: Programming, debugging, technical tasks
- reasoning: Analysis, math, logic problems
- creative: Writing, brainstorming, storytelling
- tool_use: Using tools like QR codes, conversions, file operations
- security: Hacking, exploits, pentesting, red team, blue team, CTF, CVE analysis
- image_gen: Image creation, illustration, drawing, rendering
- audio_gen: Text-to-speech, voice cloning, music generation, sound effects

Respond with ONLY the category name (e.g., "code").
Query: {query}"""
```

**Action — Step 3:** Update `_fallback_to_regex` category map (line 114):
```python
        category_map = {
            TaskCategory.CODE: LLMCategory.CODE,
            TaskCategory.MATH: LLMCategory.REASONING,
            TaskCategory.ANALYSIS: LLMCategory.REASONING,
            TaskCategory.CREATIVE: LLMCategory.CREATIVE,
            TaskCategory.TOOL_USE: LLMCategory.TOOL_USE,
            TaskCategory.SECURITY: LLMCategory.SECURITY,
            TaskCategory.IMAGE_GEN: LLMCategory.IMAGE_GEN,
            TaskCategory.AUDIO_GEN: LLMCategory.AUDIO_GEN,
            TaskCategory.GREETING: LLMCategory.GENERAL,
            TaskCategory.QUESTION: LLMCategory.GENERAL,
            TaskCategory.SUMMARIZATION: LLMCategory.GENERAL,
            TaskCategory.TRANSLATION: LLMCategory.GENERAL,
            TaskCategory.GENERAL: LLMCategory.GENERAL,
        }
```

**Action — Step 4:** Update `intelligent_router.py` category override map (line 84):
```python
        category_override = {
            LLMCategory.CODE: TaskCategory.CODE,
            LLMCategory.REASONING: TaskCategory.ANALYSIS,
            LLMCategory.CREATIVE: TaskCategory.CREATIVE,
            LLMCategory.TOOL_USE: TaskCategory.TOOL_USE,
            LLMCategory.GENERAL: TaskCategory.GENERAL,
            LLMCategory.SECURITY: TaskCategory.SECURITY,
            LLMCategory.IMAGE_GEN: TaskCategory.IMAGE_GEN,
            LLMCategory.AUDIO_GEN: TaskCategory.AUDIO_GEN,
        }
```

**Risk:** LOW — additive. Existing mappings preserved.
**Acceptance:** `mypy src/portal/routing/llm_classifier.py src/portal/routing/intelligent_router.py` passes.

---

## TASK-6: Reconfigure router_rules.json
Tier: 1
File: `src/portal/routing/router_rules.json`

**Action:** Replace entire file:
```json
{
  "version": "2.0",
  "default_model": "dolphin-llama3:8b",
  "warm_model": "dolphin-llama3:8b",
  "workspaces": {
    "auto": {
      "model": "dolphin-llama3:8b",
      "lock": false,
      "fallback": ["dolphin-llama3:8b"]
    },
    "auto-coding": {
      "model": "qwen3-coder-next:30b-q5",
      "lock": true,
      "fallback": ["devstral:24b", "dolphin-llama3:8b"]
    },
    "auto-reasoning": {
      "model": "huihui_ai/tongyi-deepresearch-abliterated:30b",
      "lock": true,
      "fallback": ["dolphin-llama3:70b", "dolphin-llama3:8b"]
    },
    "auto-security": {
      "model": "xploiter/the-xploiter",
      "lock": true,
      "fallback": ["lazarevtill/Llama-3-WhiteRabbitNeo-8B-v2.0:q4_0", "dolphin-llama3:70b"]
    },
    "auto-creative": {
      "model": "dolphin-llama3:70b",
      "lock": true,
      "fallback": ["dolphin-llama3:8b"]
    },
    "auto-multimodal": {
      "model": "qwen3-omni:30b",
      "lock": true,
      "fallback": ["dolphin-llama3:8b"]
    },
    "auto-fast": {
      "model": "dolphin-llama3:8b",
      "lock": false,
      "fallback": ["dolphin-llama3:8b"]
    }
  },
  "classifier": {
    "model": "dolphin-llama3:8b",
    "categories": {
      "general": "dolphin-llama3:8b",
      "code": "qwen3-coder-next:30b-q5",
      "reasoning": "huihui_ai/tongyi-deepresearch-abliterated:30b",
      "creative": "dolphin-llama3:70b",
      "tool_use": "dolphin-llama3:8b",
      "security": "xploiter/the-xploiter",
      "image_gen": "dolphin-llama3:8b",
      "audio_gen": "dolphin-llama3:8b"
    }
  },
  "regex_rules": [
    {
      "name": "offensive_security",
      "keywords": ["(?i)\\b(exploit|shellcode|bypass|payload|reverse.?shell|pentest|red.?team|priv.?esc|kerberoast|mimikatz|bloodhound|meterpreter)\\b"],
      "model": "xploiter/the-xploiter",
      "priority": 10
    },
    {
      "name": "defensive_security",
      "keywords": ["(?i)\\b(blue.?team|siem|detection|ioc|threat.?hunt|yara|sigma|splunk|es notable|tstats|cim\\b)"],
      "model": "huihui_ai/tongyi-deepresearch-abliterated:30b",
      "priority": 10
    },
    {
      "name": "coding",
      "keywords": ["(?i)\\b(write|debug|function|class|def |import |async def|refactor)\\b"],
      "model": "qwen3-coder-next:30b-q5",
      "priority": 8
    },
    {
      "name": "reasoning",
      "keywords": ["(?i)\\b(analyze|reason|think through|explain why|step by step)\\b"],
      "model": "huihui_ai/tongyi-deepresearch-abliterated:30b",
      "priority": 7
    }
  ],
  "manual_override_prefix": "@model:",
  "auth_token_env": "ROUTER_TOKEN"
}
```

**Key changes:**
- Default/warm → `dolphin-llama3:8b` (zero refusals out of the box)
- Splunk regex → merged into `defensive_security` routing to Tongyi
- New `offensive_security` regex at priority 10
- New workspaces: `auto-security`, `auto-creative`, `auto-multimodal`
- Classifier categories now include `security`, `image_gen`, `audio_gen`
- Classifier model → `dolphin-llama3:8b` (uncensored, won't refuse to classify offensive queries)

**Risk:** MEDIUM — changes default model for all unrouted queries. All workspace names are additive. Existing workspace names (`auto`, `auto-coding`, `auto-reasoning`, `auto-fast`) preserved.
**Acceptance:** `python3 -c "import json; r = json.load(open('src/portal/routing/router_rules.json')); print(r['default_model'])"` → `dolphin-llama3:8b`

---

## TASK-7: Scaffold media tool stubs (image_gen, audio_gen)
Tier: 2
Files: `src/portal/tools/media_tools/`

**Why:** Flux.2 (via mflux) and CosyVoice/MOSS-TTS run as CLI tools, not Ollama models. They should be invokable via function calling from Dolphin/Qwen3-Omni.

**Action:** Create two stub modules that the orchestrator can call. These are placeholders for the actual implementations — the goal is to wire the routing so that when someone says "generate an image of X", the classifier routes to Dolphin and Dolphin can call the tool.

Create `src/portal/tools/media_tools/image_generator.py`:
```python
"""Image generation tool — wraps mflux/Flux.2 CLI for local image gen."""

import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ImageGenResult:
    success: bool
    image_path: str | None = None
    error: str | None = None


async def generate_image(
    prompt: str,
    output_dir: str = "~/AI_Output/images",
    steps: int = 20,
    model: str = "dev",
) -> ImageGenResult:
    """Generate image via mflux CLI. Requires `pip install mflux`."""
    try:
        import shutil
        if not shutil.which("mflux-generate"):
            return ImageGenResult(success=False, error="mflux not installed. Run: pip install mflux")

        # TODO: Implement actual mflux invocation
        # subprocess.run(["mflux-generate", "--prompt", prompt, ...])
        logger.info("Image generation requested: %s", prompt[:80])
        return ImageGenResult(success=False, error="Image generation not yet implemented — stub only")
    except Exception as e:
        return ImageGenResult(success=False, error=str(e))
```

Create `src/portal/tools/media_tools/audio_generator.py`:
```python
"""Audio generation tool — wraps CosyVoice2/MOSS-TTS for local TTS and voice clone."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AudioGenResult:
    success: bool
    audio_path: str | None = None
    error: str | None = None


async def generate_audio(
    text: str,
    voice: str = "default",
    output_dir: str = "~/AI_Output/audio",
) -> AudioGenResult:
    """Generate audio via CosyVoice2 or MOSS-TTS. Requires separate installation."""
    # TODO: Implement actual CosyVoice/MOSS-TTS invocation
    logger.info("Audio generation requested: %s", text[:80])
    return AudioGenResult(success=False, error="Audio generation not yet implemented — stub only")
```

**Risk:** LOW — new files, no changes to existing code.
**Acceptance:** `python3 -c "from portal.tools.media_tools.image_generator import generate_image; print('OK')"`

---

## TASK-8: Update intelligent_router.py routing for new categories
Tier: 2
File: `src/portal/routing/intelligent_router.py`

**Action:** Update `_route_auto` (line 122) and `_route_quality` (line 156) to handle new categories:

In `_route_quality`:
```python
    def _route_quality(self, classification: TaskClassification, max_cost: float) -> ModelMetadata:
        if classification.requires_code:
            capability = ModelCapability.CODE
        elif classification.category == TaskCategory.SECURITY:
            capability = ModelCapability.SECURITY
        elif classification.requires_math:
            capability = ModelCapability.MATH
        elif classification.category == TaskCategory.ANALYSIS:
            capability = ModelCapability.REASONING
        elif classification.category == TaskCategory.CREATIVE:
            capability = ModelCapability.GENERAL  # Dolphin handles creative via general
        else:
            capability = ModelCapability.GENERAL
        best = self.registry.get_best_quality_model(capability, max_cost)
        return best if best else self._get_any_available_model()
```

In `_route_auto`, add security to the preference lookup:
```python
        if classification.category == TaskCategory.SECURITY:
            preferred = self.model_preferences.get("security", [])
        elif classification.category == TaskCategory.CODE and classification.requires_code:
            preferred = self.model_preferences.get("code", [])
        # ... rest unchanged
```

**Risk:** MEDIUM — changes routing logic. Existing categories still follow same paths.
**Acceptance:** `pytest tests/unit/ -v --tb=short -k "router or routing"` — all pass.

---

## TASK-9: Update tests
Tier: 2
Files: `tests/unit/` (routing tests)

**Action:** For each new `TaskCategory` and `LLMCategory` value, add test cases:
- Task classifier: verify "write a reverse shell" → `SECURITY`, "generate an image" → `IMAGE_GEN`, "clone my voice" → `AUDIO_GEN`
- LLM classifier: verify fallback mapping covers new categories
- Model registry: verify new models load from JSON, `get_best_quality_model(SECURITY)` returns The-Xploiter
- Router rules: verify new workspaces resolve correctly

**Risk:** LOW — additive test cases.
**Acceptance:** `pytest tests/ -v --tb=short` — all pass, zero failures.

---

## TASK-10: Update PORTAL_ROADMAP.md
Tier: 2
File: `PORTAL_ROADMAP.md`

**Action:** Add these as new roadmap items:

```markdown
### [ROAD-F01] mflux Image Generation Tool Integration
Status:       PLANNED
Priority:     P3-MEDIUM
Effort:       M
Dependencies: TASK-7 stub complete
Description:  Wire mflux CLI into image_generator.py. Dolphin invokes via function calling.

### [ROAD-F02] CosyVoice2/MOSS-TTS Audio Tool Integration
Status:       PLANNED
Priority:     P3-MEDIUM
Effort:       M
Dependencies: TASK-7 stub complete
Description:  Wire CosyVoice2 or MOSS-TTS into audio_generator.py.

### [ROAD-F03] Lily-Cybersecurity-7B GGUF Integration
Status:       DISCUSSED
Priority:     P4-LOW
Effort:       S
Dependencies: GGUF → Modelfile conversion
Description:  Add Lily-Cybersecurity-7B as additional security model (GGUF, needs custom Modelfile).

### [ROAD-F04] Ollama Model Pull Automation
Status:       DISCUSSED
Priority:     P3-MEDIUM
Effort:       S
Description:  Script to pull all models defined in default_models.json. Currently manual.
```

---

## TASK-11: Wire virtual workspaces into `/v1/models` on `:8081`
Tier: 1 (this is the most critical fix — without it, Open WebUI never sees the smart routing options)
File: `src/portal/interfaces/web/server.py`
Method: `_handle_list_models` (line ~464)

**Problem:** `/v1/models` queries Ollama directly and returns raw model names. Open WebUI never sees `auto`, `auto-security`, `auto-coding` etc. The user has no way to select intelligent routing from the UI — they only see bare Ollama model names like `dolphin-llama3:8b`.

**Current:**
```python
async def _handle_list_models(self, auth: dict) -> dict:
    try:
        client = self._ollama_client or httpx.AsyncClient(timeout=3.0)
        resp = await client.get(f"{self._ollama_host}/api/tags")
        data = resp.json()
        return {
            "object": "list",
            "data": [
                {"id": m["name"], "object": "model", "created": int(time.time()), "owned_by": "portal"}
                for m in data.get("models", [])
            ],
        }
    except (httpx.HTTPError, json.JSONDecodeError):
        return {"object": "list", "data": [{"id": "auto", ...}]}
```

**Action:** Load router_rules.json workspaces and prepend them as virtual models. This matches what the `:8000` proxy already does in its `/api/tags` endpoint.

```python
async def _handle_list_models(self, auth: dict) -> dict:
    created = int(time.time())
    models: list[dict] = []

    # 1. Add virtual workspace models (these trigger intelligent routing)
    try:
        rules_path = Path(__file__).parents[2] / "routing" / "router_rules.json"
        if rules_path.exists():
            import json as _json
            rules = _json.loads(rules_path.read_text())
            for ws_name in rules.get("workspaces", {}):
                models.append({
                    "id": ws_name,
                    "object": "model",
                    "created": created,
                    "owned_by": "portal-workspace",
                })
    except Exception as e:
        logger.warning("Failed to load workspace models: %s", e)

    # 2. Add real Ollama models
    try:
        client = self._ollama_client or httpx.AsyncClient(timeout=3.0)
        resp = await client.get(f"{self._ollama_host}/api/tags")
        data = resp.json()
        for m in data.get("models", []):
            models.append({
                "id": m["name"],
                "object": "model",
                "created": created,
                "owned_by": "portal",
            })
    except (httpx.HTTPError, json.JSONDecodeError):
        pass

    # Fallback: always have at least "auto"
    if not models:
        models.append({"id": "auto", "object": "model", "created": created, "owned_by": "portal"})

    return {"object": "list", "data": models}
```

Add `from pathlib import Path` to the imports at top of file if not already present.

**What this gives Open WebUI:** The model dropdown now shows `auto`, `auto-security`, `auto-coding`, `auto-creative`, `auto-multimodal`, `auto-fast`, plus all the real Ollama models. User selects `auto-security` → that string flows through as `payload.model` → becomes `incoming.model`.

**Risk:** LOW — additive. Existing models still appear. Virtual models are prepended so they show first in the dropdown.
**Parity:** `/v1/models` still returns valid OpenAI-compatible schema. New entries have `owned_by: "portal-workspace"` to distinguish them.
**Acceptance:** `curl http://localhost:8081/v1/models | python3 -m json.tool` shows workspace names before Ollama models.

---

## TASK-12: Thread `incoming.model` through AgentCore as workspace_id
Tier: 1
Files: `src/portal/core/agent_core.py`, `src/portal/routing/execution_engine.py`

**Problem:** The wire is cut in two places:

1. `agent_core.stream_response()` (line ~400) receives `incoming` with `.model` set, but calls `execution_engine.generate_stream(query=query)` without passing the model.
2. `execution_engine.generate_stream()` (line ~193) calls `self.router.route(query)` without `workspace_id`, even though `IntelligentRouter.route()` already accepts it.

Same problem exists in the non-streaming path: `process_message()` → `_execute_with_routing()` → `self.router.route(query)`.

**Action — Step 1:** Update `execution_engine.py` — add `workspace_id` parameter to both `execute()` and `generate_stream()`:

In `execute()` (line ~84):
```python
    async def execute(
        self,
        query: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        max_cost: float = 1.0,
        messages: list[dict[str, Any]] | None = None,
        workspace_id: str | None = None,              # NEW
    ) -> ExecutionResult:
        start_time = time.time()
        decision = await self.router.route(query, max_cost, workspace_id=workspace_id)  # CHANGED
```

In `generate_stream()` (line ~193):
```python
    async def generate_stream(
        self,
        query: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        messages: list[dict[str, Any]] | None = None,
        workspace_id: str | None = None,              # NEW
    ) -> AsyncIterator[str]:
        decision = await self.router.route(query, workspace_id=workspace_id)  # CHANGED
```

**Action — Step 2:** Update `agent_core.py` — pass `incoming.model` through.

In `stream_response()` (line ~400), pass workspace_id to generate_stream:
```python
    async def stream_response(self, incoming: IncomingMessage) -> AsyncIterator[str]:
        # ... existing code for system_prompt, tool_messages ...

        # Determine workspace_id: if model is a workspace name, pass it; if "auto" or explicit model, pass as-is
        workspace_id = incoming.model if incoming.model else None

        async for token in self.execution_engine.generate_stream(
            query=query,
            system_prompt=system_prompt,
            messages=final_messages,
            workspace_id=workspace_id,                # NEW
        ):
            collected_response.append(token)
            yield token
```

In `_execute_with_routing()` (line ~312), add workspace_id parameter and pass through:
```python
    async def _execute_with_routing(
        self,
        query: str,
        system_prompt: str,
        available_tools: list[str],
        chat_id: str,
        trace_id: str,
        messages: list[dict[str, Any]] | None = None,
        workspace_id: str | None = None,              # NEW
    ):
        decision = await self.router.route(query, workspace_id=workspace_id)  # CHANGED
```

In `_run_execution_with_mcp_loop()` (line ~442), thread it through:
```python
    async def _run_execution_with_mcp_loop(
        self,
        query: str,
        system_prompt: str,
        available_tools: list[str],
        chat_id: str,
        trace_id: str,
        messages: list[dict[str, Any]] | None = None,
        workspace_id: str | None = None,              # NEW
    ) -> tuple[Any, list[dict[str, Any]]]:
        # ... in the loop body:
            result = await self._execute_with_routing(
                query=query,
                system_prompt=system_prompt,
                available_tools=available_tools,
                chat_id=chat_id,
                trace_id=trace_id,
                messages=current_messages,
                workspace_id=workspace_id,             # NEW
            )
```

**Action — Step 3:** Update `process_message()` (line ~112) to accept and pass model/workspace:

```python
    async def process_message(
        self,
        chat_id: str,
        message: str,
        interface: InterfaceType = InterfaceType.UNKNOWN,
        user_context: dict | None = None,
        files: list[Any] | None = None,
        workspace_id: str | None = None,              # NEW
    ) -> ProcessingResult:
```

Then in the body, pass it to `_run_execution_with_mcp_loop()`:
```python
                result, tool_results = await self._run_execution_with_mcp_loop(
                    query=message,
                    system_prompt=system_prompt,
                    available_tools=available_tools,
                    chat_id=chat_id,
                    trace_id=trace_id,
                    messages=context_history or None,
                    workspace_id=workspace_id,         # NEW
                )
```

**Risk:** MEDIUM — touches the core routing chain. But all new parameters have `None` defaults so every existing caller is unaffected.
**Parity:** When `workspace_id` is `None` (all existing callers), behavior is identical to before — `IntelligentRouter.route()` falls through to task classification. When it's set to a workspace name like `auto-security`, the router short-circuits to the workspace model. This is how it was always designed to work — it just was never wired.
**Acceptance:** Start Portal, open Open WebUI, select `auto-security` from the model dropdown, type "write a reverse shell" → response comes from The-Xploiter (verify in logs: `Workspace routing: auto-security → xploiter/the-xploiter`).

---

## TASK-13: Pass workspace_id from web server non-streaming path
Tier: 1
File: `src/portal/interfaces/web/server.py`
Method: `_handle_chat_completions` (line ~378)

**Problem:** The non-streaming path at line ~428 calls `processor.process_message()` without passing the selected model:
```python
result = await processor.process_message(
    chat_id=incoming.id,
    message=incoming.text,
    interface=InterfaceType.WEB,
    user_context={"user_id": user_id},
)
```

**Action:** Pass the workspace_id:
```python
result = await processor.process_message(
    chat_id=incoming.id,
    message=incoming.text,
    interface=InterfaceType.WEB,
    user_context={"user_id": user_id},
    workspace_id=selected_model,                      # NEW
)
```

Note: `SecurityMiddleware.process_message()` wraps `agent_core.process_message()`. Check if it also needs the `workspace_id` parameter forwarded. If SecurityMiddleware uses `**kwargs`, it'll pass through automatically. If it has an explicit signature, add `workspace_id: str | None = None` to it as well and forward it to the inner `agent_core.process_message()` call.

```bash
grep -n "async def process_message" src/portal/security/middleware.py
```

If it needs updating:
```python
    async def process_message(
        self, chat_id, message, interface=..., user_context=None, files=None,
        workspace_id: str | None = None,              # ADD if not present
    ) -> ProcessingResult:
        # ... security checks ...
        return await self.agent_core.process_message(
            chat_id=chat_id, message=message, interface=interface,
            user_context=user_context, files=files,
            workspace_id=workspace_id,                # FORWARD
        )
```

**Risk:** LOW — additive parameter with None default.
**Parity:** Non-streaming requests now also respect workspace selection. Previously they always fell through to query-text classification.
**Acceptance:** `curl -X POST http://localhost:8081/v1/chat/completions -d '{"model":"auto-security","messages":[{"role":"user","content":"explain kerberoasting"}],"stream":false}'` — response model in logs shows The-Xploiter.

---

## Execution Rules

- Work directly on `main`. No feature branches.
- Conventional commits: `feat(routing): expand ModelCapability enum with security/creative/media`
- One commit per task. Complete TASK-1 through TASK-6 and TASK-11 through TASK-13 (all Tier 1) before TASK-7+.
- TASK-11 through TASK-13 are the routing wire fix — they connect Open WebUI to the intelligent router. Without them, the new models and workspaces exist but are unreachable from the UI.
- After each task: `ruff check src/ tests/ && mypy src/portal && pytest tests/unit/ -v --tb=short`
- Full CI green before pushing: `make ci`

## Ollama Pull Commands (for local testing)

After code changes, pull the models to test routing:
```bash
ollama pull dolphin-llama3:8b
ollama pull dolphin-llama3:70b
ollama pull xploiter/the-xploiter
ollama pull lazarevtill/Llama-3-WhiteRabbitNeo-8B-v2.0:q4_0
ollama pull huihui_ai/baronllm-abliterated
ollama pull huihui_ai/tongyi-deepresearch-abliterated:30b
ollama pull qwen3-coder-next:30b-q5
ollama pull qwen3-omni:30b
ollama pull devstral:24b
```
