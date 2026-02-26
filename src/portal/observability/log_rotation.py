"""
Log Rotation for Portal
===============================

Automated log file rotation with:
- Size-based rotation
- Time-based rotation
- Compression of old logs
- Automatic cleanup of old rotated logs

v4.7.0: Initial implementation for production log management
"""

import asyncio
import gzip
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class RotationStrategy(Enum):
    """Log rotation strategies"""
    SIZE = "size"           # Rotate when file reaches size limit
    TIME = "time"           # Rotate at time intervals
    SIZE_AND_TIME = "both"  # Rotate on either condition


@dataclass
class RotationConfig:
    """Configuration for log rotation"""

    # Rotation strategy
    strategy: RotationStrategy = RotationStrategy.SIZE_AND_TIME

    # Size-based rotation
    max_bytes: int = 10 * 1024 * 1024  # 10 MB default

    # Time-based rotation
    rotation_interval_hours: int = 24  # Rotate daily by default

    # Retention
    backup_count: int = 7  # Keep 7 rotated files

    # Compression
    compress_rotated: bool = True

    # Cleanup
    cleanup_enabled: bool = True
    cleanup_older_than_days: int = 30


class LogRotator:
    """
    Manages log file rotation and cleanup.

    Features:
    - Automatic rotation based on size or time
    - Compression of rotated logs (gzip)
    - Cleanup of old rotated logs
    - Async operation for non-blocking I/O

    Example:
        >>> rotator = LogRotator(
        ...     log_file="/var/log/portal/app.log",
        ...     config=RotationConfig(max_bytes=10*1024*1024)
        ... )
        >>> await rotator.start()
    """

    def __init__(
        self,
        log_file: Path | str,
        config: RotationConfig | None = None,
        on_rotate: Callable[[str, str], None] | None = None
    ):
        """
        Initialize log rotator.

        Args:
            log_file: Path to the log file to rotate
            config: Rotation configuration
            on_rotate: Optional callback when rotation occurs (old_path, new_path)
        """
        self.log_file = Path(log_file)
        self.config = config or RotationConfig()
        self.on_rotate = on_rotate

        self._running = False
        self._task: asyncio.Task | None = None
        self._last_rotation_time = time.time()

        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "LogRotator initialized",
            log_file=str(self.log_file),
            strategy=self.config.strategy.value,
            max_bytes=self.config.max_bytes,
            rotation_hours=self.config.rotation_interval_hours
        )

    async def start(self):
        """Start the log rotation background task"""
        if self._running:
            logger.warning("LogRotator already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._rotation_loop())
        logger.info("LogRotator started")

    async def stop(self):
        """Stop the log rotation background task"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("LogRotator stopped")

    async def _rotation_loop(self):
        """Main rotation loop"""
        check_interval = 60  # Check every minute

        try:
            while self._running:
                await asyncio.sleep(check_interval)

                if await self._should_rotate():
                    await self.rotate()

                # Periodic cleanup
                if self.config.cleanup_enabled:
                    await self._cleanup_old_logs()

        except asyncio.CancelledError:
            logger.info("Rotation loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in rotation loop: {e}", exc_info=True)

    async def _should_rotate(self) -> bool:
        """Check if log file should be rotated"""
        if not self.log_file.exists():
            return False

        # Check size-based rotation
        if self.config.strategy in (RotationStrategy.SIZE, RotationStrategy.SIZE_AND_TIME):
            file_size = self.log_file.stat().st_size
            if file_size >= self.config.max_bytes:
                logger.debug(f"Log file size ({file_size} bytes) exceeds limit ({self.config.max_bytes} bytes)")
                return True

        # Check time-based rotation
        if self.config.strategy in (RotationStrategy.TIME, RotationStrategy.SIZE_AND_TIME):
            time_since_rotation = time.time() - self._last_rotation_time
            rotation_interval_seconds = self.config.rotation_interval_hours * 3600

            if time_since_rotation >= rotation_interval_seconds:
                logger.debug(f"Time since last rotation ({time_since_rotation}s) exceeds interval ({rotation_interval_seconds}s)")
                return True

        return False

    async def rotate(self):
        """
        Rotate the log file.

        This will:
        1. Rename current log file with timestamp
        2. Optionally compress the rotated file
        3. Create new empty log file
        4. Trigger cleanup of old rotated files
        """
        if not self.log_file.exists():
            logger.warning(f"Log file {self.log_file} does not exist, skipping rotation")
            return

        try:
            # Generate rotated filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_name = f"{self.log_file.stem}_{timestamp}{self.log_file.suffix}"
            rotated_path = self.log_file.parent / rotated_name

            logger.info(f"Rotating log file: {self.log_file} -> {rotated_path}")

            # Rename current log file
            self.log_file.rename(rotated_path)

            # Create new empty log file
            self.log_file.touch()

            # Compress rotated file if enabled
            if self.config.compress_rotated:
                await self._compress_log(rotated_path)

            # Update last rotation time
            self._last_rotation_time = time.time()

            # Trigger callback if provided
            if self.on_rotate:
                try:
                    self.on_rotate(str(self.log_file), str(rotated_path))
                except Exception as e:
                    logger.error(f"Error in rotation callback: {e}")

            logger.info("Log rotation completed successfully")

        except Exception as e:
            logger.error(f"Failed to rotate log file: {e}", exc_info=True)

    async def _compress_log(self, log_path: Path):
        """
        Compress a log file with gzip.

        Args:
            log_path: Path to log file to compress
        """
        try:
            compressed_path = log_path.with_suffix(log_path.suffix + '.gz')

            logger.debug(f"Compressing {log_path} -> {compressed_path}")

            # Compress file
            await asyncio.to_thread(self._compress_file, log_path, compressed_path)

            # Remove original uncompressed file
            log_path.unlink()

            logger.debug(f"Compression completed: {compressed_path}")

        except Exception as e:
            logger.error(f"Failed to compress log file {log_path}: {e}")

    @staticmethod
    def _compress_file(src: Path, dst: Path):
        """Compress file using gzip (blocking I/O)"""
        with open(src, 'rb') as f_in:
            with gzip.open(dst, 'wb') as f_out:
                f_out.writelines(f_in)

    async def _cleanup_old_logs(self):
        """Clean up old rotated log files"""
        try:
            # Find all rotated log files
            pattern = f"{self.log_file.stem}_*{self.log_file.suffix}*"
            rotated_files = sorted(
                self.log_file.parent.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True  # Newest first
            )

            # Keep only backup_count newest files
            if len(rotated_files) > self.config.backup_count:
                files_to_delete = rotated_files[self.config.backup_count:]

                for file_path in files_to_delete:
                    logger.debug(f"Deleting old rotated log: {file_path}")
                    file_path.unlink()

            # Delete files older than retention period
            if self.config.cleanup_older_than_days > 0:
                cutoff_time = time.time() - (self.config.cleanup_older_than_days * 86400)

                for file_path in rotated_files:
                    if file_path.stat().st_mtime < cutoff_time:
                        logger.debug(f"Deleting log older than {self.config.cleanup_older_than_days} days: {file_path}")
                        file_path.unlink()

        except Exception as e:
            logger.error(f"Error during log cleanup: {e}", exc_info=True)

    def get_rotated_logs(self) -> list[Path]:
        """
        Get list of rotated log files.

        Returns:
            List of paths to rotated log files, sorted by modification time (newest first)
        """
        pattern = f"{self.log_file.stem}_*{self.log_file.suffix}*"
        return sorted(
            self.log_file.parent.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

    def get_status(self) -> dict:
        """
        Get current rotation status.

        Returns:
            Dictionary with rotation status information
        """
        if not self.log_file.exists():
            current_size = 0
        else:
            current_size = self.log_file.stat().st_size

        time_since_rotation = time.time() - self._last_rotation_time

        rotated_count = len(self.get_rotated_logs())

        return {
            'running': self._running,
            'log_file': str(self.log_file),
            'current_size_bytes': current_size,
            'max_size_bytes': self.config.max_bytes,
            'size_utilization_percent': (current_size / self.config.max_bytes * 100) if self.config.max_bytes > 0 else 0,
            'time_since_last_rotation_seconds': time_since_rotation,
            'rotation_interval_seconds': self.config.rotation_interval_hours * 3600,
            'rotated_files_count': rotated_count,
            'backup_count': self.config.backup_count,
            'strategy': self.config.strategy.value
        }


# =============================================================================
# INTEGRATION WITH STRUCTURED LOGGER
# =============================================================================

class RotatingStructuredLogHandler(logging.Handler):
    """
    Custom log handler that integrates LogRotator with Python's logging system.

    This allows automatic rotation of structured log files.

    Example:
        >>> handler = RotatingStructuredLogHandler(
        ...     log_file="/var/log/portal/app.log",
        ...     config=RotationConfig(max_bytes=10*1024*1024)
        ... )
        >>> logger.addHandler(handler)
    """

    def __init__(
        self,
        log_file: Path | str,
        config: RotationConfig | None = None
    ):
        """
        Initialize rotating log handler.

        Args:
            log_file: Path to log file
            config: Rotation configuration
        """
        super().__init__()

        self.log_file = Path(log_file)
        self.config = config or RotationConfig()
        self.rotator: LogRotator | None = None

        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Open file handler
        self._file_handler = logging.FileHandler(self.log_file)
        self.setFormatter(self._file_handler.formatter)

    def emit(self, record):
        """Emit a log record"""
        try:
            # Check if rotation is needed (synchronous check)
            if self._should_rotate_sync():
                self._rotate_sync()

            # Emit to file handler
            self._file_handler.emit(record)

        except Exception:
            self.handleError(record)

    def _should_rotate_sync(self) -> bool:
        """Synchronous rotation check"""
        if not self.log_file.exists():
            return False

        # Only check size for synchronous rotation
        if self.config.strategy in (RotationStrategy.SIZE, RotationStrategy.SIZE_AND_TIME):
            file_size = self.log_file.stat().st_size
            return file_size >= self.config.max_bytes

        return False

    def _rotate_sync(self):
        """Synchronous rotation (for use in logging handler)"""
        try:
            # Close current handler
            self._file_handler.close()

            # Generate rotated filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_name = f"{self.log_file.stem}_{timestamp}{self.log_file.suffix}"
            rotated_path = self.log_file.parent / rotated_name

            # Rename file
            if self.log_file.exists():
                self.log_file.rename(rotated_path)

            # Compress in background if needed
            if self.config.compress_rotated:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._compress_async(rotated_path))
                except RuntimeError:
                    # No running event loop — compress synchronously
                    try:
                        compressed = rotated_path.with_suffix(rotated_path.suffix + '.gz')
                        LogRotator._compress_file(rotated_path, compressed)
                        rotated_path.unlink()
                    except Exception as comp_err:
                        import sys
                        print(f"Sync compression failed: {comp_err}", file=sys.stderr)

            # Create new handler
            self._file_handler = logging.FileHandler(self.log_file)
            self.setFormatter(self._file_handler.formatter)

        except Exception as e:
            # Log to stderr if rotation fails
            import sys
            print(f"Log rotation failed: {e}", file=sys.stderr)

    async def _compress_async(self, log_path: Path):
        """Async compression helper"""
        try:
            compressed_path = log_path.with_suffix(log_path.suffix + '.gz')
            await asyncio.to_thread(LogRotator._compress_file, log_path, compressed_path)
            log_path.unlink()
        except Exception as e:
            logger.error(f"Background compression failed: {e}")

    def close(self):
        """Close the handler"""
        self._file_handler.close()
        super().close()
