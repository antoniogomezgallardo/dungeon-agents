"""Domain models — the validated shape of the game state (Milestone 3).

In M2 the game state was free-form JSON: anything could be saved, and attributes
the story showed (hp, gold...) were improvised by the model with no rules behind
them. These Pydantic models fix that: they define, in code, exactly what the game
state looks like — which fields exist, their types, and their bounds. Invalid
state can no longer be built or saved silently; Pydantic rejects it loudly.

Pure Python, no SDK. Fully unit-testable without an API key. This is the "data
contract" layer that maps directly to structured QA artifacts in TestOps AI
(a Player is to a game what a validated test case is to a test plan).

This file grows over Milestone 3: Player + InventoryItem first, then Quest,
GameState, and ActionResult.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Gameplay bounds, kept as named constants so they're testable and reusable —
# the same principle as the dice bounds in dice.py. Business rules live in code,
# not in prompts.
MAX_HP = 100


class InventoryItem(BaseModel):
    """A single stackable item the player carries.

    `quantity` must be at least 1: an item with zero copies isn't in the
    inventory at all, so representing it as an InventoryItem would be a bug. The
    model refuses to build one, catching that mistake at the data layer.
    """

    name: str = Field(min_length=1, description="Item name; cannot be empty.")
    quantity: int = Field(ge=1, description="How many are carried; at least 1.")


class Player(BaseModel):
    """The player's character.

    Bounds are enforced by the model, not by prompts or downstream code:
    - hp is clamped to [0, MAX_HP]: a character can be dead (0) or full, but
      never negative and never above the maximum.
    - gold cannot go negative: you can't owe gold, so the state can't represent
      it. (Whether the player can *afford* a purchase is a game rule for M4;
      this is just the invariant that gold is a non-negative count.)
    """

    name: str = Field(min_length=1, description="Character name; cannot be empty.")
    hp: int = Field(default=MAX_HP, ge=0, le=MAX_HP, description="Health, 0..MAX_HP.")
    max_hp: int = Field(default=MAX_HP, ge=1, le=MAX_HP, description="Upper HP bound.")
    gold: int = Field(default=0, ge=0, description="Coins carried; never negative.")


class Quest(BaseModel):
    """An objective the player is pursuing.

    In M3 this is a pure data shape: a quest has a title, a description, and a
    completion flag. The *rules* that decide when a quest is completed — and the
    win condition that makes finishing the game meaningful — are deliberately
    left to Milestone 4. Defining the data first keeps the milestones clean and
    gives M4 a validated structure to attach rules to.
    """

    title: str = Field(min_length=1, description="Short quest name; not empty.")
    description: str = Field(default="", description="What the quest asks for.")
    completed: bool = Field(default=False, description="True once fulfilled.")


class GameState(BaseModel):
    """The full snapshot of a game in progress — the container model.

    Everything needed to describe "where the adventure is right now" lives here:
    the player, their inventory, where they are, the active quest (if any), and a
    short running summary of the session. Because GameState nests the other
    models, validating a GameState validates the whole tree at once — a single
    malformed item or an out-of-range hp makes the entire state invalid, so it
    can never be saved silently (the M3 acceptance criterion).

    `active_quest` is optional: a fresh game may have no quest yet.
    `session_summary` is a concise running recap of the adventure, shown when a
    game is resumed. `last_scene` stores the Game Master's most recent narration
    verbatim, so resuming a saved game can reprint the exact scene the player was
    on — a deterministic resume (M5), not an improvised one. (From M6 the Lore
    Keeper agent will maintain the summary; for now the console loop sets both.)
    """

    player: Player
    inventory: list[InventoryItem] = Field(
        default_factory=list, description="Items the player carries."
    )
    location: str = Field(default="unknown", description="Where the player is.")
    active_quest: Quest | None = Field(
        default=None, description="Current objective, or None."
    )
    session_summary: str = Field(
        default="", description="Concise recap of the adventure so far."
    )
    last_scene: str = Field(
        default="",
        description="The Game Master's most recent scene text, for exact resume.",
    )


class ActionResult(BaseModel):
    """The outcome of applying a game action to the state.

    A small, explicit result object instead of a bare boolean or a loose dict.
    It says whether the action succeeded, carries a human-readable message
    (which the Game Master can narrate or which explains a rule failure), and
    optionally the new GameState the action produced.

    This becomes central in Milestone 4, where deterministic game rules return an
    ActionResult (e.g. "you can't spend 50 gold, you only have 10") instead of
    silently mutating state. Defining the contract now keeps M4 focused on rules.
    """

    success: bool = Field(description="Did the action succeed?")
    message: str = Field(default="", description="Human-readable outcome/why.")
    new_state: GameState | None = Field(
        default=None, description="Resulting state, if the action changed it."
    )


class SaveSlot(BaseModel):
    """A named checkpoint: everything needed to restore a game EXACTLY (M6+).

    The autosave (a single `game_state.json`) always holds the in-progress game.
    A SaveSlot is a *manual* checkpoint the player names — and to restore the
    exact point, it must carry both halves of a game:

    - `state`: the validated GameState (HP, gold, inventory, location, quest,
      last scene). Validating a SaveSlot validates this whole tree at once.
    - `conversation`: the Game Master's message history (what `to_input_list()`
      returns) as a list of plain dicts. Restoring it gives the model back its
      exact memory, so the game continues from the saved moment rather than
      re-improvising from a resume prompt.

    `conversation` is typed loosely (list of dicts) on purpose: the SDK owns that
    shape (it includes tool calls), and we persist it verbatim. If a future SDK
    changes the shape, a load simply fails validation and is reported as an
    incompatible checkpoint — an honest gap, not a crash.
    """

    name: str = Field(min_length=1, description="Checkpoint name; not empty.")
    state: GameState = Field(description="The validated game state to restore.")
    conversation: list[dict] = Field(
        default_factory=list,
        description="The Game Master's message history, restored verbatim.",
    )
