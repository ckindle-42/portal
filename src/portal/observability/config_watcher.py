"""
Config Hot-Reloading
====================

Watches configuration files for changes and reloads without restart.

Features:
- File system watching
- Automatic reload on change
- Callback system for config updates
- Validation before applying changes
- Rollback on invalid config

Example:
--------
watcher = ConfigWatcher(config_file="config.yaml")

# Register callback for config changes
def on_config_change(new_config):
    print(f"Config changed: {new_config}")

watcher.add_callback(on_config_change)

# Start watching
await watcher.start()
"""

import asyncio
import logging
from typing import Dict, Any, Callable, List, Optional
from pathlib import Path
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """
    Configuration file watcher with hot-reloading.

    Monitors a config file for changes and triggers callbacks
    when the file is modified.
    """

    def __init__(
        self,
        config_file: Path,
        check_interval: float = 5.0,
        validator: Optional[Callable[[Dict[str, Any]], bool]] = None
    ):
        """
        Initialize config watcher.

        Args:
            config_file: Path to config file to watch
            check_interval: How often to check for changes (seconds)
            validator: Optional function to validate config before applying
        """
        self.config_file = Path(config_file)
        self.check_interval = check_interval
        self.validator = validator

        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_hash: Optional[str] = None
        self._current_config: Optional[Dict[str, Any]] = None

        logger.info(f"ConfigWatcher initialized for: {config_file}")

    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Add a callback to be called when config changes.

        Args:
            callback: Function to call with new config
        """
        self._callbacks.append(callback)
        logger.info(f"Added config change callback: {callback.__name__}")

    async def start(self):
        """Start watching the config file"""
        if self._running:
            logger.warning("ConfigWatcher already running")
            return

        self._running = True

        # Load initial config
        await self._load_config()

        # Start watch loop
        self._task = asyncio.create_task(self._watch_loop())

        logger.info(f"ConfigWatcher started, checking every {self.check_interval}s")

    async def stop(self):
        """Stop watching the config file"""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("ConfigWatcher stopped")

    async def _watch_loop(self):
        """Main watch loop"""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)

                if not self._running:
                    break

                # Check for changes
                await self._check_for_changes()

            except asyncio.CancelledError:
                break

            except Exception as e:
                logger.exception(f"Error in config watch loop: {e}")

    async def _check_for_changes(self):
        """Check if config file has changed"""
        if not self.config_file.exists():
            logger.warning(f"Config file not found: {self.config_file}")
            return

        # Calculate file hash
        file_hash = self._calculate_hash(self.config_file)

        # Compare with last known hash
        if file_hash != self._last_hash:
            logger.info(f"Config file changed: {self.config_file}")
            await self._reload_config()
            self._last_hash = file_hash

    async def _load_config(self):
        """Load config for the first time"""
        if not self.config_file.exists():
            logger.error(f"Config file not found: {self.config_file}")
            return

        try:
            config = self._read_config_file(self.config_file)
            self._current_config = config
            self._last_hash = self._calculate_hash(self.config_file)

            logger.info(f"Config loaded: {self.config_file}")

        except Exception as e:
            logger.exception(f"Failed to load config: {e}")

    async def _reload_config(self):
        """Reload config when file changes"""
        try:
            # Read new config
            new_config = self._read_config_file(self.config_file)

            # Validate if validator provided
            if self.validator:
                if not self.validator(new_config):
                    logger.error("Config validation failed, keeping old config")
                    return

            # Store old config for potential rollback
            old_config = self._current_config
            self._current_config = new_config

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    # Handle both sync and async callbacks
                    result = callback(new_config)
                    if asyncio.iscoroutine(result):
                        await result

                except Exception as e:
                    logger.exception(f"Config callback failed: {e}")

                    # Rollback on callback failure
                    self._current_config = old_config
                    logger.warning("Rolled back to previous config due to callback failure")
                    return

            logger.info(f"Config reloaded successfully: {self.config_file}")

        except Exception as e:
            logger.exception(f"Failed to reload config: {e}")

    def _read_config_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Read config file.

        Supports YAML, JSON, and TOML formats.

        Args:
            file_path: Path to config file

        Returns:
            Dict with config data
        """
        content = file_path.read_text()

        # Determine format from extension
        suffix = file_path.suffix.lower()

        if suffix in ['.yaml', '.yml']:
            import yaml
            return yaml.safe_load(content)

        elif suffix == '.json':
            import json
            return json.loads(content)

        elif suffix == '.toml':
            import toml
            return toml.loads(content)

        else:
            raise ValueError(f"Unsupported config format: {suffix}")

    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate hash of file contents"""
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def get_current_config(self) -> Optional[Dict[str, Any]]:
        """Get current configuration"""
        return self._current_config


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def watch_config(
    config_file: Path,
    on_change: Callable[[Dict[str, Any]], None],
    validator: Optional[Callable[[Dict[str, Any]], bool]] = None,
    check_interval: float = 5.0
) -> ConfigWatcher:
    """
    Convenience function to start watching a config file.

    Args:
        config_file: Path to config file
        on_change: Callback for config changes
        validator: Optional config validator
        check_interval: Check interval in seconds

    Returns:
        ConfigWatcher instance (already started)
    """
    watcher = ConfigWatcher(
        config_file=config_file,
        check_interval=check_interval,
        validator=validator
    )

    watcher.add_callback(on_change)
    await watcher.start()

    return watcher
