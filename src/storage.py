"""JSON file persistence for property state and snapshots."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class JsonStorage:
    """Single-file JSON persistence for property listings and daily snapshots."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        """Load existing data or return a fresh structure."""
        if not os.path.exists(self.filepath):
            return {"version": 1, "last_run": None, "properties": {}, "snapshots": []}
        with open(self.filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self) -> None:
        """Persist current state to disk."""
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str)

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
        cutoff = datetime.utcnow() - timedelta(days=90)

        def _parse_date(d: Any) -> datetime:
            if isinstance(d, datetime):
                return d
            return datetime.fromisoformat(d)

        self._data["snapshots"] = [
            s
            for s in self._data["snapshots"]
            if _parse_date(s["date"]) > cutoff
        ]

    def get_all_properties(self) -> Dict[str, dict[str, Any]]:
        """Return all stored properties keyed by ID."""
        return self._data["properties"]

    def get_latest_snapshot(self) -> Optional[dict[str, Any]]:
        """Return the most recent snapshot, if any."""
        if not self._data["snapshots"]:
            return None
        return self._data["snapshots"][-1]
