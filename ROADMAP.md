# Portal Roadmap

Planned feature projects for Portal. These are scoped designs, not aspirational wishlists.
Each is estimated at 2-3 days of implementation.

---

## 1. LLM-Based Intelligent Routing

**Status:** Planned
**Priority:** High — improves model selection accuracy for all interfaces
**Estimated effort:** 2-3 days

### Problem

Portal has two routing systems that use regex pattern matching to select models:

1. **Proxy Router** (`:8000`, `router.py`) — matches message content against regex rules in
   `router_rules.json` to select Ollama models. Serves Open WebUI / LibreChat.
2. **IntelligentRouter** (`:8081`, `intelligent_router.py`) — uses `TaskClassifier` with 100+
   compiled regex patterns to classify task complexity/category. Serves Portal API, Telegram, Slack.

Both are fragile. "Help me understand why my Splunk search is slow" matches "understand" as
reasoning but should route to the Splunk-specialist model. Regex can't understand semantic intent.

### Design

Replace regex-based classification with a small LLM classifier call.

**Keep as-is (explicit routing — not guessing):**
- `@model:name` manual override in message text — user always wins
- Workspace virtual models (`auto-coding`, `auto-reasoning`) — explicit selection via UI model picker

**Replace with LLM classification:**
- `router_rules.json` regex rules → LLM classifier call
- `TaskClassifier` heuristics → same LLM classifier

**How it works:**

1. User sends a message
2. Portal sends the message to a small fast model (e.g., `qwen2.5:0.5b`, already warm in Ollama)
   with a structured prompt asking it to classify into one of: `general`, `code`, `reasoning`,
   `splunk`, `creative`
3. The single-word response maps to a target model via config
4. Full resolution chain becomes: `@model:` → workspace → **LLM classifier** → default

**Config schema (replaces `regex_rules` in `router_rules.json`):**
```json
{
  "classifier": {
    "model": "qwen2.5:0.5b",
    "categories": {
      "general": "qwen2.5:7b",
      "code": "qwen2.5-coder:32b",
      "reasoning": "deepseek-r1:32b",
      "splunk": "deepseek-r1:32b",
      "creative": "qwen2.5:14b"
    }
  }
}
```

**Performance:** Classifier adds ~100-300ms (0.5B model, already loaded). This is invisible
relative to 2-30s generation time. LRU cache avoids reclassifying repeated patterns.

**Implementation files:**
- New `src/portal/routing/llm_classifier.py` — async classifier function
- Update `router.py::resolve_model()` — replace regex step with classifier
- Update `intelligent_router.py` — replace `TaskClassifier` with shared classifier
- Keep `TaskClassifier` as zero-latency fallback when classifier model unavailable
- Update `router_rules.json` schema

---

## 2. MLX Backend for Apple Silicon

**Status:** Planned
**Priority:** Medium — performance optimization for M4 Mac users
**Estimated effort:** 2-3 days
**Prerequisite:** `pip install mlx-lm`; only relevant when `COMPUTE_BACKEND=mps`

### Problem

On M4 Mac, all inference goes through Ollama (llama.cpp + Metal). Apple's MLX framework can
offer better token throughput for certain model architectures on unified memory. The previous
`MLXBackend` was a non-functional stub from PocketPortal (removed in 1.3.5).

### Design

Use `mlx_lm.server` as an HTTP backend — same pattern as Ollama, not in-process loading.

`mlx_lm.server` provides an OpenAI-compatible HTTP API with native SSE streaming, Jinja2 chat
templates, and Apple Silicon memory optimization.

**How it works:**

1. `hardware/m4-mac/launch.sh` starts `mlx_lm.server` on `:8800` alongside Ollama
2. New `MLXServerBackend(BaseHTTPBackend)` in `model_backends.py` — same pattern as `OllamaBackend`
   but targeting `http://localhost:8800/v1` with OpenAI-format requests
3. `default_models.json` gets entries with `"backend": "mlx"` for Apple Silicon-optimized models
4. `ExecutionEngine` registers the `mlx` backend when `COMPUTE_BACKEND=mps`
5. Router prefers MLX models on Apple Silicon, falls back to Ollama for unsupported architectures

**Key principle:** MLX backend is an HTTP server adapter, not an in-process library call.
Same reliability model as Ollama — Portal stays a thin orchestration layer.

**Implementation files:**
- New `MLXServerBackend(BaseHTTPBackend)` in `model_backends.py` (~100 lines)
- Update `ExecutionEngine.__init__` — conditionally register mlx backend
- Update `hardware/m4-mac/launch.sh` — start `mlx_lm.server`
- Add MLX models to `default_models.json`
- Add `MLX_SERVER_PORT`, `MLX_DEFAULT_MODEL` to `.env.example`
- Update `launch.sh doctor` to check MLX server health

**New env vars:**
```bash
MLX_SERVER_PORT=8800
MLX_DEFAULT_MODEL=mlx-community/Qwen2.5-7B-Instruct-4bit
```
