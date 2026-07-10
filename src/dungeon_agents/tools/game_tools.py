"""Game tools exposed to the Game Master agent (Milestone 2).

Each function here is a THIN wrapper around a tested `domain/` function, marked
with the SDK's `@function_tool` decorator so the agent can call it. The wrappers
deliberately contain no business logic — they delegate to the domain and turn its
exceptions into friendly strings the model can read and react to.

Why this split:
- The real rules and validation live in `domain/` (pure Python, unit-tested
  without an API key). See `domain/dice.py` and `domain/state.py`.
- This layer is the only place these functions gain their "tool" identity. The
  docstrings below are read by the SDK and shown to the model, so they double as
  the agent-facing instructions for when and how to use each tool.
"""

from __future__ import annotations

from agents import function_tool

from dungeon_agents.domain import dice, state


@function_tool
def roll_dice(sides: int) -> str:
    """Roll a single die and return the result.

    Use this whenever the outcome of an action depends on chance (attacks,
    skill checks, random events). Never invent a dice result yourself — always
    call this tool so the number is real and fair.

    Args:
        sides: Number of faces on the die. Must be between 2 and 100.
    """
    try:
        value = dice.roll_dice(sides)
    except dice.InvalidDiceError as exc:
        return f"Invalid dice roll: {exc}"
    return f"Rolled a {value} on a {sides}-sided die."


@function_tool
def save_game_state(state_json: str) -> str:
    """Save the current game state so it persists between sessions.

    Provide the full game state as a JSON string (for now, any valid JSON —
    e.g. player name, hp, gold, location). The state is stored in a safe project
    directory; you cannot choose where it is written.

    Args:
        state_json: The game state to save, as a valid JSON string.
    """
    try:
        return state.save_game_state(state_json)
    except state.StateError as exc:
        return f"Could not save game state: {exc}"


@function_tool
def load_game_state() -> str:
    """Load the saved game state and return it as a JSON string.

    Use this at the start of a session to resume a saved adventure. Returns
    "{}" (an empty state) if there is no saved game yet.
    """
    try:
        return state.load_game_state()
    except state.StateError as exc:
        return f"Could not load game state: {exc}"
