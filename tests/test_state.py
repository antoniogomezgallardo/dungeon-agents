"""Tests for game-state persistence.

Deterministic, no API key, no SDK. Uses pytest's `tmp_path` fixture as the data
directory so tests are isolated and never touch the real `data/` folder.

Persistence uses a single validated format (M5 unified the two earlier systems).
These tests cover: validated save/load round-trips, the tolerant loader that
discards missing/incompatible saves, and clearing a save for a new game.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dungeon_agents.domain.models import GameState, Player
from dungeon_agents.domain.state import (
    STATE_FILENAME,
    StateError,
    clear_state,
    load_state,
    load_state_or_none,
    save_state,
)


def test_save_state_then_load_state_roundtrips(tmp_path: Path) -> None:
    """A validated GameState saved and reloaded comes back equal."""
    original = GameState(player=Player(name="Aria", hp=30, gold=7), location="tavern")
    save_state(original, data_dir=tmp_path)

    loaded = load_state(data_dir=tmp_path)
    assert loaded == original  # Pydantic models compare by value


def test_save_creates_the_file_in_the_data_dir(tmp_path: Path) -> None:
    """Saving writes the state file inside the given data directory."""
    save_state(GameState(player=Player(name="Aria")), data_dir=tmp_path)
    assert (tmp_path / STATE_FILENAME).exists()


def test_load_state_with_no_save_returns_none(tmp_path: Path) -> None:
    """A fresh game (no save yet) loads as None, not a crash."""
    assert load_state(data_dir=tmp_path) is None


def test_load_state_rejects_schema_mismatch(tmp_path: Path) -> None:
    """A save that is valid JSON but violates the GameState schema fails loudly.

    hp is negative here — valid JSON, invalid game state. The strict loader must
    raise StateError rather than return a half-valid object.
    """
    bad = '{"player": {"name": "X", "hp": -50}}'
    (tmp_path / STATE_FILENAME).write_text(bad, encoding="utf-8")
    with pytest.raises(StateError):
        load_state(data_dir=tmp_path)


# --- M5: tolerant loader and clear_state -------------------------------------

def test_load_state_or_none_returns_state_when_valid(tmp_path: Path) -> None:
    """The tolerant loader returns a valid save just like load_state."""
    original = GameState(player=Player(name="Aria", gold=3))
    save_state(original, data_dir=tmp_path)
    assert load_state_or_none(data_dir=tmp_path) == original


def test_load_state_or_none_returns_none_when_missing(tmp_path: Path) -> None:
    """No save file -> None (start fresh)."""
    assert load_state_or_none(data_dir=tmp_path) is None


def test_load_state_or_none_discards_incompatible_save(tmp_path: Path) -> None:
    """An old/incompatible save (the M5 bug) is discarded as None, not raised.

    This mirrors the real bug: an old free-form save (fields like `health`,
    `player_name`, no `player`) doesn't match the schema. The tolerant loader
    returns None so the game can start fresh with a friendly message instead of
    crashing a tool.
    """
    old_format = (
        '{"player_name": "Adventurer", "health": 25, "gold": 15, '
        '"current_scene": "somewhere", "reputation": 0}'
    )
    (tmp_path / STATE_FILENAME).write_text(old_format, encoding="utf-8")
    assert load_state_or_none(data_dir=tmp_path) is None


def test_clear_state_removes_the_save(tmp_path: Path) -> None:
    """clear_state deletes an existing save (used to start a new game)."""
    save_state(GameState(player=Player(name="Aria")), data_dir=tmp_path)
    assert (tmp_path / STATE_FILENAME).exists()
    clear_state(data_dir=tmp_path)
    assert not (tmp_path / STATE_FILENAME).exists()


def test_clear_state_is_safe_when_no_save(tmp_path: Path) -> None:
    """clear_state on a missing file is a no-op, not an error."""
    clear_state(data_dir=tmp_path)  # should not raise
    assert not (tmp_path / STATE_FILENAME).exists()
