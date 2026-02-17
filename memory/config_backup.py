"""
MRAgent — Config Backup & Rollback
Save/restore config snapshots (2-3 steps back).

Created: 2026-02-15

Note: This extends the basic backup functions in config/settings.py
with history browsing and diff capabilities.
"""

import json
from datetime import datetime
from pathlib import Path

from config.settings import CONFIG_BACKUP_DIR, DEFAULTS, save_config_backup, load_config_backup
from utils.logger import get_logger

logger = get_logger("memory.config_backup")


class ConfigBackupManager:
    """
    Manages configuration snapshots for rollback capability.
    Keeps the last 3 snapshots and provides comparison tools.
    """

    def __init__(self):
        self.logger = get_logger("memory.config_backup")

    def snapshot(self) -> Path:
        """Take a snapshot of current config."""
        path = save_config_backup()
        self.logger.info(f"Config snapshot saved: {path}")
        return path

    def rollback(self, steps: int = 1) -> dict | None:
        """
        Rollback to a previous config.

        Args:
            steps: How many steps back (1 = most recent, 2 = before that)

        Returns:
            The restored config dict, or None if no backup exists
        """
        config = load_config_backup(steps)
        if config is None:
            self.logger.warning(f"No backup found {steps} step(s) back")
            return None

        # Apply the config
        restored_defaults = config.get("defaults", {})
        for key, value in restored_defaults.items():
            if key in DEFAULTS:
                DEFAULTS[key] = value

        self.logger.info(f"Rolled back config {steps} step(s)")
        return config

    def list_backups(self) -> list[dict]:
        """List all available config backups."""
        backups = sorted(CONFIG_BACKUP_DIR.glob("config_*.json"), reverse=True)
        result = []
        for i, path in enumerate(backups, 1):
            try:
                data = json.loads(path.read_text())
                result.append({
                    "step": i,
                    "file": path.name,
                    "timestamp": data.get("timestamp", "unknown"),
                    "models": data.get("available_models", []),
                })
            except Exception:
                result.append({"step": i, "file": path.name, "error": "corrupted"})
        return result

    def diff(self, steps: int = 1) -> dict:
        """
        Compare current config with a backup.

        Returns:
            Dict of changed keys with old/new values
        """
        old = load_config_backup(steps)
        if not old:
            return {"error": "No backup found"}

        old_defaults = old.get("defaults", {})
        changes = {}
        for key, current_val in DEFAULTS.items():
            old_val = old_defaults.get(key)
            if old_val != current_val:
                changes[key] = {"old": old_val, "new": current_val}

        return changes
