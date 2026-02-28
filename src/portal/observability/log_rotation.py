"""Log rotation — size/time-based rotation with gzip compression and cleanup."""

import asyncio
import gzip
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class RotationStrategy(Enum):
    SIZE = "size"
    TIME = "time"
    SIZE_AND_TIME = "both"


@dataclass
class RotationConfig:
    strategy: RotationStrategy = RotationStrategy.SIZE_AND_TIME
    max_bytes: int = 10 * 1024 * 1024  # 10 MB
    rotation_interval_hours: int = 24
    backup_count: int = 7
    compress_rotated: bool = True
    cleanup_enabled: bool = True
    cleanup_older_than_days: int = 30


class LogRotator:
    """Manages log file rotation (size/time), gzip compression, and cleanup."""

    def __init__(
        self,
        log_file: Path | str,
        config: RotationConfig | None = None,
        on_rotate: Callable[[str, str], None] | None = None,
    ):
        self.log_file = Path(log_file)
        self.config = config or RotationConfig()
        self.on_rotate = on_rotate
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_rotation_time = time.time()
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            "LogRotator initialized",
            log_file=str(self.log_file),
            strategy=self.config.strategy.value,
            max_bytes=self.config.max_bytes,
            rotation_hours=self.config.rotation_interval_hours,
        )

    async def start(self) -> None:
        if self._running:
            logger.warning("LogRotator already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._rotation_loop())
        logger.info("LogRotator started")

    async def stop(self) -> None:
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

    async def _rotation_loop(self) -> None:
        try:
            while self._running:
                await asyncio.sleep(60)
                if await self._should_rotate():
                    await self.rotate()
                if self.config.cleanup_enabled:
                    await self._cleanup_old_logs()
        except asyncio.CancelledError:
            logger.info("Rotation loop cancelled")
            raise
        except Exception as e:
            logger.error("Error in rotation loop: %s", e, exc_info=True)

    async def _should_rotate(self) -> bool:
        if not self.log_file.exists():
            return False
        if self.config.strategy in (RotationStrategy.SIZE, RotationStrategy.SIZE_AND_TIME):
            if self.log_file.stat().st_size >= self.config.max_bytes:
                return True
        if self.config.strategy in (RotationStrategy.TIME, RotationStrategy.SIZE_AND_TIME):
            if time.time() - self._last_rotation_time >= self.config.rotation_interval_hours * 3600:
                return True
        return False

    async def rotate(self) -> None:
        if not self.log_file.exists():
            logger.warning("Log file %s does not exist, skipping rotation", self.log_file)
            return
        try:
            timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
            rotated_path = (
                self.log_file.parent / f"{self.log_file.stem}_{timestamp}{self.log_file.suffix}"
            )
            logger.info("Rotating log file: %s -> %s", self.log_file, rotated_path)
            self.log_file.rename(rotated_path)
            self.log_file.touch()
            if self.config.compress_rotated:
                await self._compress_log(rotated_path)
            self._last_rotation_time = time.time()
            if self.on_rotate:
                try:
                    self.on_rotate(str(self.log_file), str(rotated_path))
                except Exception as e:
                    logger.error("Error in rotation callback: %s", e)
            logger.info("Log rotation completed successfully")
        except Exception as e:
            logger.error("Failed to rotate log file: %s", e, exc_info=True)

    async def _compress_log(self, log_path: Path) -> None:
        try:
            compressed_path = log_path.with_suffix(log_path.suffix + ".gz")
            await asyncio.to_thread(self._compress_file, log_path, compressed_path)
            log_path.unlink()
        except Exception as e:
            logger.error("Failed to compress log file %s: %s", log_path, e)

    @staticmethod
    def _compress_file(src: Path, dst: Path) -> None:
        with open(src, "rb") as f_in, gzip.open(dst, "wb") as f_out:
            f_out.writelines(f_in)

    async def _cleanup_old_logs(self) -> None:
        try:
            pattern = f"{self.log_file.stem}_*{self.log_file.suffix}*"
            rotated_files = sorted(
                self.log_file.parent.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
            )
            for fp in rotated_files[self.config.backup_count :]:
                logger.debug("Deleting old rotated log: %s", fp)
                fp.unlink()
            if self.config.cleanup_older_than_days > 0:
                cutoff = time.time() - self.config.cleanup_older_than_days * 86400
                for fp in rotated_files:
                    if fp.stat().st_mtime < cutoff:
                        logger.debug(
                            "Deleting log older than %s days: %s",
                            self.config.cleanup_older_than_days,
                            fp,
                        )
                        fp.unlink()
        except Exception as e:
            logger.error("Error during log cleanup: %s", e, exc_info=True)

    def get_rotated_logs(self) -> list[Path]:
        pattern = f"{self.log_file.stem}_*{self.log_file.suffix}*"
        return sorted(
            self.log_file.parent.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
        )

    def get_status(self) -> dict:
        current_size = self.log_file.stat().st_size if self.log_file.exists() else 0
        return {
            "running": self._running,
            "log_file": str(self.log_file),
            "current_size_bytes": current_size,
            "max_size_bytes": self.config.max_bytes,
            "size_utilization_percent": (
                current_size / self.config.max_bytes * 100 if self.config.max_bytes > 0 else 0
            ),
            "time_since_last_rotation_seconds": time.time() - self._last_rotation_time,
            "rotation_interval_seconds": self.config.rotation_interval_hours * 3600,
            "rotated_files_count": len(self.get_rotated_logs()),
            "backup_count": self.config.backup_count,
            "strategy": self.config.strategy.value,
        }


class RotatingStructuredLogHandler(logging.Handler):
    """Log handler that integrates LogRotator with Python's logging system."""

    def __init__(self, log_file: Path | str, config: RotationConfig | None = None):
        super().__init__()
        self.log_file = Path(log_file)
        self.config = config or RotationConfig()
        self.rotator: LogRotator | None = None
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._file_handler = logging.FileHandler(self.log_file)
        self.setFormatter(self._file_handler.formatter)

    def emit(self, record) -> None:
        try:
            if self._should_rotate_sync():
                self._rotate_sync()
            self._file_handler.emit(record)
        except Exception:
            self.handleError(record)

    def _should_rotate_sync(self) -> bool:
        if not self.log_file.exists():
            return False
        if self.config.strategy in (RotationStrategy.SIZE, RotationStrategy.SIZE_AND_TIME):
            return self.log_file.stat().st_size >= self.config.max_bytes
        return False

    def _rotate_sync(self) -> None:
        try:
            self._file_handler.close()
            timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
            rotated_path = (
                self.log_file.parent / f"{self.log_file.stem}_{timestamp}{self.log_file.suffix}"
            )
            if self.log_file.exists():
                self.log_file.rename(rotated_path)
            if self.config.compress_rotated:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._compress_async(rotated_path))
                except RuntimeError:
                    try:
                        compressed = rotated_path.with_suffix(rotated_path.suffix + ".gz")
                        LogRotator._compress_file(rotated_path, compressed)
                        rotated_path.unlink()
                    except Exception as comp_err:
                        print(f"Sync compression failed: {comp_err}", file=sys.stderr)
            self._file_handler = logging.FileHandler(self.log_file)
            self.setFormatter(self._file_handler.formatter)
        except Exception as e:
            print(f"Log rotation failed: {e}", file=sys.stderr)

    async def _compress_async(self, log_path: Path) -> None:
        try:
            compressed_path = log_path.with_suffix(log_path.suffix + ".gz")
            await asyncio.to_thread(LogRotator._compress_file, log_path, compressed_path)
            log_path.unlink()
        except Exception as e:
            logger.error("Background compression failed: %s", e)

    def close(self) -> None:
        self._file_handler.close()
        super().close()
