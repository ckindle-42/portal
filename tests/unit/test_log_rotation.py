"""Tests for portal.observability.log_rotation"""

import gzip
import logging
import time
from unittest.mock import MagicMock

import pytest

from portal.observability.log_rotation import (
    LogRotator,
    RotatingStructuredLogHandler,
    RotationConfig,
    RotationStrategy,
)

# ── LogRotator ───────────────────────────────────────────────────────────


class TestLogRotator:
    def test_init_creates_directory(self, tmp_path):
        log_file = tmp_path / "sub" / "app.log"
        rotator = LogRotator(log_file=log_file)
        assert log_file.parent.exists()
        assert rotator.config.strategy == RotationStrategy.SIZE_AND_TIME

    def test_init_with_custom_config(self, tmp_path):
        cfg = RotationConfig(max_bytes=512, backup_count=2)
        rotator = LogRotator(log_file=tmp_path / "app.log", config=cfg)
        assert rotator.config.max_bytes == 512
        assert rotator.config.backup_count == 2

    def test_init_with_callback(self, tmp_path):
        cb = MagicMock()
        rotator = LogRotator(log_file=tmp_path / "app.log", on_rotate=cb)
        assert rotator.on_rotate is cb

    # ── _should_rotate ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_should_rotate_false_when_file_missing(self, tmp_path):
        rotator = LogRotator(log_file=tmp_path / "missing.log")
        assert await rotator._should_rotate() is False

    @pytest.mark.asyncio
    async def test_should_rotate_size(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("x" * 200)
        cfg = RotationConfig(strategy=RotationStrategy.SIZE, max_bytes=100)
        rotator = LogRotator(log_file=log_file, config=cfg)
        assert await rotator._should_rotate() is True

    @pytest.mark.asyncio
    async def test_should_not_rotate_size_under_limit(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("x" * 10)
        cfg = RotationConfig(strategy=RotationStrategy.SIZE, max_bytes=1000)
        rotator = LogRotator(log_file=log_file, config=cfg)
        assert await rotator._should_rotate() is False

    @pytest.mark.asyncio
    async def test_should_rotate_time(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("data")
        cfg = RotationConfig(strategy=RotationStrategy.TIME, rotation_interval_hours=0)
        rotator = LogRotator(log_file=log_file, config=cfg)
        # Force past rotation time
        rotator._last_rotation_time = time.time() - 100
        assert await rotator._should_rotate() is True

    @pytest.mark.asyncio
    async def test_should_not_rotate_time_recent(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("data")
        cfg = RotationConfig(strategy=RotationStrategy.TIME, rotation_interval_hours=24)
        rotator = LogRotator(log_file=log_file, config=cfg)
        assert await rotator._should_rotate() is False

    # ── rotate ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_rotate_renames_and_creates_new(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("original content")
        cfg = RotationConfig(compress_rotated=False)
        rotator = LogRotator(log_file=log_file, config=cfg)
        await rotator.rotate()
        # New empty file should exist
        assert log_file.exists()
        assert log_file.read_text() == ""
        # Rotated file should exist
        rotated = list(tmp_path.glob("app_*.log"))
        assert len(rotated) == 1
        assert rotated[0].read_text() == "original content"

    @pytest.mark.asyncio
    async def test_rotate_skip_when_file_missing(self, tmp_path):
        rotator = LogRotator(log_file=tmp_path / "nope.log")
        # Should not raise
        await rotator.rotate()

    @pytest.mark.asyncio
    async def test_rotate_with_compression(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("compress me")
        cfg = RotationConfig(compress_rotated=True)
        rotator = LogRotator(log_file=log_file, config=cfg)
        await rotator.rotate()
        gz_files = list(tmp_path.glob("*.gz"))
        assert len(gz_files) == 1
        with gzip.open(gz_files[0], 'rb') as f:
            assert f.read() == b"compress me"

    @pytest.mark.asyncio
    async def test_rotate_triggers_callback(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("data")
        cb = MagicMock()
        cfg = RotationConfig(compress_rotated=False)
        rotator = LogRotator(log_file=log_file, config=cfg, on_rotate=cb)
        await rotator.rotate()
        cb.assert_called_once()
        args = cb.call_args[0]
        assert str(log_file) == args[0]

    @pytest.mark.asyncio
    async def test_rotate_callback_error_does_not_propagate(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("data")
        cb = MagicMock(side_effect=ValueError("oops"))
        cfg = RotationConfig(compress_rotated=False)
        rotator = LogRotator(log_file=log_file, config=cfg, on_rotate=cb)
        await rotator.rotate()  # Should not raise

    # ── _compress_file (static) ──────────────────────────────────────

    def test_compress_file_static(self, tmp_path):
        src = tmp_path / "src.log"
        dst = tmp_path / "src.log.gz"
        src.write_text("hello world")
        LogRotator._compress_file(src, dst)
        assert dst.exists()
        with gzip.open(dst, 'rb') as f:
            assert f.read() == b"hello world"

    # ── _cleanup_old_logs ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_cleanup_old_logs_removes_excess(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("current")
        cfg = RotationConfig(backup_count=2, compress_rotated=False, cleanup_older_than_days=0)
        rotator = LogRotator(log_file=log_file, config=cfg)
        # Create 4 rotated files
        for i in range(4):
            f = tmp_path / f"app_2024010{i}_000000.log"
            f.write_text(f"old {i}")
            # Stagger mtime
            import os
            os.utime(f, (time.time() - (4 - i) * 60, time.time() - (4 - i) * 60))

        await rotator._cleanup_old_logs()
        remaining = list(tmp_path.glob("app_*.log"))
        assert len(remaining) <= 2

    # ── get_rotated_logs ─────────────────────────────────────────────

    def test_get_rotated_logs_empty(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.touch()
        rotator = LogRotator(log_file=log_file)
        assert rotator.get_rotated_logs() == []

    def test_get_rotated_logs_returns_sorted(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.touch()
        for ts in ["20240101_000000", "20240102_000000"]:
            (tmp_path / f"app_{ts}.log").touch()
        rotator = LogRotator(log_file=log_file)
        logs = rotator.get_rotated_logs()
        assert len(logs) == 2

    # ── get_status ───────────────────────────────────────────────────

    def test_get_status_file_exists(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("some data")
        rotator = LogRotator(log_file=log_file)
        status = rotator.get_status()
        assert status['running'] is False
        assert status['current_size_bytes'] > 0
        assert 'size_utilization_percent' in status
        assert status['strategy'] == 'both'

    def test_get_status_file_missing(self, tmp_path):
        log_file = tmp_path / "missing.log"
        rotator = LogRotator(log_file=log_file)
        status = rotator.get_status()
        assert status['current_size_bytes'] == 0

    # ── start / stop ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_start_stop(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.touch()
        rotator = LogRotator(log_file=log_file)
        await rotator.start()
        assert rotator._running is True
        await rotator.stop()
        assert rotator._running is False

    @pytest.mark.asyncio
    async def test_start_twice_noop(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.touch()
        rotator = LogRotator(log_file=log_file)
        await rotator.start()
        await rotator.start()  # Should not raise
        await rotator.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.touch()
        rotator = LogRotator(log_file=log_file)
        await rotator.stop()  # Should not raise


# ── RotatingStructuredLogHandler ─────────────────────────────────────────


class TestRotatingStructuredLogHandler:
    def test_init(self, tmp_path):
        log_file = tmp_path / "handler.log"
        handler = RotatingStructuredLogHandler(log_file=log_file)
        assert handler.log_file == log_file
        handler.close()

    def test_emit_writes_record(self, tmp_path):
        log_file = tmp_path / "handler.log"
        handler = RotatingStructuredLogHandler(log_file=log_file)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._file_handler.setFormatter(logging.Formatter("%(message)s"))
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None
        )
        handler.emit(record)
        handler.close()
        assert "test message" in log_file.read_text()

    def test_should_rotate_sync_false_when_under_limit(self, tmp_path):
        log_file = tmp_path / "handler.log"
        log_file.write_text("small")
        handler = RotatingStructuredLogHandler(
            log_file=log_file,
            config=RotationConfig(max_bytes=10000),
        )
        assert handler._should_rotate_sync() is False
        handler.close()

    def test_should_rotate_sync_true_when_over_limit(self, tmp_path):
        log_file = tmp_path / "handler.log"
        log_file.write_text("x" * 200)
        handler = RotatingStructuredLogHandler(
            log_file=log_file,
            config=RotationConfig(strategy=RotationStrategy.SIZE, max_bytes=100),
        )
        assert handler._should_rotate_sync() is True
        handler.close()

    def test_should_rotate_sync_false_file_missing(self, tmp_path):
        log_file = tmp_path / "gone.log"
        handler = RotatingStructuredLogHandler(log_file=log_file)
        log_file.unlink(missing_ok=True)
        assert handler._should_rotate_sync() is False
        handler.close()

    def test_rotate_sync(self, tmp_path):
        log_file = tmp_path / "handler.log"
        log_file.write_text("original")
        cfg = RotationConfig(compress_rotated=False)
        handler = RotatingStructuredLogHandler(log_file=log_file, config=cfg)
        handler._rotate_sync()
        # A new handler should be created
        assert handler._file_handler is not None
        handler.close()

    def test_rotate_sync_with_compression(self, tmp_path):
        log_file = tmp_path / "handler.log"
        log_file.write_text("compress this")
        cfg = RotationConfig(compress_rotated=True)
        handler = RotatingStructuredLogHandler(log_file=log_file, config=cfg)
        handler._rotate_sync()
        handler.close()
        gz_files = list(tmp_path.glob("*.gz"))
        assert len(gz_files) >= 1

    def test_close(self, tmp_path):
        log_file = tmp_path / "handler.log"
        handler = RotatingStructuredLogHandler(log_file=log_file)
        handler.close()  # Should not raise
