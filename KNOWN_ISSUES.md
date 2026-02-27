# Known Issues

This file tracks intentional known-failure states, deferred work, and structural
debt. It is referenced by `tests/conftest.py` to explain why certain tests are
marked `xfail`.

---

## Section 1 — Open: CSP trade-off

The default Content-Security-Policy in `src/portal/interfaces/web/server.py`
includes `'unsafe-inline' 'unsafe-eval'` for compatibility with Open WebUI's
JavaScript. This should be tightened in production deployments that do not use
a web UI frontend.

---

## Section 2 — Open: Pickle embedding migration

Knowledge base embeddings serialized with the legacy `pickle` format will fail
to load unless `ALLOW_LEGACY_PICKLE_EMBEDDINGS=true` is set. To migrate:
re-index affected documents (`action=add`) so they are re-serialized in the
current JSON format, then remove the environment variable.

---

## Section 3 — Open: M4 Mac Memory Pressure (MLX)

Running quantization levels above `q8_0` with MLX on an M4 Mac Mini Pro
(64 GB or 128 GB unified-memory configurations) can trigger macOS memory
pressure and cause page-outs even with models that nominally fit in RAM.

**Affected models:** Any MLX model loaded at `q8_0` or above (e.g.
`mlx-community/Qwen2.5-32B-Instruct-8bit`, `mlx-community/Llama-3.3-70B-Instruct-8bit`).

**Symptoms:** Elevated `memory_pressure` in Activity Monitor, increased
swap usage, degraded tokens-per-second, occasional OOM kills of Ollama or
Portal when multiple processes compete for unified memory.

**Workarounds:**
- Prefer `q4_K_M` or `q5_K_M` quantization for 32B+ models on M4.
- Run at most one large model at a time; unload idle models via
  `ollama rm <model>` before loading a new one.
- Monitor with `vm_stat` and `memory_pressure` CLI utilities.
- Set `OLLAMA_MAX_LOADED_MODELS=1` in your environment to prevent
  Ollama from keeping multiple models resident simultaneously.
