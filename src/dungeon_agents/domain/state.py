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

import json
from pathlib import Path

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


def save_game_state(state_json: str, *, data_dir: Path | None = None) -> str:
    """Validate `state_json` and write it to the state file.

    Args:
        state_json: The game state as a JSON string. Must parse as valid JSON.
        data_dir: Where to store the file. Defaults to the project's `data/`.
            Injectable so tests can use a temp directory (reproducible, isolated).

    Returns:
        A short human-friendly confirmation message (handy as a tool result).

    Raises:
        StateError: If `state_json` is not valid JSON. Failing here keeps a
            malformed blob from ever reaching disk.
    """
    try:
        # Parse then re-dump: this both validates the input is real JSON and
        # normalizes the on-disk format (pretty, stable key order).
        parsed = json.loads(state_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise StateError(f"state must be valid JSON: {exc}") from exc

    target_dir = data_dir or DEFAULT_DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = _state_path(target_dir)
    path.write_text(json.dumps(parsed, indent=2, sort_keys=True), encoding="utf-8")

    return f"Game state saved to {path.name}."


def load_game_state(*, data_dir: Path | None = None) -> str:
    """Read the saved game state and return it as a JSON string.

    Args:
        data_dir: Where to read from. Defaults to the project's `data/`.

    Returns:
        The saved state as a JSON string, or an empty-object string `"{}"` when
        no save exists yet — a safe default so callers never crash on a missing
        file (a fresh game just starts from an empty state).

    Raises:
        StateError: If a save file exists but is corrupt (not valid JSON).
    """
    path = _state_path(data_dir or DEFAULT_DATA_DIR)
    if not path.exists():
        return "{}"

    raw = path.read_text(encoding="utf-8")
    try:
        # Validate on read too: a corrupt save should fail loudly, not feed
        # garbage back into the game.
        json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateError(f"saved state is corrupt: {exc}") from exc

    return raw
