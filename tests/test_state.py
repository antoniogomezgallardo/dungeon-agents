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

from dungeon_agents.domain.models import GameState, Player, SaveSlot
from dungeon_agents.domain.state import (
    STATE_FILENAME,
    StateError,
    clear_state,
    list_checkpoints,
    load_checkpoint,
    load_state,
    load_state_or_none,
    save_checkpoint,
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


# --- Named checkpoints (manual save/load slots) ------------------------------

def _slot(name: str = "battle") -> SaveSlot:
    return SaveSlot(
        name=name,
        state=GameState(player=Player(name="Aria", gold=12), location="ruins"),
        conversation=[{"role": "user", "content": "I enter the ruins"}],
    )


def test_checkpoint_roundtrips_state_and_conversation(tmp_path: Path) -> None:
    """A checkpoint restores BOTH the game state and the conversation exactly."""
    save_checkpoint(_slot(), data_dir=tmp_path)
    loaded = load_checkpoint("battle", data_dir=tmp_path)
    assert loaded is not None
    assert loaded.state.player.gold == 12
    assert loaded.state.location == "ruins"
    assert loaded.conversation == [{"role": "user", "content": "I enter the ruins"}]


def test_load_missing_checkpoint_returns_none(tmp_path: Path) -> None:
    """Loading a checkpoint that was never saved returns None, not a crash."""
    assert load_checkpoint("nope", data_dir=tmp_path) is None


def test_checkpoint_name_is_sanitized_to_a_safe_file(tmp_path: Path) -> None:
    """A name with path traversal is stripped to a safe filename (bounded write).

    The dangerous name must not escape the saves directory, and must round-trip
    under its sanitized form.
    """
    save_checkpoint(_slot(name="../../evil boss"), data_dir=tmp_path)
    # Nothing was written outside the data dir.
    assert not (tmp_path.parent / "evil boss.json").exists()
    # It IS retrievable under the same (sanitized) name.
    assert load_checkpoint("../../evil boss", data_dir=tmp_path) is not None


def test_checkpoint_all_illegal_name_raises(tmp_path: Path) -> None:
    """A name with no usable characters fails loudly rather than writing garbage."""
    with pytest.raises(StateError):
        save_checkpoint(_slot(name="../"), data_dir=tmp_path)


def test_load_incompatible_checkpoint_returns_none(tmp_path: Path) -> None:
    """A checkpoint file that doesn't match the SaveSlot schema loads as None."""
    saves = tmp_path / "saves"
    saves.mkdir(parents=True)
    (saves / "broken.json").write_text('{"name": "broken"}', encoding="utf-8")  # no state
    assert load_checkpoint("broken", data_dir=tmp_path) is None


def test_list_checkpoints_returns_saved_names(tmp_path: Path) -> None:
    """list_checkpoints reports saved slot names; empty when none exist."""
    assert list_checkpoints(data_dir=tmp_path) == []
    save_checkpoint(_slot(name="alpha"), data_dir=tmp_path)
    save_checkpoint(_slot(name="beta"), data_dir=tmp_path)
    assert list_checkpoints(data_dir=tmp_path) == ["alpha", "beta"]
