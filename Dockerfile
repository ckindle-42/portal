# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install into a virtualenv so we can copy it cleanly to the runtime stage
COPY pyproject.toml ./
COPY src/ ./src/

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && (/opt/venv/bin/pip install --no-cache-dir ".[all]" \
        || /opt/venv/bin/pip install --no-cache-dir .)

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 portal \
    && mkdir -p /app/data /app/logs \
    && chown -R portal:portal /app

# Copy venv from builder and source tree
COPY --from=builder /opt/venv /opt/venv
COPY --chown=portal:portal src/ ./src/

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/src

USER portal

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

CMD ["uvicorn", "portal.interfaces.web.server:app", \
     "--host", "0.0.0.0", "--port", "8081"]
