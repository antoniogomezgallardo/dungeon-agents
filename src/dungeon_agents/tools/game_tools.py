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

from dungeon_agents.domain import dice, rules, state
from dungeon_agents.domain.models import GameState, Player, Quest


def _load_or_new_state() -> GameState:
    """Return the current game state, creating a starter one if none is saved.

    The inventory/resource tools follow a load-modify-save pattern so state
    persists between turns in `data/game_state.json` (validated by M3). If no
    save exists yet, we seed a new game with a default hero and an opening quest
    so there is always a valid state and a goal to complete.
    """
    current = state.load_state()
    if current is not None:
        return current
    return GameState(
        player=Player(name="Adventurer"),
        location="the Broken Wheel Inn",
        active_quest=Quest(
            title="Clear the cellar",
            description="Deal with whatever is lurking in the inn's cellar.",
        ),
    )


def _apply(result) -> str:
    """Persist a rule's new state (on success) and return its message.

    Rules return an ActionResult; on success we save the produced state so the
    change sticks, then hand the friendly message back to the agent to narrate.
    On failure nothing is saved and the failure message is returned as-is.
    """
    if result.success and result.new_state is not None:
        state.save_state(result.new_state)
    return result.message


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


# --- Milestone 4: inventory & rule tools -------------------------------------
#
# These expose the deterministic game rules to the agent. Each loads the current
# state, applies a rule, and (on success) saves the new state. The rules — not
# the model — decide whether an action is allowed, and return a friendly message
# for the agent to narrate.


@function_tool
def get_inventory() -> str:
    """Show what the player is currently carrying.

    Call this when the player asks about their inventory or you need to know what
    they have before resolving an action.
    """
    return rules.get_inventory(_load_or_new_state())


@function_tool
def add_item(item_name: str, quantity: int = 1) -> str:
    """Give the player an item (e.g. loot, a purchase, a reward).

    Args:
        item_name: The item to add.
        quantity: How many to add (must be positive).
    """
    return _apply(rules.add_item(_load_or_new_state(), item_name, quantity))


@function_tool
def remove_item(item_name: str, quantity: int = 1) -> str:
    """Remove an item the player uses, drops, or loses.

    The player cannot lose an item they do not have — the rule refuses safely and
    explains why. Never remove items the player doesn't possess.

    Args:
        item_name: The item to remove.
        quantity: How many to remove (must be positive).
    """
    return _apply(rules.remove_item(_load_or_new_state(), item_name, quantity))


@function_tool
def validate_action(action: str) -> str:
    """Check whether a player's intended action is allowed by the game rules.

    Use this before narrating the outcome of an action that spends resources or
    uses items, so you never let the player do something impossible (spend gold
    they lack, use an item they don't carry). Returns whether it's allowed and,
    if not, a friendly reason to relay to the player.

    Args:
        action: A short description of what the player wants to do.
    """
    game = _load_or_new_state()
    summary = rules.get_inventory(game)
    return (
        f"Player has {game.player.gold} gold and {game.player.hp} HP. {summary}\n"
        f"Judge whether this action is possible with those resources: {action}"
    )
