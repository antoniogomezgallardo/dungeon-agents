"""Tests for game-state persistence (Milestone 2).

Deterministic, no API key, no SDK. Uses pytest's `tmp_path` fixture as the
data directory so tests are isolated and never touch the real `data/` folder —
the same `data_dir` injection that keeps saves reproducible under test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dungeon_agents.domain.state import (
    STATE_FILENAME,
    StateError,
    load_game_state,
    save_game_state,
)


def test_save_then_load_roundtrips(tmp_path: Path) -> None:
    """State written by save is read back unchanged (semantically) by load."""
    original = '{"hp": 10, "gold": 5, "location": "tavern"}'
    save_game_state(original, data_dir=tmp_path)

    loaded = load_game_state(data_dir=tmp_path)
    # Compare parsed content, not raw text (save normalizes formatting).
    assert json.loads(loaded) == json.loads(original)


def test_load_with_no_save_returns_empty_object(tmp_path: Path) -> None:
    """A fresh game (no save file yet) loads as an empty JSON object."""
    assert load_game_state(data_dir=tmp_path) == "{}"


def test_save_creates_the_file_in_the_data_dir(tmp_path: Path) -> None:
    """Saving writes the state file inside the given data directory."""
    save_game_state('{"ok": true}', data_dir=tmp_path)
    assert (tmp_path / STATE_FILENAME).exists()


def test_save_rejects_invalid_json(tmp_path: Path) -> None:
    """Non-JSON input is refused and nothing is written to disk."""
    with pytest.raises(StateError):
        save_game_state("not valid json {{{", data_dir=tmp_path)
    # The file must not have been created by the failed save.
    assert not (tmp_path / STATE_FILENAME).exists()


def test_load_rejects_corrupt_save(tmp_path: Path) -> None:
    """A corrupt save file fails loudly instead of returning garbage."""
    (tmp_path / STATE_FILENAME).write_text("{ broken json", encoding="utf-8")
    with pytest.raises(StateError):
        load_game_state(data_dir=tmp_path)


def test_save_normalizes_formatting(tmp_path: Path) -> None:
    """Saved JSON is normalized (sorted keys, indented) for stable diffs."""
    save_game_state('{"b": 2, "a": 1}', data_dir=tmp_path)
    on_disk = (tmp_path / STATE_FILENAME).read_text(encoding="utf-8")
    # sort_keys=True means "a" is written before "b".
    assert on_disk.index('"a"') < on_disk.index('"b"')
