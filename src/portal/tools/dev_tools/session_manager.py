"""
Session Manager - Stateful Code Execution
==========================================

Manages persistent execution sessions for stateful code execution,
similar to Jupyter notebooks or ChatGPT Code Interpreter.

Instead of spinning up a new container for every execution,
maintains a persistent connection to a container/kernel where
variables persist between calls.

Features:
- Persistent execution environment per chat_id
- Variables persist between executions
- Session isolation (different users don't share state)
- Automatic cleanup of idle sessions
- Support for both Docker containers and Jupyter kernels

Architecture:
    SessionManager
        ├─ Session (per chat_id)
        │   ├─ Docker container OR
        │   └─ Jupyter kernel
        └─ Cleanup task (idle session removal)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ExecutionSession:
    """
    Represents a persistent execution session

    This could be backed by:
    - A Docker container with persistent Python process
    - A Jupyter kernel
    - An IPython kernel
    """
    session_id: str
    chat_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: datetime = field(default_factory=datetime.utcnow)
    container_id: Optional[str] = None
    kernel_id: Optional[str] = None
    execution_count: int = 0
    variables: Dict[str, Any] = field(default_factory=dict)

    def touch(self):
        """Update last_used_at timestamp"""
        self.last_used_at = datetime.utcnow()

    def is_idle(self, idle_timeout_minutes: int = 30) -> bool:
        """Check if session is idle"""
        idle_time = datetime.utcnow() - self.last_used_at
        return idle_time > timedelta(minutes=idle_timeout_minutes)


class SessionManager:
    """
    Manages stateful execution sessions

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
            backend: Backend type ("docker" or "jupyter")
        """
        self.idle_timeout_minutes = idle_timeout_minutes
        self.max_sessions = max_sessions
        self.backend = backend

        self._sessions: Dict[str, ExecutionSession] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown = False

        logger.info(
            "SessionManager initialized",
            backend=backend,
            idle_timeout=idle_timeout_minutes,
            max_sessions=max_sessions
        )

    async def start(self):
        """Start the session manager and cleanup task"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("SessionManager started")

    async def stop(self):
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
    ) -> Dict[str, Any]:
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

        Example:
            result = await manager.execute("chat_123", "x = 42")
            result = await manager.execute("chat_123", "print(x)")
            # Output: 42
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
            # Execute code based on backend
            if self.backend == "docker":
                result = await self._execute_docker(session, code, timeout)
            elif self.backend == "jupyter":
                result = await self._execute_jupyter(session, code, timeout)
            else:
                raise ValueError(f"Unknown backend: {self.backend}")

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

        # Initialize backend
        if self.backend == "docker":
            await self._init_docker_session(session)
        elif self.backend == "jupyter":
            await self._init_jupyter_session(session)

        self._sessions[chat_id] = session

        logger.info(
            f"Created new session {session.session_id}",
            chat_id=chat_id,
            backend=self.backend
        )

        return session

    async def _init_docker_session(self, session: ExecutionSession):
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
        logger.debug(f"Initializing Docker session (placeholder)")
        session.container_id = f"placeholder-{session.session_id[:8]}"

    async def _init_jupyter_session(self, session: ExecutionSession):
        """
        Initialize a Jupyter kernel for the session

        This would:
        1. Start a Jupyter kernel
        2. Store kernel_id in session
        3. Use jupyter_client to execute code
        """
        # Placeholder for Jupyter implementation
        logger.debug(f"Initializing Jupyter session (placeholder)")
        session.kernel_id = f"placeholder-{session.session_id[:8]}"

    async def _execute_docker(
        self,
        session: ExecutionSession,
        code: str,
        timeout: int
    ) -> Dict[str, Any]:
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

    async def _execute_jupyter(
        self,
        session: ExecutionSession,
        code: str,
        timeout: int
    ) -> Dict[str, Any]:
        """
        Execute code in a Jupyter kernel

        Placeholder implementation - in a real system this would:
        1. Use jupyter_client to execute code
        2. Capture output
        3. Return results
        """
        logger.debug("Executing via Jupyter (placeholder)")
        return {
            'output': f'Executed: {code[:50]}...',
            'error': '',
            'result': None,
            'execution_count': session.execution_count + 1
        }

    async def _cleanup_loop(self):
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
                logger.error(f"Cleanup loop error: {e}", exc_info=True)

    async def _cleanup_session(self, session: ExecutionSession):
        """Cleanup a single session"""
        logger.info(
            f"Cleaning up session {session.session_id}",
            chat_id=session.chat_id,
            execution_count=session.execution_count
        )

        # Cleanup backend resources
        if session.container_id:
            # docker stop/rm container
            logger.debug(f"Stopping Docker container (placeholder)")

        if session.kernel_id:
            # Shutdown Jupyter kernel
            logger.debug(f"Shutting down Jupyter kernel (placeholder)")

        # Remove from sessions
        self._sessions.pop(session.chat_id, None)

    async def _cleanup_oldest_session(self):
        """Cleanup the oldest session to make room for new ones"""
        if not self._sessions:
            return

        oldest_session = min(
            self._sessions.values(),
            key=lambda s: s.last_used_at
        )

        logger.warning(
            f"Max sessions reached, cleaning up oldest session",
            session_id=oldest_session.session_id
        )

        await self._cleanup_session(oldest_session)

    async def get_session_info(self, chat_id: str) -> Optional[Dict[str, Any]]:
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

    async def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active sessions

        Returns:
            Dictionary of chat_id -> session info
        """
        return {
            chat_id: await self.get_session_info(chat_id)
            for chat_id in self._sessions
        }
