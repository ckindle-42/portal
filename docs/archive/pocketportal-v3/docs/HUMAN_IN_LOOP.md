# Human-in-the-Loop Middleware

## Quick Summary

**Status:** ✅ Complete and Production-Ready
**Version:** Implemented in v4.1.2+
**Purpose:** Safety layer requiring admin approval for high-risk tools

The Human-in-the-Loop (HITL) Middleware intercepts dangerous tool execution (shell commands, git push, docker operations) and requires administrator approval via Telegram before proceeding. This prevents accidental data loss, unauthorized deployments, and security vulnerabilities.

---

## Overview

The Human-in-the-Loop (HITL) Middleware adds a critical safety layer to PocketPortal by requiring administrator approval before executing high-risk tools. This prevents dangerous operations from running automatically and gives you full control over sensitive actions.

## Features

- **🛡️ Safety First**: Intercepts high-risk tool execution
- **⏱️ Configurable Timeouts**: Set how long to wait for approval
- **🔔 Real-time Notifications**: Instant Telegram alerts for confirmations
- **📊 Event Tracking**: Full audit trail via EventBus
- **🔄 Automatic Cleanup**: Expired confirmations are auto-cleaned
- **🎯 Flexible Configuration**: Per-tool or global confirmation settings

## Architecture

```
User Request
    ↓
Tool Execution Requested
    ↓
┌─────────────────────────────────────────┐
│ ToolConfirmationMiddleware              │
│ - Check if tool requires confirmation   │
│ - Create pending confirmation           │
│ - Send notification to admin            │
└─────────────────────────────────────────┘
    ↓
Admin Receives Telegram Message
    ↓
Admin Clicks "Approve" or "Deny"
    ↓
┌─────────────────────────────────────────┐
│ Confirmation Callback Handler           │
│ - Validate admin authorization          │
│ - Update confirmation status            │
│ - Notify middleware                     │
└─────────────────────────────────────────┘
    ↓
Tool Executes (if approved) or Cancelled (if denied)
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Enable/disable confirmation middleware (default: true)
TOOLS_REQUIRE_CONFIRMATION=true

# Admin chat ID for confirmations (optional, uses TELEGRAM_USER_ID if not set)
TOOLS_ADMIN_CHAT_ID=123456789

# Confirmation timeout in seconds (default: 300 = 5 minutes)
TOOLS_CONFIRMATION_TIMEOUT=300
```

### Configuration Options

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TOOLS_REQUIRE_CONFIRMATION` | bool | `true` | Enable/disable confirmation middleware |
| `TOOLS_ADMIN_CHAT_ID` | int | `TELEGRAM_USER_ID` | Telegram chat ID to send confirmation requests |
| `TOOLS_CONFIRMATION_TIMEOUT` | int | `300` | Timeout in seconds (min: 30, max: 3600) |

## High-Risk Tools

The following tools are marked as requiring confirmation by default:

### Shell Operations
- **`shell_safety`** - Executes shell commands
  - Extra protection for dangerous patterns (rm -rf, sudo, dd, etc.)

### Git Operations
- **`git_push`** - Pushes code to remote repository
- **`git_commit`** - Commits changes to repository
- **`git_merge`** - Merges branches

### Docker Operations
- **`docker_stop`** - Stops Docker containers

## Usage Examples

### Basic Flow

1. **User Sends Message**
   ```
   User: "Delete all temporary files with rm -rf /tmp/*"
   ```

2. **Agent Attempts to Execute**
   - AgentCore routes to `shell_safety` tool
   - Detects tool requires confirmation
   - Pauses execution

3. **Admin Gets Notification**
   ```
   ⚠️ Tool Confirmation Required

   Tool: shell_safety
   User Chat: telegram_123456789
   User ID: user_456

   Parameters:
     • command: rm -rf /tmp/*

   Timeout: 300s

   This tool requires your approval before execution.
   Please review and approve or deny.

   [✅ Approve] [❌ Deny]
   ```

4. **Admin Responds**
   - Clicks "✅ Approve" → Tool executes
   - Clicks "❌ Deny" → Tool cancelled, user notified
   - No response → Timeout after 5 minutes, tool cancelled

### Programmatic Usage

#### Basic Confirmation Request

```python
from pocketportal.middleware import ToolConfirmationMiddleware

# Initialize middleware
middleware = ToolConfirmationMiddleware(
    event_bus=event_bus,
    confirmation_sender=send_telegram_confirmation,
    default_timeout=300
)

await middleware.start()

# Request confirmation
approved = await middleware.request_confirmation(
    tool_name="shell_safety",
    parameters={"command": "rm -rf /data"},
    chat_id="telegram_123456789",
    user_id="user_456",
    timeout=600  # Optional custom timeout
)

if approved:
    # Execute tool
    result = await tool.execute(parameters)
else:
    # Cancelled or denied
    raise ToolExecutionError("Tool execution denied by administrator")
```

#### Manual Approval/Denial

```python
# Get pending confirmations
pending = middleware.get_pending_confirmations()
for request in pending:
    print(f"Pending: {request.tool_name} - {request.confirmation_id}")

# Approve a confirmation
success = middleware.approve(
    confirmation_id="abc-123",
    approver_id="admin_789"
)

# Deny a confirmation
success = middleware.deny(
    confirmation_id="abc-123",
    denier_id="admin_789"
)
```

#### Check Pending Confirmations by Chat

```python
# Get all pending confirmations for a specific chat
chat_pending = middleware.get_pending_confirmations(chat_id="telegram_123456789")

print(f"Pending confirmations for chat: {len(chat_pending)}")
for request in chat_pending:
    print(f"  - {request.tool_name}: {request.parameters}")
```

## Integration with AgentCore

The middleware integrates seamlessly with AgentCore:

```python
from pocketportal.core import create_agent_core
from pocketportal.middleware import ToolConfirmationMiddleware

# Create agent core
agent_core = create_agent_core(config)

# Create and inject middleware
middleware = ToolConfirmationMiddleware(
    event_bus=agent_core.event_bus,
    confirmation_sender=send_confirmation_to_admin,
    default_timeout=300
)

agent_core.confirmation_middleware = middleware
await middleware.start()

# Now all tool executions will be intercepted
result = await agent_core.execute_tool(
    tool_name='shell_safety',
    parameters={'command': 'ls'},
    chat_id='test_chat',
    user_id='test_user'
)
```

## Event System

The middleware emits events for monitoring and audit trails:

### TOOL_CONFIRMATION_REQUIRED

Emitted when a confirmation is requested:

```python
{
    'event_type': 'tool_confirmation_required',
    'chat_id': 'telegram_123456789',
    'data': {
        'confirmation_id': 'abc-123',
        'tool_name': 'shell_safety',
        'parameters': {'command': 'rm -rf /tmp/*'},
        'timeout': 300
    },
    'trace_id': 'trace-xyz'
}
```

### TOOL_CONFIRMATION_APPROVED

Emitted when a confirmation is approved (future enhancement).

### TOOL_CONFIRMATION_DENIED

Emitted when a confirmation is denied (future enhancement).

## Security Considerations

### Authorization

- Only the configured admin (via `TOOLS_ADMIN_CHAT_ID`) can approve/deny confirmations
- Unauthorized users receive "⛔ Unauthorized" message

### Timeout Handling

- Confirmations expire after configured timeout
- Expired confirmations are automatically cleaned up
- Tool execution is blocked if confirmation times out

### Audit Trail

- All confirmation requests are logged
- Approval/denial actions are logged with admin ID
- Events are emitted for external monitoring

## Error Handling

### Confirmation Sender Fails

If sending the confirmation request fails:
```python
try:
    await middleware.request_confirmation(...)
except Exception as e:
    logger.error(f"Failed to send confirmation: {e}")
    # Returns False, tool execution is blocked
```

### Timeout Scenarios

- **Timeout during wait**: Returns `False`, tool blocked
- **Admin doesn't respond**: Cleaned up automatically
- **Network issues**: Timeout applies, tool blocked

### Double Approval

Confirmations can only be approved/denied once:
```python
success1 = middleware.approve(confirmation_id)  # True
success2 = middleware.approve(confirmation_id)  # False (already processed)
```

## Advanced Configuration

### Creating Custom High-Risk Tools

To mark your own tools as requiring confirmation:

```python
from pocketportal.tools.base_tool import BaseTool, ToolMetadata, ToolCategory

class MyDangerousTool(BaseTool):
    def __init__(self):
        metadata = ToolMetadata(
            name="my_dangerous_tool",
            description="Does something dangerous",
            category=ToolCategory.AUTOMATION,
            requires_confirmation=True  # ← Set this to True
        )
        super().__init__(metadata)

    async def execute(self, parameters):
        # Tool implementation
        pass
```

### Custom Confirmation Timeout

Set different timeouts for different tools:

```python
# Short timeout for simple operations
approved = await middleware.request_confirmation(
    tool_name="git_push",
    parameters={...},
    chat_id="chat_123",
    timeout=60  # 1 minute
)

# Long timeout for complex operations
approved = await middleware.request_confirmation(
    tool_name="shell_safety",
    parameters={...},
    chat_id="chat_123",
    timeout=1800  # 30 minutes
)
```

### Disabling Confirmations

To disable confirmations globally:

```bash
# In .env
TOOLS_REQUIRE_CONFIRMATION=false
```

Or programmatically:

```python
# Don't inject middleware into agent_core
agent_core.confirmation_middleware = None
```

## Monitoring and Statistics

Get middleware statistics:

```python
stats = middleware.get_stats()
print(stats)
# Output:
# {
#     'total_pending': 2,
#     'active_pending': 2,
#     'running': True
# }
```

## Troubleshooting

### Confirmations Not Appearing

**Problem**: Admin doesn't receive confirmation messages

**Solutions**:
1. Check `TOOLS_ADMIN_CHAT_ID` is set correctly
2. Verify bot has permission to send messages to admin
3. Check logs for "Failed to send confirmation request" errors

### Confirmations Timing Out

**Problem**: Confirmations expire before admin can respond

**Solutions**:
1. Increase `TOOLS_CONFIRMATION_TIMEOUT`
2. Check admin is available to respond
3. Consider setting up multiple admins (future enhancement)

### Tool Executes Without Confirmation

**Problem**: High-risk tool executes without approval

**Solutions**:
1. Verify `TOOLS_REQUIRE_CONFIRMATION=true` in `.env`
2. Check tool has `requires_confirmation=True` in metadata
3. Confirm middleware is properly injected into AgentCore

### Duplicate Confirmation Requests

**Problem**: Multiple confirmation requests for same tool

**Solutions**:
1. Check if user is retrying the request
2. Verify cleanup task is running (not stuck)
3. Check for race conditions in tool execution

## Future Enhancements

Planned improvements for the HITL middleware:

- **Multi-Admin Support**: Multiple admins can approve/deny
- **Approval Policies**: Require N-of-M approvals
- **Persistent Confirmations**: Survive agent restarts
- **Approval Templates**: Pre-approved parameter patterns
- **Conditional Approvals**: Auto-approve based on rules
- **Audit Dashboard**: Web UI for viewing confirmation history

## Testing

Run the test suite:

```bash
# Run all HITL tests
pytest tests/test_human_in_loop_middleware.py -v

# Run specific test
pytest tests/test_human_in_loop_middleware.py::TestToolConfirmationMiddleware::test_request_confirmation_approved -v
```

## API Reference

### ToolConfirmationMiddleware

```python
class ToolConfirmationMiddleware:
    def __init__(
        self,
        event_bus: EventBus,
        confirmation_sender: Callable[[ConfirmationRequest], Awaitable[None]],
        default_timeout: int = 300,
        cleanup_interval: int = 60
    )

    async def start() -> None
    async def stop() -> None

    async def request_confirmation(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        chat_id: str,
        user_id: Optional[str] = None,
        timeout: Optional[int] = None,
        trace_id: Optional[str] = None
    ) -> bool

    def approve(
        self,
        confirmation_id: str,
        approver_id: Optional[str] = None
    ) -> bool

    def deny(
        self,
        confirmation_id: str,
        denier_id: Optional[str] = None
    ) -> bool

    def get_pending_confirmations(
        self,
        chat_id: Optional[str] = None
    ) -> List[ConfirmationRequest]

    def get_stats() -> Dict[str, Any]
```

### ConfirmationRequest

```python
@dataclass
class ConfirmationRequest:
    confirmation_id: str
    tool_name: str
    parameters: Dict[str, Any]
    chat_id: str
    user_id: Optional[str]
    status: ConfirmationStatus
    requested_at: datetime
    timeout_seconds: int
    trace_id: Optional[str] = None

    def is_expired() -> bool
    def to_dict() -> Dict[str, Any]
```

### ConfirmationStatus

```python
class ConfirmationStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/ckindle-42/pocketportal/issues
- Documentation: https://github.com/ckindle-42/pocketportal/docs
