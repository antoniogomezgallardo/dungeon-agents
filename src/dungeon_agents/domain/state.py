"""Game-state persistence — deterministic domain logic (Milestone 2).

Reads and writes the game state as a JSON file inside a controlled project
directory (`data/`). Two safety ideas drive this module:

1. **Bounded writes.** The save path is always resolved *inside* the data
   directory. A caller can never write outside it (no `../` escapes, no absolute
   paths to system files). This is a first taste of the guardrails formalized in
   Milestone 6: the model may ask to "save state", but never *where*.
2. **Validated content.** In M2 the state is free-form JSON (strict Pydantic
   models arrive in Milestone 3). We still refuse to persist anything that isn't
   valid JSON, so a corrupt blob can't be silently written to disk.

Pure Python, no SDK. Unit-testable without an API key.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from dungeon_agents.domain.models import GameState

# The one directory game state is allowed to live in. Resolved relative to the
# project root (three parents up from this file: domain/ -> dungeon_agents/ ->
# src/ -> project root). `data/` is git-ignored.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = _PROJECT_ROOT / "data"
STATE_FILENAME = "game_state.json"


class StateError(Exception):
    """Raised when game state cannot be safely saved or loaded."""


def _state_path(data_dir: Path) -> Path:
    """Return the absolute path to the state file inside `data_dir`."""
    return data_dir / STATE_FILENAME


# --- Pydantic-validated persistence (single save format, unified in M5) ------
#
# Persistence works with the validated `GameState` model only. (Milestone 2's
# raw-JSON save/load was retired in M5: two formats coexisting caused a save
# written by one to be unreadable by the other. One validated format removes
# that whole class of bug.) Writes are still confined to the data directory, and
# state that doesn't match the GameState schema is rejected loudly.


def save_state(state: GameState, *, data_dir: Path | None = None) -> str:
    """Persist a validated `GameState` to the state file.

    Because `state` is already a GameState instance, it is guaranteed valid by
    construction — Pydantic would have refused to build an invalid one. We
    serialize it to normalized JSON and write it inside the data directory.

    Returns a short confirmation message.
    """
    target_dir = data_dir or DEFAULT_DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = _state_path(target_dir)
    # model_dump_json produces JSON straight from the validated model.
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return f"Game state saved to {path.name}."


def load_state(*, data_dir: Path | None = None) -> GameState | None:
    """Load and validate the saved state into a `GameState`.

    Returns:
        A validated GameState, or None when no valid save exists.

    Raises:
        StateError: If a save exists but does not match the GameState schema —
            failing loudly. Use `load_state_or_none` for the tolerant variant the
            game loop uses to discard incompatible saves gracefully.
    """
    path = _state_path(data_dir or DEFAULT_DATA_DIR)
    if not path.exists():
        return None

    raw = path.read_text(encoding="utf-8")
    try:
        # validate_json parses AND validates against the schema in one step.
        return GameState.model_validate_json(raw)
    except ValidationError as exc:
        raise StateError(f"saved state does not match the game schema: {exc}") from exc


def load_state_or_none(*, data_dir: Path | None = None) -> GameState | None:
    """Load the saved state, returning None if it's missing OR incompatible.

    The Milestone 5 change: the game once had two save formats (M2 free-form JSON
    and M3's validated GameState) that could clash — a save written in the old
    format failed the schema on load and crashed a tool. Now there is one
    validated format, and this tolerant loader lets the game *discard* an
    old/incompatible save instead of erroring: if the file doesn't match the
    current schema, we treat it as "no valid save" and let the caller start
    fresh with a friendly message.

    Returns:
        A validated GameState, or None when there is no save or the save is
        incompatible with the current game schema.
    """
    try:
        return load_state(data_dir=data_dir)
    except StateError:
        return None


def clear_state(*, data_dir: Path | None = None) -> None:
    """Delete the saved state file if it exists (used to start a new game)."""
    path = _state_path(data_dir or DEFAULT_DATA_DIR)
    path.unlink(missing_ok=True)
