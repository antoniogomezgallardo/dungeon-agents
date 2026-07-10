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


def new_game_state() -> GameState:
    """Build a fresh starter game: a default hero and an opening quest."""
    return GameState(
        player=Player(name="Adventurer"),
        location="the Broken Wheel Inn",
        active_quest=Quest(
            title="Clear the cellar",
            description="Deal with whatever is lurking in the inn's cellar.",
        ),
    )


def _load_or_new_state() -> GameState:
    """Return the current game state, creating a starter one if none is valid.

    All game tools follow a load-modify-save pattern over a single, validated
    save format (M5 unified persistence). `load_state_or_none` tolerantly returns
    None for a missing OR incompatible save, so an old/foreign save never crashes
    a tool — we just start fresh instead.
    """
    return state.load_state_or_none() or new_game_state()


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
def save_game() -> str:
    """Save the player's current progress so it persists between sessions.

    Saves the game's validated state (player, inventory, gold, HP, location,
    quest) to a safe project directory. Call this when the player asks to save.
    You do not pass any data — the current tracked game state is saved as-is.
    """
    current = state.load_state_or_none() or new_game_state()
    return state.save_state(current)


@function_tool
def load_game() -> str:
    """Resume the player's saved adventure and summarize where they left off.

    Call this when the player asks to load or continue a saved game. Returns a
    short factual summary of the saved state (or a note that no valid save
    exists, in which case a new game begins).
    """
    saved = state.load_state_or_none()
    if saved is None:
        return "No saved game found (or it was incompatible). Starting a new adventure."
    p = saved.player
    quest = saved.active_quest.title if saved.active_quest else "none"
    return (
        f"Resumed. {p.name} is at {saved.location} with {p.hp}/{p.max_hp} HP and "
        f"{p.gold} gold. Active quest: {quest}."
    )


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
