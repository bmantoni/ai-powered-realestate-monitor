"""JSON file persistence for property state and snapshots."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger


class JsonStorage:
    """Single-file JSON persistence for property listings and daily snapshots."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        """Load existing data or return a fresh structure."""
        if not os.path.exists(self.filepath):
            return {"version": 1, "last_run": None, "properties": {}, "snapshots": []}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            logger.error(
                "Corrupted JSON file {} — backing up and starting fresh: {}",
                self.filepath,
                exc,
            )
            # Backup the corrupted file
            backup_path = f"{self.filepath}.corrupted.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            os.rename(self.filepath, backup_path)
            logger.info("Corrupted file backed up to {}", backup_path)
            return {"version": 1, "last_run": None, "properties": {}, "snapshots": []}

    def save(self) -> None:
        """Persist current state to disk atomically (temp file + rename)."""
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        dir_name = os.path.dirname(self.filepath) or "."
        fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, default=str)
            os.replace(temp_path, self.filepath)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def get_property(self, property_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a single property by ID."""
        return self._data["properties"].get(property_id)

    def upsert_property(self, property_id: str, data: dict[str, Any]) -> None:
        """Insert or update a property, preserving first_seen and tracking last_price."""
        existing: Optional[dict[str, Any]] = self._data["properties"].get(property_id)
        if existing:
            # Track price changes
            if existing.get("price") != data.get("price"):
                data["last_price"] = existing["price"]
            data["first_seen"] = existing["first_seen"]
        self._data["properties"][property_id] = data

    def mark_removed(self, active_ids: List[str]) -> None:
        """Mark properties not in active_ids as unavailable."""
        for pid, prop in self._data["properties"].items():
            if pid not in active_ids:
                prop["is_available"] = False

    def add_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Append a daily snapshot and trim entries older than 90 days."""
        self._data["snapshots"].append(snapshot)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        def _parse_date(d: Any) -> datetime:
            if isinstance(d, datetime):
                # If naive, assume UTC for comparison with timezone-aware cutoff
                if d.tzinfo is None:
                    return d.replace(tzinfo=timezone.utc)
                return d
            parsed = datetime.fromisoformat(d)
            # If naive, assume UTC for comparison with timezone-aware cutoff
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed

        self._data["snapshots"] = [
            s
            for s in self._data["snapshots"]
            if _parse_date(s["date"]) > cutoff
        ]

    def set_last_run(self, timestamp: str) -> None:
        """Update the last_run timestamp."""
        self._data["last_run"] = timestamp

    def get_all_properties(self) -> Dict[str, dict[str, Any]]:
        """Return all stored properties keyed by ID."""
        return self._data["properties"]

    def get_latest_snapshot(self) -> Optional[dict[str, Any]]:
        """Return the most recent snapshot, if any."""
        if not self._data["snapshots"]:
            return None
        return self._data["snapshots"][-1]
