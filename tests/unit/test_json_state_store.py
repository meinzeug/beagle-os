"""Unit tests for core.persistence.json_state_store.JsonStateStore."""
from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path

import pytest

from core.persistence.json_state_store import JsonStateStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_store(tmp_path: Path, filename: str = "state.json", mode: int = 0o600) -> JsonStateStore:
    return JsonStateStore(
        tmp_path / filename,
        default_factory=lambda: {"items": []},
        mode=mode,
    )


# ---------------------------------------------------------------------------
# Basic round-trip
# ---------------------------------------------------------------------------

def test_save_and_load_round_trip(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    data = {"items": [1, 2, 3], "name": "hello"}
    store.save(data)
    loaded = store.load()
    assert loaded == data


def test_load_default_when_file_missing(tmp_path: Path) -> None:
    store = make_store(tmp_path, "nonexistent.json")
    result = store.load()
    assert result == {"items": []}


def test_load_raises_on_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not valid json!!!", encoding="utf-8")
    store = JsonStateStore(path, default_factory=lambda: {})
    with pytest.raises(json.JSONDecodeError):
        store.load()


def test_exists_true_after_save(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert not store.exists()
    store.save({"items": []})
    assert store.exists()


# ---------------------------------------------------------------------------
# Atomic write: temp file is cleaned up
# ---------------------------------------------------------------------------

def test_atomic_write_no_stale_tmp_files(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save({"items": ["x"]})
    tmp_files = list(tmp_path.glob(".tmp-*"))
    assert tmp_files == [], f"Stale temp files found: {tmp_files}"


def test_original_unchanged_if_write_would_produce_bad_json(tmp_path: Path) -> None:
    """Even if an error occurs, the original file must survive (tested via non-serialisable obj)."""
    store = make_store(tmp_path)
    store.save({"items": ["original"]})

    class _NotSerializable:
        pass

    with pytest.raises(TypeError):
        store.save({"items": [_NotSerializable()]})

    # Original must still be intact
    loaded = store.load()
    assert loaded == {"items": ["original"]}


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def test_permissions_600_applied(tmp_path: Path) -> None:
    store = make_store(tmp_path, mode=0o600)
    store.save({"items": []})
    file_mode = stat.S_IMODE(os.stat(tmp_path / "state.json").st_mode)
    assert file_mode == 0o600


def test_permissions_644_applied(tmp_path: Path) -> None:
    store = make_store(tmp_path, filename="pub.json", mode=0o644)
    store.save({"items": []})
    file_mode = stat.S_IMODE(os.stat(tmp_path / "pub.json").st_mode)
    assert file_mode == 0o644


# ---------------------------------------------------------------------------
# update() — read-modify-write under lock
# ---------------------------------------------------------------------------

def test_update_modifies_in_place(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save({"counter": 0, "items": []})
    store.update(lambda d: d.update({"counter": d["counter"] + 1}))
    assert store.load()["counter"] == 1


def test_update_creates_file_if_missing(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.update(lambda d: d["items"].append("first"))
    assert store.load()["items"] == ["first"]


# ---------------------------------------------------------------------------
# Concurrent writes — 20 threads each append one item
# ---------------------------------------------------------------------------

def test_concurrent_updates_no_data_loss(tmp_path: Path) -> None:
    store = JsonStateStore(
        tmp_path / "concurrent.json",
        default_factory=lambda: {"values": []},
        mode=0o600,
    )
    store.save({"values": []})

    errors: list[Exception] = []

    def worker(n: int) -> None:
        try:
            store.update(lambda d: d["values"].append(n))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Worker errors: {errors}"
    final = store.load()
    assert len(final["values"]) == 20, f"Expected 20 values, got {len(final['values'])}"
    assert sorted(final["values"]) == list(range(20))


# ---------------------------------------------------------------------------
# Parent directory created automatically
# ---------------------------------------------------------------------------

def test_parent_dir_created_on_save(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c" / "state.json"
    store = JsonStateStore(nested, default_factory=lambda: {})
    store.save({"ok": True})
    assert nested.exists()
    assert store.load() == {"ok": True}
