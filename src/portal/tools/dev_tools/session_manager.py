"""
Session Manager - Stateful Code Execution
==========================================

Manages persistent execution sessions for stateful code execution,
similar to ChatGPT Code Interpreter.

Instead of spinning up a new container for every execution,
maintains a persistent connection to a Docker container where
variables persist between calls.

Features:
- Persistent execution environment per chat_id
- Variables persist between executions
- Session isolation (different users don't share state)
- Automatic cleanup of idle sessions
- Docker container-based execution

Architecture:
    SessionManager
        ├─ Session (per chat_id)
        │   └─ Docker container
        └─ Cleanup task (idle session removal)
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExecutionSession:
    """
    Represents a persistent execution session backed by a Docker container.
    """
    session_id: str
    chat_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    last_used_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    container_id: str | None = None
    kernel_id: str | None = None
    execution_count: int = 0
    variables: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update last_used_at timestamp"""
        self.last_used_at = datetime.now(tz=UTC)

    def is_idle(self, idle_timeout_minutes: int = 30) -> bool:
        """Check if session is idle"""
        idle_time = datetime.now(tz=UTC) - self.last_used_at
        return idle_time > timedelta(minutes=idle_timeout_minutes)


class SessionManager:
    """
    Manages stateful Docker execution sessions.

    Provides persistent execution environments where variables
    persist between executions.

    Example:
        manager = SessionManager()

        # First execution
        await manager.execute("chat_123", "x = 42")

        # Second execution (x still exists!)
        result = await manager.execute("chat_123", "print(x)")
        # Output: 42
    """

    def __init__(
        self,
        idle_timeout_minutes: int = 30,
        max_sessions: int = 100,
        backend: str = "docker"
    ):
        """
        Initialize session manager

        Args:
            idle_timeout_minutes: Minutes before idle session cleanup
            max_sessions: Maximum number of concurrent sessions
            backend: Backend type (currently only "docker" is supported)
        """
        self.idle_timeout_minutes = idle_timeout_minutes
        self.max_sessions = max_sessions
        self.backend = backend

        self._sessions: dict[str, ExecutionSession] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._shutdown = False

        logger.info(
            "SessionManager initialized",
            backend=backend,
            idle_timeout=idle_timeout_minutes,
            max_sessions=max_sessions
        )

    async def start(self) -> None:
        """Start the session manager and cleanup task"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("SessionManager started")

    async def stop(self) -> None:
        """Stop the session manager and cleanup all sessions"""
        self._shutdown = True

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cleanup all sessions
        for session in list(self._sessions.values()):
            await self._cleanup_session(session)

        logger.info("SessionManager stopped")

    async def execute(
        self,
        chat_id: str,
        code: str,
        timeout: int = 30
    ) -> dict[str, Any]:
        """
        Execute code in a persistent session

        Args:
            chat_id: Chat/user identifier
            code: Python code to execute
            timeout: Execution timeout in seconds

        Returns:
            Dictionary with:
                - output: Standard output
                - error: Error output (if any)
                - result: Return value (if any)
                - execution_count: Number of executions in this session
        """
        # Get or create session
        session = await self._get_or_create_session(chat_id)
        session.touch()

        logger.debug(
            f"Executing code in session {session.session_id}",
            chat_id=chat_id,
            code_length=len(code)
        )

        try:
            if self.backend != "docker":
                raise ValueError(f"Unknown backend: {self.backend}")
            result = await self._execute_docker(session, code, timeout)
            session.execution_count += 1
            return result

        except Exception as e:
            logger.error(
                f"Execution error: {e}",
                chat_id=chat_id,
                session_id=session.session_id,
                exc_info=True
            )
            return {
                'output': '',
                'error': str(e),
                'result': None,
                'execution_count': session.execution_count
            }

    async def _get_or_create_session(self, chat_id: str) -> ExecutionSession:
        """Get existing session or create a new one"""
        if chat_id in self._sessions:
            return self._sessions[chat_id]

        # Check max sessions
        if len(self._sessions) >= self.max_sessions:
            # Remove oldest idle session
            await self._cleanup_oldest_session()

        # Create new session
        session = ExecutionSession(
            session_id=str(uuid.uuid4()),
            chat_id=chat_id
        )

        await self._init_docker_session(session)
        self._sessions[chat_id] = session

        logger.info(
            f"Created new session {session.session_id}",
            chat_id=chat_id,
            backend=self.backend
        )

        return session

    async def _init_docker_session(self, session: ExecutionSession) -> None:
        """
        Initialize a Docker container for the session

        This would:
        1. Start a container with Python
        2. Keep it running with a long-lived process
        3. Execute code via docker exec
        4. Store container_id in session
        """
        # Placeholder for Docker implementation
        # In a real implementation:
        # - docker run -d python:3.11 python -c "import time; time.sleep(86400)"
        # - Store container ID
        # - Use docker exec for code execution
        logger.debug("Initializing Docker session (placeholder)")
        session.container_id = f"placeholder-{session.session_id[:8]}"

    async def _execute_docker(
        self,
        session: ExecutionSession,
        code: str,
        timeout: int
    ) -> dict[str, Any]:
        """
        Execute code in a Docker container

        Placeholder implementation - in a real system this would:
        1. docker exec <container_id> python -c "<code>"
        2. Capture stdout/stderr
        3. Return results
        """
        logger.debug("Executing via Docker (placeholder)")
        return {
            'output': f'Executed: {code[:50]}...',
            'error': '',
            'result': None,
            'execution_count': session.execution_count + 1
        }

    async def _cleanup_loop(self) -> None:
        """Background task to cleanup idle sessions"""
        while not self._shutdown:
            try:
                await asyncio.sleep(60)  # Check every minute

                # Find idle sessions
                idle_sessions = [
                    session for session in self._sessions.values()
                    if session.is_idle(self.idle_timeout_minutes)
                ]

                # Cleanup idle sessions
                for session in idle_sessions:
                    await self._cleanup_session(session)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cleanup loop error: %s", e, exc_info=True)

    async def _cleanup_session(self, session: ExecutionSession) -> None:
        """Cleanup a single session"""
        logger.info(
            f"Cleaning up session {session.session_id}",
            chat_id=session.chat_id,
            execution_count=session.execution_count
        )

        # Cleanup backend resources
        if session.container_id:
            # docker stop/rm container
            logger.debug("Stopping Docker container (placeholder)")

        # Remove from sessions
        self._sessions.pop(session.chat_id, None)

    async def _cleanup_oldest_session(self) -> None:
        """Cleanup the oldest session to make room for new ones"""
        if not self._sessions:
            return

        oldest_session = min(
            self._sessions.values(),
            key=lambda s: s.last_used_at
        )

        logger.warning(
            "Max sessions reached, cleaning up oldest session",
            session_id=oldest_session.session_id
        )

        await self._cleanup_session(oldest_session)

    async def get_session_info(self, chat_id: str) -> dict[str, Any] | None:
        """
        Get information about a session

        Args:
            chat_id: Chat identifier

        Returns:
            Dictionary with session info or None if not found
        """
        session = self._sessions.get(chat_id)
        if not session:
            return None

        return {
            'session_id': session.session_id,
            'chat_id': session.chat_id,
            'created_at': session.created_at.isoformat(),
            'last_used_at': session.last_used_at.isoformat(),
            'execution_count': session.execution_count,
            'backend': self.backend,
            'is_idle': session.is_idle(self.idle_timeout_minutes)
        }

    async def list_sessions(self) -> dict[str, dict[str, Any]]:
        """
        List all active sessions

        Returns:
            Dictionary of chat_id -> session info
        """
        return {
            chat_id: await self.get_session_info(chat_id)
            for chat_id in self._sessions
        }
