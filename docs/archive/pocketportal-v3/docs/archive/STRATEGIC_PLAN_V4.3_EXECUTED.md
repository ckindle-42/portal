# PocketPortal v4.3.0 - Strategic Architectural Plan

**Status:** In Progress
**Target Version:** 4.3.0 → "One-for-All" Foundation
**Approach:** John Carmack Style - Explore, Plan, Execute Systematically

---

## Executive Summary

This document outlines a comprehensive architectural improvement plan for PocketPortal v4.3.0. The goal is to transform PocketPortal from a capable agent platform into a true "one-for-all" solution that can handle:

- ✅ Lightweight local tasks (current strength)
- 🎯 Heavy computational workloads (video, OCR, data science)
- 🔌 Community-driven plugin ecosystem
- 📊 Production-grade observability
- 🌐 Universal resource access (local, cloud, MCP servers)

**Guiding Principles:**
1. **Systematic Exploration** - Understand before changing
2. **Strategic Planning** - Design before implementing
3. **Closed-Loop Testing** - Verify independently
4. **Incremental Delivery** - Ship working software

---

## Current State Analysis (v4.1.2)

### Strengths
- ✅ Solid core architecture (AgentCore, EventBus, Security)
- ✅ Dynamic tool discovery using pkgutil
- ✅ DAO pattern for persistence layer
- ✅ Lazy loading for heavy dependencies
- ✅ Human-in-the-loop middleware
- ✅ Multiple interfaces (Telegram, Web, API)
- ✅ Comprehensive documentation

### Gaps Identified
- ❌ **Plugin System**: pkgutil only works for internal tools
- ❌ **Async Queue**: All tool execution blocks the agent
- ❌ **Stateful Execution**: No persistent execution environments
- ❌ **MCP Integration**: Treated as just another tool, not a protocol layer
- ❌ **Observability**: Only structured logging, no tracing/metrics
- ❌ **Config Management**: No hot-reloading, requires restart
- ❌ **Health Checks**: No standard health/readiness endpoints
- ❌ **Documentation Drift**: Multiple versions of same docs
- ❌ **Version Management**: Manual version updates across files
- ❌ **Test Organization**: No markers for unit vs integration tests

---

## Phase 1: Foundation & Cleanup

**Goal:** Organize existing work and establish clean baseline

### 1.1 Documentation Consolidation

**Problem:**
- Root `ARCHITECTURE.md` (v4.2.0) vs `docs/architecture.md` (v4.1)
- `HUMAN_IN_LOOP_SUMMARY.md` (root) vs `docs/HUMAN_IN_LOOP.md`
- Inconsistent version numbering

**Solution:**
```
BEFORE:
├── ARCHITECTURE.md (v4.2.0)
├── HUMAN_IN_LOOP_SUMMARY.md
└── docs/
    ├── architecture.md (v4.1)
    └── HUMAN_IN_LOOP.md

AFTER:
└── docs/
    ├── architecture.md (v4.3.0 - merged, single source of truth)
    ├── HUMAN_IN_LOOP.md (comprehensive with summary section)
    └── STRATEGIC_PLAN_V4.3.md (this document)
```

**Actions:**
- [x] Move root `ARCHITECTURE.md` → `docs/architecture.md` (overwrite)
- [ ] Add summary section to `docs/HUMAN_IN_LOOP.md`
- [ ] Delete root `HUMAN_IN_LOOP_SUMMARY.md`
- [ ] Update root README to link to `docs/` as single source of truth

**Benefits:**
- Single source of truth for architecture
- No version confusion
- Easier maintenance

### 1.2 Version Synchronization

**Problem:**
- `pyproject.toml`: 4.1.2
- `pocketportal/__init__.py`: 4.1.2
- `ARCHITECTURE.md`: Claims v4.2.0

**Solution:**
- Bump to **v4.3.0** across all files
- Set up single-source versioning in `pyproject.toml`
- Use `importlib.metadata` for runtime version access

**Actions:**
- [ ] Update `pyproject.toml` version = "4.3.0"
- [ ] Update `pocketportal/__init__.py` __version__ = '4.3.0'
- [ ] Update all docs to reference v4.3.0
- [ ] Add version consistency check to CI/CD

### 1.3 Test Organization

**Problem:**
- Tests exist but no categorization
- Hard to run "just unit tests" vs "integration tests"
- No separation of fast vs slow tests

**Solution:**
```python
# Add pytest markers
@pytest.mark.unit  # Fast, no I/O, no external dependencies
@pytest.mark.integration  # Requires Docker, network, database
@pytest.mark.slow  # Takes >5 seconds
```

**Actions:**
- [ ] Add markers to `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  markers = [
      "unit: Fast unit tests with no external dependencies",
      "integration: Tests requiring Docker, network, or database",
      "slow: Tests taking more than 5 seconds",
  ]
  ```
- [ ] Tag all existing tests
- [ ] Update CI to run unit tests on every commit, integration on PR
- [ ] Add `pytest -m unit` to pre-commit hook

---

## Phase 2: Plugin Architecture (Entry Points)

**Goal:** Enable third-party tool development without modifying core

### 2.1 Current Limitation

**Today (pkgutil-based):**
```python
# Only discovers tools inside pocketportal.tools.*
for importer, modname, ispkg in pkgutil.walk_packages(
    path=[str(tools_dir)],
    prefix='pocketportal.tools.'
):
    # Load tool classes
```

**Problem:**
- Community developers must fork and modify `pocketportal/tools/`
- No way to `pip install pocketportal-tool-finance` and have it auto-discover
- Limits ecosystem growth

### 2.2 Solution: Python Entry Points

**How it works:**
```toml
# Third-party package: pocketportal-tool-finance/pyproject.toml
[project.entry-points."pocketportal.tools"]
stock_ticker = "pocketportal_finance:StockTickerTool"
crypto_price = "pocketportal_finance:CryptoPriceTool"
```

**Tool Registry Enhancement:**
```python
# pocketportal/tools/__init__.py
import importlib.metadata

def discover_and_load(self):
    # 1. Discover internal tools (existing pkgutil code)
    self._discover_internal_tools()

    # 2. Discover external plugins via entry_points
    self._discover_entry_point_tools()

def _discover_entry_point_tools(self):
    """Load tools from entry_points"""
    entry_points = importlib.metadata.entry_points()

    if hasattr(entry_points, 'select'):
        # Python 3.10+
        plugin_entry_points = entry_points.select(group='pocketportal.tools')
    else:
        # Python 3.9
        plugin_entry_points = entry_points.get('pocketportal.tools', [])

    for entry_point in plugin_entry_points:
        try:
            tool_class = entry_point.load()
            tool_instance = tool_class()
            self.tools[tool_instance.metadata.name] = tool_instance
            logger.info(f"Loaded plugin tool: {tool_instance.metadata.name}")
        except Exception as e:
            logger.error(f"Failed to load plugin {entry_point.name}: {e}")
```

### 2.3 Example Plugin Structure

**Create docs/PLUGIN_DEVELOPMENT.md:**
```markdown
# Creating a PocketPortal Plugin

## Quick Start

1. Create package structure:
   ```
   pocketportal-tool-finance/
   ├── pyproject.toml
   ├── pocketportal_finance/
   │   ├── __init__.py
   │   └── stock_ticker.py
   ```

2. Define tool:
   ```python
   # pocketportal_finance/stock_ticker.py
   from pocketportal.tools.base_tool import BaseTool, ToolMetadata, ToolCategory

   class StockTickerTool(BaseTool):
       def __init__(self):
           metadata = ToolMetadata(
               name="stock_ticker",
               description="Get real-time stock prices",
               category=ToolCategory.DATA,
               version="1.0.0"
           )
           super().__init__(metadata)

       async def execute(self, parameters):
           # Implementation
           pass
   ```

3. Register in pyproject.toml:
   ```toml
   [project.entry-points."pocketportal.tools"]
   stock_ticker = "pocketportal_finance:StockTickerTool"
   ```

4. Install:
   ```bash
   pip install pocketportal-tool-finance
   ```

5. Tool auto-discovered on next PocketPortal startup!
```

### 2.4 Implementation Checklist

- [ ] Update `pocketportal/tools/__init__.py` with entry_points discovery
- [ ] Add backwards compatibility (keep pkgutil for internal tools)
- [ ] Create example plugin: `pocketportal-tool-example`
- [ ] Document plugin API in `docs/PLUGIN_DEVELOPMENT.md`
- [ ] Add plugin validation (check BaseTool inheritance)
- [ ] Test with real external package

**Benefits:**
- ✅ Community can create tools without forking
- ✅ Install tools like `pip install pocketportal-tool-X`
- ✅ Official and community plugins coexist
- ✅ Keeps core lightweight

---

## Phase 3: Async Job Queue Architecture

**Goal:** Handle long-running tasks without blocking the agent

### 3.1 Problem Statement

**Current Behavior:**
```python
# Agent blocks until tool completes
result = await tool.execute(parameters)  # Waits for 30 minutes of video processing
# Cannot process new messages until this finishes
```

**Issues:**
- Video processing, OCR, large data analysis blocks the agent
- User sends "hello" → waits 10 minutes for video to finish
- Not production-ready for heavy workloads

### 3.2 Solution: Task Queue Interface (DAO Pattern)

**Architecture:**
```
pocketportal/queues/
├── __init__.py              # Public exports
├── queue_interface.py       # Abstract base class
├── in_memory_queue.py       # Default (asyncio.Queue)
└── redis_queue.py           # Future (production)
```

**Queue Interface:**
```python
# pocketportal/queues/queue_interface.py
from abc import ABC, abstractmethod
from typing import Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    job_id: str
    tool_name: str
    parameters: dict
    chat_id: str
    user_id: str
    status: JobStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

class QueueInterface(ABC):
    """Abstract interface for job queues"""

    @abstractmethod
    async def enqueue(self, job: Job) -> str:
        """Add job to queue, return job_id"""
        pass

    @abstractmethod
    async def get_status(self, job_id: str) -> Optional[Job]:
        """Get job status"""
        pass

    @abstractmethod
    async def cancel(self, job_id: str) -> bool:
        """Cancel pending job"""
        pass

    @abstractmethod
    async def start_worker(self, worker_fn: Callable) -> None:
        """Start background worker"""
        pass

    @abstractmethod
    async def stop_worker(self) -> None:
        """Stop background worker"""
        pass
```

**In-Memory Implementation:**
```python
# pocketportal/queues/in_memory_queue.py
import asyncio
from typing import Dict, Callable
from .queue_interface import QueueInterface, Job, JobStatus

class InMemoryQueue(QueueInterface):
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._jobs: Dict[str, Job] = {}
        self._worker_task: Optional[asyncio.Task] = None

    async def enqueue(self, job: Job) -> str:
        self._jobs[job.job_id] = job
        await self._queue.put(job.job_id)
        return job.job_id

    async def get_status(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            return True
        return False

    async def start_worker(self, worker_fn: Callable):
        self._worker_task = asyncio.create_task(self._worker_loop(worker_fn))

    async def _worker_loop(self, worker_fn: Callable):
        while True:
            job_id = await self._queue.get()
            job = self._jobs[job_id]

            if job.status == JobStatus.CANCELLED:
                continue

            job.status = JobStatus.RUNNING
            job.started_at = time.time()

            try:
                result = await worker_fn(job)
                job.status = JobStatus.COMPLETED
                job.result = result
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = str(e)
            finally:
                job.completed_at = time.time()

    async def stop_worker(self):
        if self._worker_task:
            self._worker_task.cancel()
```

### 3.3 Tool Integration

**Heavy tools can opt-in to async queue:**
```python
# pocketportal/tools/base_tool.py
@dataclass
class ToolMetadata:
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    requires_confirmation: bool = False
    async_capable: bool = False
    use_job_queue: bool = False  # ← New flag

# pocketportal/tools/video_processing/video_transcoder.py
class VideoTranscoderTool(BaseTool):
    def __init__(self):
        metadata = ToolMetadata(
            name="video_transcode",
            description="Transcode video files",
            category=ToolCategory.MEDIA,
            use_job_queue=True  # ← Use queue
        )
        super().__init__(metadata)
```

**AgentCore Integration:**
```python
# pocketportal/core/engine.py
async def execute_tool(self, tool_name: str, parameters: dict, chat_id: str):
    tool = self.tool_registry.get_tool(tool_name)

    # Check if tool should use job queue
    if tool.metadata.use_job_queue and self.job_queue:
        # Enqueue instead of executing immediately
        job = Job(
            job_id=str(uuid.uuid4()),
            tool_name=tool_name,
            parameters=parameters,
            chat_id=chat_id,
            status=JobStatus.PENDING,
            created_at=time.time()
        )

        job_id = await self.job_queue.enqueue(job)

        # Emit event for user notification
        await self.event_bus.emit(EventType.JOB_QUEUED, {
            'job_id': job_id,
            'tool_name': tool_name,
            'message': f"Task queued. I'll notify you when it's done!"
        }, chat_id)

        return {'status': 'queued', 'job_id': job_id}
    else:
        # Execute immediately (existing behavior)
        return await tool.execute(parameters)
```

### 3.4 User Experience

**Before (blocking):**
```
User: "Transcode this 2GB video to MP4"
[Agent silent for 15 minutes]
Agent: "Done! Here's your video."
```

**After (async queue):**
```
User: "Transcode this 2GB video to MP4"
Agent: "Got it! I've queued the transcoding job. I'll notify you when it's done."
[User can ask other questions]
[15 minutes later]
Agent: "✅ Video transcoding complete! Here's your MP4."
```

### 3.5 Implementation Checklist

- [ ] Create `pocketportal/queues/` module
- [ ] Implement `QueueInterface` abstract base
- [ ] Implement `InMemoryQueue` (default)
- [ ] Add `use_job_queue` flag to ToolMetadata
- [ ] Integrate with AgentCore
- [ ] Add EventBus events: `JOB_QUEUED`, `JOB_COMPLETED`, `JOB_FAILED`
- [ ] Create background worker in AgentCore
- [ ] Add job status command: `/job_status <job_id>`
- [ ] Document usage in docs/ASYNC_JOBS.md
- [ ] Test with heavy tool (video processing)

**Benefits:**
- ✅ Non-blocking agent
- ✅ Can handle heavy workloads
- ✅ User gets immediate feedback
- ✅ Foundation for production scaling (swap to Redis later)

---

## Phase 4: MCP Protocol Elevation

**Goal:** Treat MCP as a protocol layer, not just another tool

### 4.1 Current State

**Today:**
```
pocketportal/tools/
├── mcp_tools/
│   ├── mcp_connector.py
│   └── mcp_registry.py
```

MCP is just another tool category → limits its potential

### 4.2 Vision: Bidirectional MCP

**PocketPortal as MCP Client:**
- Connect to external MCP servers (database, filesystem, APIs)
- Use their tools as if they were native

**PocketPortal as MCP Server:**
- Expose PocketPortal's tools to other AI clients
- Claude Desktop, IDEs can use PocketPortal's Git, Docker, etc.

### 4.3 New Structure

```
pocketportal/protocols/
├── __init__.py
├── mcp/
│   ├── __init__.py
│   ├── client.py       # Connect to external MCP servers
│   ├── server.py       # Expose PocketPortal as MCP server
│   ├── registry.py     # MCP resource registry
│   └── connector.py    # Connection management
└── resource_resolver.py  # Universal URI resolver
```

### 4.4 Universal Resource Resolver

**Problem:**
```python
# User asks: "Analyze the file in my Google Drive"
# Today: Can't access, only local files
```

**Solution: Universal Resource URIs**
```python
# pocketportal/protocols/resource_resolver.py
class ResourceResolver:
    """Resolve resources from multiple sources"""

    async def resolve(self, uri: str) -> bytes:
        """
        Supported URIs:
        - local://path/to/file
        - drive://fileId
        - s3://bucket/key
        - mcp://server/resource
        - http://example.com/file
        """
        scheme = uri.split('://')[0]

        if scheme == 'local':
            return await self._resolve_local(uri)
        elif scheme == 'drive':
            return await self._resolve_google_drive(uri)
        elif scheme == 'mcp':
            return await self._resolve_mcp(uri)
        # ... etc
```

**Usage:**
```python
# Tool can accept any resource URI
result = await ocr_tool.execute({
    'file_uri': 'drive://1A2B3C4D5E6F',  # Google Drive
    # or 'local:///tmp/document.pdf'
    # or 'mcp://database-server/query-result'
})
```

### 4.5 Implementation Checklist

- [ ] Create `pocketportal/protocols/` directory
- [ ] Move `tools/mcp_tools/` → `protocols/mcp/`
- [ ] Update all imports
- [ ] Implement MCP Server interface (expose tools)
- [ ] Implement MCP Client interface (consume tools)
- [ ] Create ResourceResolver for universal URIs
- [ ] Add MCP server/client examples to docs
- [ ] Test bidirectional MCP communication

**Benefits:**
- ✅ Access resources anywhere (Drive, S3, MCP servers)
- ✅ Expose tools to other AI clients
- ✅ True "universal" agent
- ✅ Aligns with MCP vision

---

## Phase 5: Observability & Operations

**Goal:** Production-ready monitoring and operations

### 5.1 OpenTelemetry Integration

**Current:** Structured logging only
**Need:** Distributed tracing, metrics, latency waterfall

**Architecture:**
```python
# pocketportal/observability/
├── __init__.py
├── telemetry.py        # OpenTelemetry wrapper
└── metrics.py          # Custom metrics

# Usage
from pocketportal.observability import trace_span

@trace_span("tool.execute")
async def execute_tool(self, tool_name, parameters):
    # Automatically creates span with:
    # - tool_name
    # - execution time
    # - success/failure
    # - parameters (sanitized)
    pass
```

**Metrics to track:**
- Tool execution latency (p50, p95, p99)
- LLM call latency
- Database query time
- Cache hit rates
- Error rates by tool

**Implementation:**
```toml
# pyproject.toml - Add optional dependency
[project.optional-dependencies]
observability = [
    "opentelemetry-api==1.21.0",
    "opentelemetry-sdk==1.21.0",
    "opentelemetry-exporter-otlp==1.21.0",
]
```

```python
# pocketportal/observability/telemetry.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def init_telemetry(service_name: str = "pocketportal"):
    """Initialize OpenTelemetry"""
    provider = TracerProvider()
    processor = BatchSpanProcessor(OTLPSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    return trace.get_tracer(service_name)
```

### 5.2 Health & Readiness Endpoints

**Add to Web Interface:**
```python
# pocketportal/interfaces/web_interface.py

@app.get("/health")
async def health_check():
    """
    Health check endpoint (for monitoring)
    Returns 200 if service is alive
    """
    return {
        "status": "healthy",
        "version": __version__,
        "timestamp": time.time()
    }

@app.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint (for load balancers)
    Returns 200 if service can accept traffic
    """
    # Check critical dependencies
    checks = {
        "tools_loaded": len(tool_registry.tools) > 0,
        "database": await check_database_connection(),
        "llm_backend": await check_llm_availability(),
    }

    all_ready = all(checks.values())

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks
    }, 200 if all_ready else 503
```

**Benefits:**
- ✅ Kubernetes liveness/readiness probes
- ✅ systemd health monitoring
- ✅ Load balancer health checks

### 5.3 Config Hot-Reloading

**Current:** Requires restart to change config
**Need:** Reload config without downtime

```python
# pocketportal/config/hot_reload.py
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigReloader(FileSystemEventHandler):
    def __init__(self, config_path: str, reload_callback):
        self.config_path = config_path
        self.reload_callback = reload_callback

    def on_modified(self, event):
        if event.src_path == self.config_path:
            logger.info("Config file changed, reloading...")
            asyncio.create_task(self.reload_callback())

# Usage in AgentCore
observer = Observer()
observer.schedule(
    ConfigReloader('config.yaml', self.reload_config),
    path='.',
    recursive=False
)
observer.start()
```

**Hot-reloadable settings:**
- ✅ Prompt templates
- ✅ Tool permissions
- ✅ Rate limits
- ✅ Model preferences
- ❌ NOT reloadable: Database paths, critical infrastructure

### 5.4 Implementation Checklist

- [ ] Add `observability` optional dependency
- [ ] Create telemetry module
- [ ] Wrap key operations with trace spans
- [ ] Add health/readiness endpoints
- [ ] Implement config hot-reload
- [ ] Add metrics dashboard example (Grafana)
- [ ] Document observability setup

**Benefits:**
- ✅ Debug production issues with traces
- ✅ Monitor performance over time
- ✅ Zero-downtime config updates
- ✅ Production-ready operations

---

## Phase 6: Developer Experience

### 6.1 Semantic Versioning Automation

**Current:** Manual version bumps
**Goal:** Automatic versioning from commit messages

**Setup Conventional Commits:**
```bash
# Commit message format
<type>(<scope>): <subject>

# Types
feat: New feature (bumps MINOR)
fix: Bug fix (bumps PATCH)
docs: Documentation only
refactor: Code refactoring
test: Adding tests
chore: Maintenance

# Breaking changes
feat!: Breaking change (bumps MAJOR)
# or
BREAKING CHANGE: in commit body
```

**Examples:**
```bash
# Bumps 4.3.0 → 4.3.1
git commit -m "fix(tools): Resolve shell_safety timeout issue"

# Bumps 4.3.0 → 4.4.0
git commit -m "feat(queue): Add async job queue support"

# Bumps 4.3.0 → 5.0.0
git commit -m "feat!: Replace SQLite with PostgreSQL by default"
```

**Tooling:**
```bash
# Install semantic-release
pip install python-semantic-release

# Configure in pyproject.toml
[tool.semantic_release]
version_variable = "pocketportal/__init__.py:__version__"
branch = "main"
upload_to_pypi = false
build_command = "pip install build && python -m build"
```

### 6.2 Standardized Docstrings

**Goal:** Auto-generate tool catalog from code

**Standard Format (Google Style):**
```python
class StockTickerTool(BaseTool):
    """Get real-time stock prices from Yahoo Finance.

    This tool fetches current stock prices, historical data, and
    basic financial metrics for publicly traded companies.

    Args:
        symbol (str): Stock ticker symbol (e.g., "AAPL", "GOOGL")
        metric (str, optional): Metric to fetch. One of: price, volume, pe_ratio

    Returns:
        dict: Stock data with keys: symbol, price, currency, timestamp

    Raises:
        ToolExecutionError: If symbol not found or API unavailable

    Examples:
        >>> await tool.execute({"symbol": "AAPL", "metric": "price"})
        {'symbol': 'AAPL', 'price': 178.45, 'currency': 'USD'}
    """
```

**Auto-generate catalog:**
```python
# scripts/generate_tool_catalog.py
import inspect
from pocketportal.tools import registry

def generate_catalog():
    """Generate TOOLS_CATALOG.md from tool docstrings"""
    catalog = "# PocketPortal Tool Catalog\n\n"

    for category, tools in registry.tool_categories.items():
        catalog += f"## {category.title()}\n\n"

        for tool_name in tools:
            tool = registry.get_tool(tool_name)
            docstring = inspect.getdoc(tool.__class__)

            catalog += f"### {tool_name}\n\n"
            catalog += f"{docstring}\n\n"

    with open('docs/TOOLS_CATALOG.md', 'w') as f:
        f.write(catalog)
```

### 6.3 Pre-commit Hooks

**Setup:**
```bash
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]

  - repo: local
    hooks:
      - id: pytest-unit
        name: Run unit tests
        entry: pytest -m unit
        language: system
        pass_filenames: false
        always_run: true
```

### 6.4 Implementation Checklist

- [ ] Set up conventional commits guide (CONTRIBUTING.md)
- [ ] Install python-semantic-release
- [ ] Configure automatic version bumping
- [ ] Standardize all tool docstrings (Google style)
- [ ] Create tool catalog generator script
- [ ] Set up pre-commit hooks
- [ ] Add commit message linter
- [ ] Document developer workflow

---

## Migration Strategy

### 7.1 Backwards Compatibility

**All changes MUST be backwards compatible:**

- ✅ Entry points discovery: Keep pkgutil, add entry_points
- ✅ Job queue: Optional, tools work without it
- ✅ MCP elevation: Move but maintain compatibility imports
- ✅ Telemetry: Optional dependency, graceful degradation
- ✅ Config hot-reload: Opt-in feature

**Example: Compatibility Import**
```python
# Maintain old import path
# pocketportal/tools/mcp_tools/__init__.py
import warnings
from pocketportal.protocols.mcp import *

warnings.warn(
    "Importing from pocketportal.tools.mcp_tools is deprecated. "
    "Use pocketportal.protocols.mcp instead.",
    DeprecationWarning
)
```

### 7.2 Rollout Plan

**Phase-by-phase deployment:**

1. **v4.3.0-alpha1**: Documentation + Foundation
   - Doc consolidation
   - Version sync
   - Test markers

2. **v4.3.0-alpha2**: Plugin System
   - Entry points discovery
   - Example plugin
   - Plugin docs

3. **v4.3.0-beta1**: Async Queue
   - Queue interface
   - In-memory implementation
   - Job status tracking

4. **v4.3.0-beta2**: MCP Elevation
   - Restructure to protocols/
   - Universal resource resolver
   - MCP server implementation

5. **v4.3.0-rc1**: Observability
   - OpenTelemetry integration
   - Health endpoints
   - Config hot-reload

6. **v4.3.0**: Final Release
   - All features complete
   - Full test coverage
   - Documentation complete

---

## Success Criteria

### 8.1 Technical Metrics

- [ ] Tool discovery supports entry_points
- [ ] At least one working external plugin
- [ ] Async queue handles heavy tools without blocking
- [ ] MCP accessible as protocol layer
- [ ] OpenTelemetry traces visible in Jaeger
- [ ] Health endpoints return correct status
- [ ] Config changes reload without restart
- [ ] All tests pass with pytest markers
- [ ] 100% backwards compatibility maintained

### 8.2 Documentation Quality

- [ ] Single source of truth for architecture (docs/)
- [ ] Plugin development guide with examples
- [ ] Async job queue usage documented
- [ ] MCP integration examples
- [ ] Observability setup guide
- [ ] Migration guide from 4.1.x
- [ ] Tool catalog auto-generated
- [ ] Conventional commits guide

### 8.3 Developer Experience

- [ ] `pip install pocketportal-tool-X` works
- [ ] Pre-commit hooks prevent bad commits
- [ ] Semantic versioning automatic
- [ ] CI runs unit tests in <1 minute
- [ ] Integration tests in <5 minutes
- [ ] Clear error messages with docs links

---

## Timeline Estimate

**Note:** Following Carmack's principle - no time estimates, just clear steps.

**Order of Implementation:**
1. Foundation (docs, versioning, tests) - First priority
2. Plugin architecture - High value, medium complexity
3. Async queue - High value, medium complexity
4. MCP elevation - Medium value, medium complexity
5. Observability - High value for production, lower priority for MVP
6. Developer tooling - Continuous improvement

**Parallelization Opportunities:**
- Docs + versioning (independent)
- Plugin architecture + async queue (different modules)
- Health endpoints + config reload (different features)

---

## Future Roadmap (v4.4+)

### v4.4.0: Stateful Execution
- Jupyter kernel integration
- Persistent variables across tool calls
- Interactive data exploration

### v4.5.0: GraphRAG
- Knowledge graph layer
- Entity relationship mapping
- Advanced semantic search

### v5.0.0: Breaking Changes (if needed)
- PostgreSQL as default (optional breaking change)
- New config format (YAML → TOML)
- Deprecation removals

---

## Conclusion

This strategic plan transforms PocketPortal from a capable agent platform into a true "one-for-all" solution:

**Before (v4.1.2):**
- ✅ Great for lightweight tasks
- ❌ Blocks on heavy workloads
- ❌ Limited to internal tools
- ❌ Hard to observe in production

**After (v4.3.0):**
- ✅ Handles any workload (async queue)
- ✅ Plugin ecosystem (entry_points)
- ✅ Universal resource access (MCP + URIs)
- ✅ Production-ready (telemetry, health checks)
- ✅ Developer-friendly (semantic versioning, docs)

**Implementation approach:**
1. ✅ Explore first (understand current state)
2. ✅ Plan strategically (this document)
3. 🎯 Execute systematically (phase by phase)
4. ✅ Test independently (closed-loop verification)

---

**Document Version:** 1.0
**Created:** 2025-12-17
**Status:** Ready for Implementation
**Approach:** John Carmack's systematic engineering methodology
