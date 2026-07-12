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
from dungeon_agents.domain.models import ActionResult, GameState, Player, Quest


def new_game_state() -> GameState:
    """Build a fresh starter game with a NEUTRAL, undefined setting.

    Location and quest are intentionally left undefined here: the Game Master
    improvises a unique story each game and fills them in via `set_location` /
    `set_quest`, so the saved state matches the narration the player actually
    sees (rather than a hard-coded template that would contradict the story).
    """
    return GameState(player=Player(name="Adventurer"))


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
def check_can_afford(
    gold_cost: int = 0, item_name: str = "", item_quantity: int = 1
) -> str:
    """Check whether the player can afford a cost BEFORE allowing an action.

    Deterministic and read-only: the game's code (not the model) decides whether
    the player has enough. Call this before allowing an action that spends gold or
    uses items, passing the numbers you read from the story:
    - `gold_cost`: how much gold the action costs (0 if none).
    - `item_name` / `item_quantity`: an item the action consumes and how many.
    Returns "Affordable." or a "Cannot afford: ..." reason naming what is short —
    relay that reason to the player if disallowed. This nothing-is-spent check
    replaces the old, model-judged `validate_action`.

    Args:
        gold_cost: Gold the action would cost. Defaults to 0.
        item_name: An item the action would consume. Optional.
        item_quantity: How many of that item are needed. Defaults to 1.
    """
    result = rules.can_afford(
        _load_or_new_state(), gold_cost, item_name, item_quantity
    )
    return result.message


@function_tool
def earn_gold(amount: int) -> str:
    """Give the player gold (a reward, loot, payment) and PERSIST it.

    Call this whenever the story says the player gains gold, so the tracked state
    (which stats and purchases read) actually reflects it. Without this call the
    gold exists only in the narration and is lost on reload.

    Args:
        amount: How much gold to add (must be positive).
    """
    return _apply(rules.earn_gold(_load_or_new_state(), amount))


@function_tool
def spend_gold(amount: int) -> str:
    """Deduct gold the player spends (a purchase, a bribe, a toll) and PERSIST it.

    The rule refuses to overspend: a player cannot go below 0 gold. Prefer calling
    `check_can_afford` first to tell the player *before* committing; this tool
    performs the actual deduction once the spend is allowed.

    Args:
        amount: How much gold to deduct (must be positive).
    """
    return _apply(rules.spend_gold(_load_or_new_state(), amount))


@function_tool
def change_hp(delta: int) -> str:
    """Apply a health change (damage as a negative delta, healing as positive).

    HP is clamped to the valid range by the rules (never below 0, never above the
    player's maximum), and the change is PERSISTED. Call this when the story deals
    damage or heals the player, so stats and the lose condition stay accurate.

    Args:
        delta: HP change; negative for damage, positive for healing.
    """
    return _apply(rules.change_hp(_load_or_new_state(), delta))


@function_tool
def skill_check(difficulty: str = "moderate") -> str:
    """Resolve a risky action by rolling 1d20 against a named difficulty.

    Use this instead of a bare dice roll whenever an action's success is
    uncertain (an attack, a climb, picking a lock, persuading a guard). YOU judge
    how hard it is and pass a difficulty; the CODE rolls and decides success or
    failure — you cannot overrule the result, only narrate it.

    Difficulty levels: "trivial", "easy", "moderate", "hard", "very_hard".
    Returns the roll, the threshold, and whether it SUCCEEDED or FAILED.

    Args:
        difficulty: How hard the action is. Defaults to "moderate".
    """
    try:
        result = dice.resolve_check(difficulty)
    except dice.InvalidDifficultyError as exc:
        return f"Invalid difficulty: {exc}"
    verdict = "SUCCESS" if result.success else "FAILURE"
    return (
        f"{verdict}: rolled {result.roll} on 1d20 vs {result.difficulty} "
        f"(needs {result.threshold}+)."
    )


@function_tool
def update_summary(summary: str) -> str:
    """Record a concise running summary of the adventure so far.

    Call this after story-significant moments — accepting or completing a quest,
    reaching a new place, meeting a key character, a major win or loss — to keep a
    short recap of the important beats. The summary is shown to the player when
    they resume a saved game or ask to see it, so write it as a brief factual
    recap of what has happened (2-4 sentences), not a to-do list. Replace the
    previous summary with an updated version each time.

    Args:
        summary: The updated recap of the adventure so far.
    """
    game = _load_or_new_state()
    game.session_summary = summary.strip()
    return _apply(ActionResult(success=True, message="Summary updated.", new_state=game))


@function_tool
def set_location(location: str) -> str:
    """Set the player's current location to match your narration.

    Call this whenever you place the player somewhere or they travel — including
    the very first scene — so the tracked state matches the story the player
    sees. Use a short place name (e.g. "the Whispering Forest", "Karth's docks").

    Args:
        location: The player's current location, as a short name.
    """
    location = location.strip()
    if not location:
        return "A location needs a name."
    game = _load_or_new_state()
    game.location = location
    return _apply(ActionResult(success=True, message=f"Location set to {location}.", new_state=game))


@function_tool
def set_quest(title: str, description: str = "") -> str:
    """Set (or replace) the player's active quest to match your narration.

    Call this when the player takes on their objective — including the opening
    quest you introduce — so the tracked quest matches the story. Setting a new
    quest replaces the previous active one.

    Args:
        title: A short quest name (e.g. "Recover the stolen relic").
        description: What the quest asks for (optional, one sentence).
    """
    title = title.strip()
    if not title:
        return "A quest needs a title."
    game = _load_or_new_state()
    game.active_quest = Quest(title=title, description=description.strip())
    return _apply(ActionResult(success=True, message=f"Quest set: {title}.", new_state=game))
