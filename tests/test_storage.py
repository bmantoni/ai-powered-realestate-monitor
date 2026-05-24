"""Tests for src.storage.JsonStorage — load, save, upsert, mark_removed, snapshots."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import mock_open, patch

import pytest
from freezegun import freeze_time

from src.storage import JsonStorage


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
class TestStorageLoad:
    """JsonStorage initialisation and _load behaviour."""

    def test_load_creates_default_structure_when_file_missing(self, temp_dir: Path) -> None:
        """When the file does not exist, _load returns a fresh data structure."""
        filepath = temp_dir / "nonexistent" / "props.json"
        storage = JsonStorage(str(filepath))
        assert storage._data == {
            "version": 1,
            "last_run": None,
            "properties": {},
            "snapshots": [],
        }

    def test_load_reads_existing_file(self, populated_storage_file: Path) -> None:
        """When the file exists, _load reads its contents."""
        storage = JsonStorage(str(populated_storage_file))
        assert storage._data["version"] == 1
        assert "existing-001" in storage._data["properties"]
        assert len(storage._data["snapshots"]) == 1

    def test_load_invalid_json_raises(self, temp_dir: Path) -> None:
        """Loading a file with invalid JSON raises an exception."""
        filepath = temp_dir / "bad.json"
        filepath.write_text("not json")
        with pytest.raises(Exception):  # json.JSONDecodeError
            JsonStorage(str(filepath))


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------
class TestStorageSave:
    """JsonStorage save behaviour."""

    def test_save_creates_directories(self, temp_dir: Path) -> None:
        """save() creates parent directories if they do not exist."""
        filepath = temp_dir / "deep" / "nested" / "props.json"
        storage = JsonStorage(str(filepath))
        storage.save()
        assert filepath.exists()

    def test_save_writes_valid_json(self, temp_dir: Path) -> None:
        """save() writes valid JSON that can be reloaded."""
        filepath = temp_dir / "props.json"
        storage = JsonStorage(str(filepath))
        storage.save()
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert data["properties"] == {}

    def test_save_overwrites_existing_file(self, temp_dir: Path) -> None:
        """save() overwrites an existing file with current state."""
        filepath = temp_dir / "props.json"
        filepath.write_text('{"version": 99, "last_run": null, "properties": {}, "snapshots": []}')
        storage = JsonStorage(str(filepath))
        # Modify state then save
        storage.upsert_property("x", {"id": "x"})
        storage.save()
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["properties"]["x"]["id"] == "x"


# ---------------------------------------------------------------------------
# Property operations
# ---------------------------------------------------------------------------
class TestStoragePropertyOps:
    """CRUD-like operations for individual properties."""

    def test_get_property_returns_none_for_missing(self, temp_dir: Path) -> None:
        """get_property returns None when the ID does not exist."""
        storage = JsonStorage(str(temp_dir / "props.json"))
        assert storage.get_property("missing") is None

    def test_get_property_returns_dict(self, populated_storage_file: Path) -> None:
        """get_property returns the property dict when it exists."""
        storage = JsonStorage(str(populated_storage_file))
        prop = storage.get_property("existing-001")
        assert prop is not None
        assert prop["title"] == "Existing Property"

    def test_upsert_property_inserts_new(self, temp_dir: Path) -> None:
        """upsert_property adds a new property to storage."""
        filepath = temp_dir / "props.json"
        storage = JsonStorage(str(filepath))
        storage.upsert_property("new-001", {"id": "new-001", "price": 150_000.0})
        assert storage.get_property("new-001") == {"id": "new-001", "price": 150_000.0}

    def test_upsert_property_updates_existing(self, populated_storage_file: Path) -> None:
        """upsert_property overwrites an existing property's fields."""
        storage = JsonStorage(str(populated_storage_file))
        storage.upsert_property("existing-001", {"id": "existing-001", "price": 175_000.0})
        prop = storage.get_property("existing-001")
        assert prop["price"] == 175_000.0

    def test_upsert_property_preserves_first_seen(self, populated_storage_file: Path) -> None:
        """When updating, first_seen is preserved from the existing record."""
        storage = JsonStorage(str(populated_storage_file))
        original = storage.get_property("existing-001")
        original_first_seen = original["first_seen"]
        storage.upsert_property("existing-001", {"id": "existing-001", "price": 175_000.0})
        updated = storage.get_property("existing-001")
        assert updated["first_seen"] == original_first_seen

    def test_upsert_property_tracks_last_price_on_change(self, populated_storage_file: Path) -> None:
        """When price changes, last_price is set to the previous price."""
        storage = JsonStorage(str(populated_storage_file))
        storage.upsert_property("existing-001", {"id": "existing-001", "price": 175_000.0})
        updated = storage.get_property("existing-001")
        assert updated["last_price"] == 160_000.0

    def test_upsert_property_does_not_set_last_price_when_unchanged(self, populated_storage_file: Path) -> None:
        """When price does not change, last_price is not modified."""
        storage = JsonStorage(str(populated_storage_file))
        storage.upsert_property("existing-001", {"id": "existing-001", "price": 160_000.0})
        updated = storage.get_property("existing-001")
        # last_price key should be absent because the incoming data didn't have it
        # and existing didn't have it either
        assert "last_price" not in updated

    def test_get_all_properties_returns_empty_dict_initially(self, temp_dir: Path) -> None:
        """get_all_properties returns an empty dict for fresh storage."""
        storage = JsonStorage(str(temp_dir / "props.json"))
        assert storage.get_all_properties() == {}

    def test_get_all_properties_returns_all(self, populated_storage_file: Path) -> None:
        """get_all_properties returns every stored property keyed by ID."""
        storage = JsonStorage(str(populated_storage_file))
        all_props = storage.get_all_properties()
        assert len(all_props) == 1
        assert "existing-001" in all_props


# ---------------------------------------------------------------------------
# mark_removed
# ---------------------------------------------------------------------------
class TestStorageMarkRemoved:
    """Behaviour of mark_removed."""

    def test_mark_removed_marks_inactive(self, populated_storage_file: Path) -> None:
        """Properties not in active_ids are marked unavailable."""
        storage = JsonStorage(str(populated_storage_file))
        storage.mark_removed(["some-other-id"])
        prop = storage.get_property("existing-001")
        assert prop["is_available"] is False

    def test_mark_removed_preserves_active(self, populated_storage_file: Path) -> None:
        """Properties in active_ids remain available."""
        storage = JsonStorage(str(populated_storage_file))
        storage.mark_removed(["existing-001"])
        prop = storage.get_property("existing-001")
        assert prop["is_available"] is True

    def test_mark_removed_with_empty_list_marks_all_unavailable(self, temp_dir: Path) -> None:
        """Passing an empty active_ids list marks every property unavailable."""
        filepath = temp_dir / "props.json"
        storage = JsonStorage(str(filepath))
        storage.upsert_property("a", {"id": "a", "is_available": True})
        storage.upsert_property("b", {"id": "b", "is_available": True})
        storage.mark_removed([])
        assert storage.get_property("a")["is_available"] is False
        assert storage.get_property("b")["is_available"] is False


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------
class TestStorageSnapshots:
    """Behaviour of add_snapshot and get_latest_snapshot."""

    @freeze_time("2024-01-15T12:00:00")
    def test_add_snapshot_appends(self, temp_dir: Path) -> None:
        """add_snapshot appends the snapshot to the snapshots list."""
        filepath = temp_dir / "props.json"
        storage = JsonStorage(str(filepath))
        snapshot = {
            "date": datetime(2024, 1, 15, 10, 0, 0).isoformat(),
            "total_listings": 3,
            "average_price": 150_000.0,
            "median_price": 150_000.0,
            "new_listings": [],
            "price_changes": [],
            "removed_listings": [],
        }
        storage.add_snapshot(snapshot)
        assert len(storage._data["snapshots"]) == 1

    def test_get_latest_snapshot_returns_none_when_empty(self, temp_dir: Path) -> None:
        """get_latest_snapshot returns None if no snapshots exist."""
        storage = JsonStorage(str(temp_dir / "props.json"))
        assert storage.get_latest_snapshot() is None

    def test_get_latest_snapshot_returns_most_recent(self, populated_storage_file: Path) -> None:
        """get_latest_snapshot returns the last appended snapshot."""
        storage = JsonStorage(str(populated_storage_file))
        latest = storage.get_latest_snapshot()
        assert latest is not None
        assert latest["total_listings"] == 1

    @freeze_time("2024-01-15T12:00:00")
    def test_add_snapshot_trims_older_than_90_days(self, temp_dir: Path) -> None:
        """Snapshots older than 90 days are removed after adding a new one."""
        filepath = temp_dir / "props.json"
        storage = JsonStorage(str(filepath))
        old_snapshot = {
            "date": (datetime(2024, 1, 15, 12, 0, 0) - timedelta(days=91)).isoformat(),
            "total_listings": 1,
            "average_price": 100_000.0,
            "median_price": 100_000.0,
            "new_listings": [],
            "price_changes": [],
            "removed_listings": [],
        }
        new_snapshot = {
            "date": datetime(2024, 1, 15, 12, 0, 0).isoformat(),
            "total_listings": 2,
            "average_price": 200_000.0,
            "median_price": 200_000.0,
            "new_listings": [],
            "price_changes": [],
            "removed_listings": [],
        }
        storage.add_snapshot(old_snapshot)
        storage.add_snapshot(new_snapshot)
        assert len(storage._data["snapshots"]) == 1
        assert storage._data["snapshots"][0]["total_listings"] == 2

    @freeze_time("2024-01-15T12:00:00")
    def test_add_snapshot_keeps_snapshots_within_90_days(self, temp_dir: Path) -> None:
        """Snapshots within 90 days of cutoff are retained."""
        filepath = temp_dir / "props.json"
        storage = JsonStorage(str(filepath))
        old_but_valid = {
            "date": (datetime(2024, 1, 15, 12, 0, 0) - timedelta(days=89)).isoformat(),
            "total_listings": 1,
            "average_price": 100_000.0,
            "median_price": 100_000.0,
            "new_listings": [],
            "price_changes": [],
            "removed_listings": [],
        }
        new_snapshot = {
            "date": datetime(2024, 1, 15, 12, 0, 0).isoformat(),
            "total_listings": 2,
            "average_price": 200_000.0,
            "median_price": 200_000.0,
            "new_listings": [],
            "price_changes": [],
            "removed_listings": [],
        }
        storage.add_snapshot(old_but_valid)
        storage.add_snapshot(new_snapshot)
        assert len(storage._data["snapshots"]) == 2

    @freeze_time("2024-01-15T12:00:00")
    def test_add_snapshot_accepts_datetime_object(self, temp_dir: Path) -> None:
        """add_snapshot now accepts a snapshot with a datetime object (from model_dump)."""
        filepath = temp_dir / "props.json"
        storage = JsonStorage(str(filepath))
        snapshot = {
            "date": datetime(2024, 1, 15, 12, 0, 0),  # datetime object, not string
            "total_listings": 2,
            "average_price": 200_000.0,
            "median_price": 200_000.0,
            "new_listings": [],
            "price_changes": [],
            "removed_listings": [],
        }
        storage.add_snapshot(snapshot)
        assert len(storage._data["snapshots"]) == 1
        assert storage._data["snapshots"][0]["total_listings"] == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestStorageEdgeCases:
    """Edge-case and error-condition handling."""

    def test_upsert_property_with_none_data(self, temp_dir: Path) -> None:
        """upsert_property stores None values without crashing."""
        storage = JsonStorage(str(temp_dir / "props.json"))
        storage.upsert_property("none-prop", None)  # type: ignore[arg-type]
        # The implementation does not guard against None, so this documents current behaviour
        assert storage.get_property("none-prop") is None

    def test_load_empty_file_raises(self, temp_dir: Path) -> None:
        """Loading an empty file raises JSONDecodeError."""
        filepath = temp_dir / "empty.json"
        filepath.write_text("")
        with pytest.raises(Exception):
            JsonStorage(str(filepath))

    def test_save_after_load_preserves_structure(self, populated_storage_file: Path, temp_dir: Path) -> None:
        """Saving after loading preserves the original file structure."""
        storage = JsonStorage(str(populated_storage_file))
        storage.save()
        reloaded = json.loads(populated_storage_file.read_text(encoding="utf-8"))
        assert reloaded["version"] == 1
        assert "existing-001" in reloaded["properties"]
        assert len(reloaded["snapshots"]) == 1

    def test_concurrent_directory_creation(self, temp_dir: Path) -> None:
        """save() handles race conditions in directory creation gracefully."""
        filepath = temp_dir / "race" / "props.json"
        storage = JsonStorage(str(filepath))
        # os.makedirs with exist_ok=True should not raise even if dir exists
        os.makedirs(os.path.dirname(str(filepath)), exist_ok=True)
        storage.save()
        assert filepath.exists()
