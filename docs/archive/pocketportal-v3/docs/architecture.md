# PocketPortal - Architecture Reference

**Version-Agnostic Documentation - Current State**

---

## Overview

PocketPortal is a production-grade, interface-agnostic AI agent platform with modular architecture, enterprise features, and operational excellence.

**Core Principles:**
- Interface-agnostic core (Telegram, Web, Slack, Discord, API)
- Dependency injection for testability
- Repository pattern for persistence
- Plugin architecture for extensibility
- Production-ready reliability features

**For historical evolution and migration guides, see [docs/archive/HISTORY.md](archive/HISTORY.md).**
**For release-specific changes, see [CHANGELOG.md](../CHANGELOG.md).**

---

## Table of Contents

1. [Conceptual Boundaries](#conceptual-boundaries)
2. [Project Structure](#project-structure)
3. [Core Architecture](#core-architecture)
4. [Design Patterns](#design-patterns)
5. [Key Components](#key-components)
6. [Data Flow](#data-flow)
7. [Extensibility](#extensibility)

---

## Conceptual Boundaries

PocketPortal uses a precise taxonomy to classify components and guide contributors in adding new functionality. Understanding these distinctions is critical for maintaining architectural integrity.

### Tool
**Definition:** An atomic, single-purpose action that performs a discrete task and returns a result.

**Characteristics:**
- Self-contained execution (no persistent state between invocations)
- Accepts parameters, performs operation, returns result
- Examples: Generate QR code, compress file, transcribe audio, query CSV
- Location: `src/pocketportal/tools/`
- Interface: Implements `BaseTool` from `core/interfaces/tool.py`

**Decision Criteria:**
- ✅ Use a **Tool** if: The functionality is invoked on-demand, completes in finite time, and produces a result
- ❌ Do NOT use a **Tool** if: The functionality maintains persistent connections, requires continuous operation, or acts as an integration layer

**Examples:**
- ✅ **Tool**: `QRGenerator` - generates QR code and returns image
- ✅ **Tool**: `FileCompressor` - compresses files and returns archive
- ❌ **Not a Tool**: MCP client (persistent connection → Protocol)
- ❌ **Not a Tool**: Telegram bot (user-facing adapter → Interface)

---

### Protocol
**Definition:** A persistent or standardized integration that maintains connections, implements communication standards, or provides bidirectional interaction with external systems.

**Characteristics:**
- Maintains persistent state or connections
- Implements external protocol specifications (MCP, HTTP long-polling, etc.)
- Provides abstraction over external system interactions
- Examples: MCP client/server, approval workflow, resource resolver
- Location: `src/pocketportal/protocols/`
- Interface: Typically implements custom protocol-specific interfaces

**Decision Criteria:**
- ✅ Use a **Protocol** if: The functionality implements a standardized communication protocol, maintains persistent connections, or coordinates complex multi-step workflows
- ❌ Do NOT use a **Protocol** if: The functionality is a simple one-shot operation or directly handles user interaction

**Examples:**
- ✅ **Protocol**: `MCPConnector` - persistent MCP client connection
- ✅ **Protocol**: `ApprovalProtocol` - coordinates human-in-the-loop approval workflow
- ✅ **Protocol**: `UniversalResourceResolver` - standardized resource access (file://, http://, mcp://)
- ❌ **Not a Protocol**: Simple HTTP GET request (one-shot → Tool)
- ❌ **Not a Protocol**: Telegram message handling (user-facing → Interface)

---

### Interface
**Definition:** A user-facing adapter that translates between external communication channels and the internal agent core.

**Characteristics:**
- Handles user interaction (receiving input, sending output)
- Implements `BaseInterface` contract
- Translates between external format and internal `ProcessingResult`
- Examples: Telegram bot, Web server, Slack adapter, CLI
- Location: `src/pocketportal/interfaces/`
- Interface: Implements `BaseInterface` from `core/interfaces/agent_interface.py`

**Decision Criteria:**
- ✅ Use an **Interface** if: The functionality directly interacts with end users through a communication channel (chat, web, API, CLI)
- ❌ Do NOT use an **Interface** if: The functionality is an internal component or doesn't handle user I/O

**Examples:**
- ✅ **Interface**: `TelegramInterface` - receives/sends Telegram messages
- ✅ **Interface**: `WebInterface` - serves HTTP/WebSocket endpoints
- ❌ **Not an Interface**: Job queue (internal component → Core)
- ❌ **Not an Interface**: Cost tracker (middleware → Middleware)

---

### Classification Guide

When adding new functionality, ask these questions in order:

1. **Does it directly interact with end users?**
   - YES → **Interface** (e.g., Discord bot, voice assistant)
   - NO → Continue to question 2

2. **Does it maintain persistent connections or implement a protocol standard?**
   - YES → **Protocol** (e.g., WebSocket handler, OAuth provider)
   - NO → Continue to question 3

3. **Does it perform a single, atomic operation?**
   - YES → **Tool** (e.g., image resizer, calculator, file reader)
   - NO → Consider **Core Component** or **Middleware**

---

## Project Structure

```
pocketportal/                       # Repository root
├── src/
│   └── pocketportal/              # Main Python package (strict src-layout)
│       ├── __init__.py            # Package entry point & version
│       │
│       ├── core/                  # Core Engine & Orchestration
│       │   ├── agent_core.py      # Main agent orchestration (AgentCore class)
│       │   ├── context_manager.py # Conversation history
│       │   ├── event_broker.py    # Event distribution (DAO pattern)
│       │   ├── event_bus.py       # Real-time event system
│       │   ├── exceptions.py      # Structured exceptions with error codes
│       │   ├── prompt_manager.py  # External prompt templates
│       │   ├── structured_logger.py # JSON logging with traces
│       │   ├── job_worker.py      # Background job processing
│       │   ├── factories.py       # Dependency injection factories
│       │   ├── interfaces/        # Core contracts (BaseTool, etc.)
│       │   ├── registries/        # Registration schemas (ToolManifest)
│       │   └── types.py           # Type definitions
│       │
│       ├── interfaces/            # User-Facing Adapters
│       │   ├── base.py            # Abstract BaseInterface
│       │   ├── telegram/          # Telegram bot interface
│       │   │   ├── interface.py   # Main bot logic
│       │   │   └── renderers.py   # UI rendering (buttons, menus)
│       │   └── web/               # Web interface
│       │       └── server.py      # FastAPI + WebSocket
│       │
│       ├── routing/               # Intelligent Model Selection
│       │   ├── intelligent_router.py  # Routing strategies
│       │   ├── task_classifier.py     # Task complexity analysis
│       │   ├── model_registry.py      # Available models catalog
│       │   ├── model_backends.py      # Backend implementations
│       │   ├── execution_engine.py    # LLM execution with circuit breaker
│       │   └── response_formatter.py  # Output formatting
│       │
│       ├── security/              # Security Components
│       │   ├── middleware.py      # Security middleware
│       │   ├── security_module.py # Rate limiting, validation
│       │   ├── sqlite_rate_limiter.py # Persistent rate limits
│       │   └── sandbox/           # Isolated execution
│       │       └── docker_sandbox.py  # Docker isolation
│       │
│       ├── tools/                 # Extensible Tool System
│       │   ├── __init__.py        # Tool registry (auto-discovery)
│       │   ├── system_tools/      # System operations
│       │   ├── git_tools/         # Git integration
│       │   ├── web_tools/         # HTTP/web scraping
│       │   ├── data_tools/        # CSV, JSON, compression, QR
│       │   ├── media_tools/       # Media processing
│       │   │   └── audio/         # Whisper transcription
│       │   ├── automation_tools/  # Scheduling, shell execution
│       │   ├── dev_tools/         # Python environment, sessions
│       │   ├── knowledge/         # Knowledge base (semantic search)
│       │   └── document_processing/ # PDF OCR, Office docs
│       │
│       ├── protocols/             # Protocol-Level Integrations
│       │   ├── mcp/               # Model Context Protocol (bidirectional)
│       │   │   ├── mcp_connector.py # MCP client
│       │   │   ├── mcp_server.py    # MCP server
│       │   │   ├── mcp_registry.py  # Server registry
│       │   │   └── security_policy.py # MCP access control
│       │   ├── approval/          # Human-in-the-Loop protocol
│       │   │   └── protocol.py    # Approval workflow
│       │   └── resource_resolver.py # Universal resource access
│       │
│       ├── persistence/           # Data Access Layer (DAO Pattern)
│       │   ├── repositories.py    # Abstract interfaces
│       │   ├── sqlite_impl.py     # SQLite implementations
│       │   └── inmemory_impl.py   # In-memory implementations
│       │
│       ├── observability/         # Monitoring & Reliability
│       │   ├── __init__.py        # OpenTelemetry setup
│       │   ├── tracer.py          # Distributed tracing
│       │   ├── metrics.py         # Prometheus metrics
│       │   ├── health.py          # Health check endpoints
│       │   ├── config_watcher.py  # Hot-reload configuration
│       │   ├── watchdog.py        # Component monitoring & auto-recovery
│       │   └── log_rotation.py    # Automated log management
│       │
│       ├── middleware/            # Application Middleware
│       │   └── cost_tracker.py    # Cost tracking & business metrics
│       │
│       ├── config/                # Configuration Management
│       │   ├── settings.py        # Settings loader
│       │   ├── validator.py       # Configuration validation
│       │   ├── secrets.py         # Secret provider abstraction
│       │   └── schemas/           # Pydantic schemas
│       │       ├── settings_schema.py # Main config schema
│       │       └── __init__.py    # Schema exports
│       │
│       ├── utils/                 # Shared Utilities
│       │   └── (helper functions)
│       │
│       ├── lifecycle.py           # Bootstrap & runtime management
│       └── cli.py                 # Command-line interface
│
├── tests/                         # Test Suite
│   ├── unit/                      # Unit tests (fast, no I/O)
│   ├── integration/               # Integration tests (Docker, network)
│   └── e2e/                       # End-to-end tests (formerly scripts/verification/)
│
├── docs/                          # Documentation
│   ├── architecture.md            # This file
│   ├── setup.md                   # Installation guide
│   ├── security/                  # Security documentation
│   └── archive/                   # Historical documents
│       ├── HISTORY.md             # Evolution history
│       └── SETUP_V3.md            # Legacy v3.x setup
│
├── scripts/                       # Utility Scripts (optional tooling)
│
├── pyproject.toml                 # Modern Python package config
└── README.md                      # Project overview
```

---

## Core Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│                   User Interfaces                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Telegram   │  │   Web UI     │  │   Slack      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                ┌────────────▼────────────┐
                │  Security Middleware   │
                │  • Rate Limiting       │
                │  • Input Validation    │
                │  • Sandboxing          │
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │      Agent Core         │
                │  ┌──────────────────┐  │
                │  │  Context Manager │  │
                │  │  Event Broker    │  │
                │  │  Prompt Manager  │  │
                │  │  Job Worker Pool │  │
                │  └──────────────────┘  │
                └────────────┬────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼─────┐      ┌─────▼──────┐     ┌─────▼─────┐
    │ Routing  │      │   Tools     │     │Persistence│
    │ System   │      │  Registry   │     │   Layer   │
    └────┬─────┘      └─────┬──────┘     └─────┬─────┘
         │                  │                   │
    ┌────▼─────┐      ┌─────▼──────┐     ┌─────▼─────┐
    │   LLM    │      │Tool Exec   │     │Repository │
    │ Backends │      └────────────┘     │Implements │
    │+Circuit  │                          └───────────┘
    │ Breaker  │
    └──────────┘
```

### Component Descriptions

#### 1. **Core Engine** (`core/agent_core.py`)
- Orchestrates all agent operations
- Manages conversation flow
- Coordinates tool execution
- Handles error propagation
- Emits events for real-time feedback

**Key Methods:**
- `process_message()`: Main entry point for message processing
- `execute_tool()`: Tool execution with error handling
- `generate_response()`: LLM response generation

#### 2. **Context Manager** (`core/context_manager.py`)
- Maintains conversation history
- Implements sliding window for context limits
- Uses Repository pattern for persistence
- Supports multiple storage backends

**Key Features:**
- Per-user conversation isolation
- Automatic context pruning
- Search capabilities
- Export/import functionality

#### 3. **Event Broker** (`core/event_broker.py`)
- Distributes events across system
- Abstract interface (DAO pattern)
- In-memory and Redis implementations
- Real-time status updates

**Event Types:**
- `thinking_started`, `thinking_stopped`
- `tool_execution_started`, `tool_execution_completed`
- `response_started`, `response_completed`
- `error_occurred`

#### 4. **Routing System** (`routing/`)
- Intelligent model selection
- Task complexity analysis
- Circuit breaker pattern for reliability
- Fallback chains

**Routing Strategies:**
- Complexity-based (fast models for simple queries)
- Capability-based (code models for programming)
- Cost-based (optimize for token usage)
- Custom policies

#### 5. **Tool Registry** (`tools/__init__.py`)
- Automatic tool discovery via `pkgutil`
- Plugin support via entry points
- Lazy loading for performance
- Security manifest enforcement

**Tool Categories:**
- System: Process monitoring, clipboard, stats
- Data: CSV, JSON, compression, QR codes
- Web: HTTP client, web scraping
- Media: Audio transcription, image processing
- Documents: PDF, Word, Excel, PowerPoint
- Knowledge: Semantic search, RAG
- Development: Python environments, sessions
- Automation: Scheduling, shell execution

---

## Design Patterns

### 1. Repository Pattern (DAO)

**Purpose**: Decouple persistence logic from business logic

**Implementation**:
```python
# Abstract interface
class ConversationRepository(ABC):
    @abstractmethod
    async def add_message(self, chat_id: str, role: str, content: str) -> None:
        pass

# Concrete implementation
class SQLiteConversationRepository(ConversationRepository):
    async def add_message(self, chat_id: str, role: str, content: str) -> None:
        # SQLite-specific implementation
        ...

# Usage (dependency injection)
repo = SQLiteConversationRepository(db_path)
context_manager = ContextManager(repository=repo)
```

**Benefits**:
- Easy to test (mock repositories)
- Swap backends without changing core logic
- Support multiple storage systems

**Repositories**:
- `ConversationRepository`: Chat history
- `KnowledgeRepository`: Document storage + embeddings
- `JobRepository`: Background job queue

---

### 2. Factory Pattern (Dependency Injection)

**Purpose**: Centralize component creation and configuration

**Implementation**:
```python
# core/factories.py
class DependencyContainer:
    def __init__(self, config: Config):
        self.config = config

    def create_context_manager(self) -> ContextManager:
        repo = self.create_conversation_repository()
        return ContextManager(repository=repo)

    def create_agent_core(self) -> AgentCore:
        return AgentCore(
            context_manager=self.create_context_manager(),
            router=self.create_router(),
            tool_registry=self.create_tool_registry(),
            event_broker=self.create_event_broker()
        )

# Usage
container = DependencyContainer(config)
agent = container.create_agent_core()
```

**Benefits**:
- Simplified testing (inject mocks)
- Consistent configuration
- Easy customization

---

### 3. Circuit Breaker Pattern

**Purpose**: Prevent cascading failures from unavailable backends

**States**:
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Backend failing, requests fail fast
- **HALF_OPEN**: Testing recovery, limited requests allowed

**Implementation**:
```python
# routing/execution_engine.py
class ExecutionEngine:
    def __init__(self):
        self.circuit_breakers = {
            'ollama': CircuitBreaker(failure_threshold=3, timeout=60),
            'lm_studio': CircuitBreaker(failure_threshold=3, timeout=60),
        }

    async def execute(self, backend: str, prompt: str):
        breaker = self.circuit_breakers[backend]
        if breaker.is_open():
            raise BackendUnavailableError(f"{backend} circuit open")

        try:
            result = await self._execute_llm(backend, prompt)
            breaker.record_success()
            return result
        except Exception as e:
            breaker.record_failure()
            raise
```

**Benefits**:
- Fast failure detection
- Automatic recovery testing
- System stability under failures

---

### 4. Observer Pattern (Event Bus)

**Purpose**: Decouple components via event-driven architecture

**Implementation**:
```python
# core/event_bus.py
class EventBus:
    def __init__(self):
        self._subscribers = defaultdict(list)

    def subscribe(self, event_type: str, callback: Callable):
        self._subscribers[event_type].append(callback)

    async def publish(self, event: Event):
        for callback in self._subscribers[event.type]:
            try:
                await callback(event)
            except Exception:
                # Log but don't propagate
                pass

# Usage
bus.subscribe('thinking_started', show_spinner)
bus.subscribe('tool_execution_started', log_tool_use)
await bus.publish(Event('thinking_started', data={...}))
```

**Benefits**:
- Loose coupling
- Real-time UI updates
- Extensible via plugins

---

### 5. Strategy Pattern (Routing)

**Purpose**: Select LLM model based on task characteristics

**Strategies**:
- `ComplexityStrategy`: Route by task complexity
- `CapabilityStrategy`: Route by required capabilities
- `CostStrategy`: Minimize token usage
- `LatencyStrategy`: Minimize response time
- `CustomStrategy`: User-defined rules

**Implementation**:
```python
# routing/intelligent_router.py
class IntelligentRouter:
    def __init__(self, strategy: RoutingStrategy):
        self.strategy = strategy

    async def route(self, message: str) -> Model:
        task = self.classify_task(message)
        return self.strategy.select_model(task)

# Usage
router = IntelligentRouter(ComplexityStrategy())
model = await router.route("What's 2+2?")  # Returns fast model
```

---

## Key Components

### Lifecycle Management (`lifecycle.py`)

**Responsibilities**:
- Application bootstrap
- Dependency initialization
- Signal handling (SIGTERM, SIGINT)
- Graceful shutdown
- Priority-based cleanup

**Shutdown Phases**:
1. **CRITICAL**: Stop accepting new work
2. **HIGH**: Flush event queues
3. **NORMAL**: Complete in-flight tasks
4. **LOW**: Close network connections
5. **LOWEST**: Persist state
6. **FINAL**: Release resources

**Features**:
- Timeout handling per phase
- Task draining
- Active task tracking
- Health status during shutdown

---

### Watchdog System (`observability/watchdog.py`)

**Responsibilities**:
- Monitor critical components (workers, interfaces)
- Detect failures (crashes, hangs, resource leaks)
- Auto-recovery with exponential backoff
- Integration with health checks

**Monitored Components**:
- Background job workers
- Interface connections
- Event broker
- LLM backends (via circuit breaker)

**Recovery Strategies**:
- Restart failed workers
- Reconnect dropped interfaces
- Clear resource leaks
- Alert on repeated failures

---

### Log Rotation (`observability/log_rotation.py`)

**Responsibilities**:
- Size-based rotation (default: 10MB)
- Time-based rotation (default: daily)
- Automatic compression (gzip)
- Old log cleanup

**Features**:
- Async I/O (non-blocking)
- Python logging integration
- Configurable retention
- Graceful degradation

---

### Job Queue (`core/job_worker.py`)

**Responsibilities**:
- Background task execution
- Priority queueing (LOW, NORMAL, HIGH, CRITICAL)
- Automatic retry with backoff
- Dead letter queue for failures

**Features**:
- Worker pool with concurrency control
- Stale job detection
- Event integration for status updates
- CLI tools for queue management

**Use Cases**:
- Heavy computations (video processing)
- Long-running tasks (large OCR jobs)
- Scheduled operations
- Batch processing

---

## Data Flow

### Message Processing Flow

```
1. User sends message
   ↓
2. Interface receives message
   ↓
3. Security Middleware validates
   ↓
4. Agent Core processes
   ↓
5. Context Manager retrieves history
   ↓
6. Router selects appropriate model
   ↓
7. Execution Engine calls LLM (with circuit breaker)
   ↓
8. LLM response parsed
   ↓
9. Tool execution (if needed)
   ↓
10. Response formatted
   ↓
11. Context Manager saves conversation
   ↓
12. Interface renders response
   ↓
13. User receives response
```

### Event Flow

```
Core Engine emits event
   ↓
Event Bus receives
   ↓
Subscribers notified concurrently
   ├─→ Interface (show spinner)
   ├─→ Logger (audit trail)
   ├─→ Metrics (Prometheus)
   └─→ Plugins (custom handlers)
```

---

## Extensibility

### Adding a New Tool

```python
# 1. Create tool file in appropriate directory
# src/pocketportal/tools/my_tools/awesome_tool.py

from pocketportal.core.interfaces import BaseTool
from pocketportal.core.registries import ToolManifest, SecurityScope

class AwesomeTool(BaseTool):
    def __init__(self):
        super().__init__(
            manifest=ToolManifest(
                name="awesome_tool",
                description="Does something awesome",
                security_scope=SecurityScope.READ_ONLY,
                trust_level=TrustLevel.CORE
            )
        )

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # Implementation
        return {"result": "awesome"}

# 2. That's it! Auto-discovered on startup
```

### Adding a New Interface

```python
# src/pocketportal/interfaces/slack/interface.py

from pocketportal.interfaces.base import BaseInterface

class SlackInterface(BaseInterface):
    async def start(self):
        # Connect to Slack API
        pass

    async def send_message(self, chat_id: str, message: str):
        # Send to Slack
        pass

    async def receive_message(self):
        # Listen for messages
        pass
```

### Adding a Plugin (Third-Party)

```python
# my_plugin_package/pyproject.toml
[project.entry-points."pocketportal.tools"]
my_tool = "my_plugin_package:MyTool"

# Installed via: pip install my_plugin_package
# Auto-discovered on PocketPortal startup
```

---

## Design Principles

1. **Dependency Injection**: All components receive dependencies, not hardcoded
2. **Interface Segregation**: Core knows nothing about interface specifics
3. **Event-Driven**: Real-time feedback via EventBus
4. **Fail-Safe**: Errors isolated, context saved immediately
5. **Configurable**: No hardcoded values, all via config
6. **Testable**: Clean interfaces, easy to mock
7. **Observable**: Comprehensive logging, metrics, and tracing
8. **Reliable**: Circuit breakers, retries, watchdogs

---

## Performance Characteristics

### Startup Time
- **Cold Start**: ~500ms (lazy loading)
- **With All Tools**: ~1-2 seconds (if all dependencies pre-installed)

### Memory Usage
- **Base**: ~20MB (core only)
- **With Tools**: ~50-100MB (varies by active tools)
- **With LLM**: +Model size (loaded by Ollama/LM Studio)

### Response Time
- **Simple Query**: 50-200ms (fast model)
- **Complex Query**: 500ms-2s (large model)
- **Tool Execution**: Varies by tool (50ms-10s+)

### Scalability
- **Concurrent Users**: 10-100 (single instance)
- **Messages/Second**: 5-20 (depends on model)
- **Tool Executions**: Limited by worker pool (default: 5 workers)

---

## Security Architecture

### Defense in Depth

1. **Input Validation**: All user input sanitized
2. **Rate Limiting**: Per-user request limits
3. **Sandboxing**: Docker isolation for code execution
4. **Authentication**: Token-based auth for interfaces
5. **Authorization**: Role-based access control
6. **Audit Logging**: All actions logged with trace IDs
7. **Secret Management**: Centralized secret provider
8. **MCP Security Policy**: Granular resource access control

### Security Scopes

Tools are categorized by security impact:
- `READ_ONLY`: Cannot modify system
- `READ_WRITE`: File I/O allowed
- `SYSTEM_MODIFY`: Can change system state
- `NETWORK_ACCESS`: Can make external requests
- `CODE_EXECUTION`: Can execute arbitrary code

---

## Testing Strategy

### Unit Tests (`tests/unit/`)
- Fast (<100ms per test)
- No I/O, no network, no database
- Mock all dependencies
- Test business logic in isolation

### Integration Tests (`tests/integration/`)
- Test component interactions
- May require Docker, network, database
- Test repository implementations
- Test LLM backend connections

### End-to-End Tests (`tests/e2e/`)
- Full system tests
- Real LLM, real database
- Test user workflows
- Validate production scenarios

---

## Configuration

### Configuration Sources (Priority Order)

1. **Environment Variables** (highest priority)
2. **Config File** (`~/.config/pocketportal/config.yaml`)
3. **Defaults** (lowest priority)

### Configuration Schema

```yaml
interfaces:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
  web:
    enabled: false
    port: 8000

llm:
  default_backend: "ollama"
  ollama:
    host: "http://localhost:11434"
    model: "qwen2.5:7b-instruct-q4_K_M"
  circuit_breaker_enabled: true

security:
  rate_limit:
    messages_per_minute: 30
  sandbox:
    enabled: false

observability:
  logging:
    level: "INFO"
  watchdog:
    enabled: true
  log_rotation:
    enabled: true

shutdown_timeout_seconds: 30
```

---

## Documentation References

- **Installation**: [docs/setup.md](setup.md)
- **Release Notes**: [CHANGELOG.md](../CHANGELOG.md)
- **Evolution History**: [docs/archive/HISTORY.md](archive/HISTORY.md)
- **Legacy v3.x Setup**: [docs/archive/SETUP_V3.md](archive/SETUP_V3.md)
- **Security**: [docs/security/](security/)

---

**Last Updated**: December 2025
**Maintained By**: PocketPortal Team

For questions, issues, or contributions: https://github.com/ckindle-42/pocketportal
