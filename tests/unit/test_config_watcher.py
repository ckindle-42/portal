"""Tests for portal.observability.config_watcher."""

import asyncio

import pytest

from portal.observability.config_watcher import ConfigWatcher


@pytest.fixture
def config_file(tmp_path):
    """Create a temporary config file."""
    config = tmp_path / "config.yaml"
    config.write_text("key: value\n")
    return config


class TestConfigWatcher:
    """Test ConfigWatcher functionality."""

    def test_watcher_initialization(self, config_file):
        """ConfigWatcher initializes correctly."""
        watcher = ConfigWatcher(config_file=config_file)
        assert watcher.config_file == config_file
        assert watcher.check_interval == 5.0
        assert watcher._running is False

    def test_watcher_with_custom_interval(self, config_file):
        """ConfigWatcher accepts custom check interval."""
        watcher = ConfigWatcher(config_file=config_file, check_interval=10.0)
        assert watcher.check_interval == 10.0

    def test_add_callback(self, config_file):
        """Callbacks can be added to the watcher."""
        watcher = ConfigWatcher(config_file=config_file)

        def my_callback(config):
            pass

        watcher.add_callback(my_callback)
        assert len(watcher._callbacks) == 1
        assert watcher._callbacks[0] == my_callback


class TestConfigWatcherAsync:
    """Test async behavior of ConfigWatcher."""

    @pytest.mark.asyncio
    async def test_config_watcher_detects_change(self, tmp_path):
        """Config file changes are detected and callbacks are invoked."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value1\n")

        callback_invoked = []

        def on_change(config):
            callback_invoked.append(config)

        watcher = ConfigWatcher(config_file=config_file, check_interval=0.5)
        watcher.add_callback(on_change)

        # Start the watcher
        await watcher.start()

        # Wait a bit to ensure watcher is running
        await asyncio.sleep(0.2)

        # Modify the config file
        config_file.write_text("key: value2\n")

        # Wait for the watcher to detect the change
        await asyncio.sleep(1.0)

        # Stop the watcher
        await watcher.stop()

        # Callback should have been invoked with the new config
        assert len(callback_invoked) >= 1

    @pytest.mark.asyncio
    async def test_config_watcher_handles_missing_file(self, tmp_path):
        """Watcher handles missing config file gracefully."""
        config_file = tmp_path / "nonexistent.yaml"

        watcher = ConfigWatcher(config_file=config_file, check_interval=0.5)

        # Starting the watcher with a missing file should not raise
        await watcher.start()

        # Wait a bit
        await asyncio.sleep(0.5)

        # Stop should also not raise
        await watcher.stop()

    @pytest.mark.asyncio
    async def test_watcher_stop(self, config_file):
        """Watcher can be stopped."""
        watcher = ConfigWatcher(config_file=config_file, check_interval=0.5)

        await watcher.start()
        assert watcher._running is True
        assert watcher._task is not None

        await watcher.stop()
        assert watcher._running is False
