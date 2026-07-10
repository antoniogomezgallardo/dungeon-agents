"""Game rules — deterministic logic that makes actions have consequences (M4).

This is where the pieces from earlier milestones finally connect. Rules operate
on the validated `GameState` models (M3), can use the dice (M2), and return an
`ActionResult` (M3) describing what happened — success plus the new state, or a
friendly failure message when a rule forbids the action.

Two design principles run through this module:
1. **Rules live in Python, not in prompts.** The agent proposes an action; these
   deterministic functions decide whether it's allowed and what results. This is
   the "AI orchestrates, code verifies" pattern, now applied to game logic.
2. **Rules are pure functions.** Each takes a GameState and returns a *new* one
   inside an ActionResult; it never mutates the input. That makes every rule
   trivially testable and reproducible — give it a state, assert the result.

Pure Python, no SDK. Unit-testable without an API key. This is the code that maps
most directly to a QA acceptance-criteria validator in TestOps AI.
"""

from __future__ import annotations

from dungeon_agents.domain.models import ActionResult, GameState, InventoryItem


def _find_item(state: GameState, name: str) -> InventoryItem | None:
    """Return the inventory item matching `name` (case-insensitive), or None."""
    key = name.strip().lower()
    for item in state.inventory:
        if item.name.lower() == key:
            return item
    return None


def get_inventory(state: GameState) -> str:
    """Return a human-readable summary of the player's inventory.

    A read-only rule: it inspects state but changes nothing. Handy as the body of
    a `get_inventory` tool so the agent (and player) can see what's carried.
    """
    if not state.inventory:
        return "The inventory is empty."
    lines = [f"- {item.name} x{item.quantity}" for item in state.inventory]
    return "Inventory:\n" + "\n".join(lines)


def add_item(state: GameState, name: str, quantity: int = 1) -> ActionResult:
    """Add `quantity` of an item to the inventory, returning the new state.

    Rules enforced:
    - quantity must be at least 1 (adding zero/negative items is meaningless).
    - If the item already exists, its stack grows; otherwise a new stack is made.

    Returns an ActionResult; on a rule violation, success is False with a
    friendly message and the state is left unchanged.
    """
    name = name.strip()
    if not name:
        return ActionResult(success=False, message="An item needs a name.")
    if quantity < 1:
        return ActionResult(
            success=False, message="You can only add a positive number of items."
        )

    # Work on a copy so the input state is never mutated (pure function).
    new_state = state.model_copy(deep=True)
    existing = _find_item(new_state, name)
    if existing is not None:
        existing.quantity += quantity
    else:
        new_state.inventory.append(InventoryItem(name=name, quantity=quantity))

    return ActionResult(
        success=True,
        message=f"Added {quantity}x {name}.",
        new_state=new_state,
    )


def remove_item(state: GameState, name: str, quantity: int = 1) -> ActionResult:
    """Remove `quantity` of an item, returning the new state.

    Rules enforced:
    - quantity must be at least 1.
    - You cannot remove an item you do not have.
    - You cannot remove more than you carry.
    When a stack drops to zero it is taken out of the inventory entirely.

    On any violation, success is False with a friendly message and the state is
    unchanged — the core M4 idea that impossible actions fail safely.
    """
    name = name.strip()
    if quantity < 1:
        return ActionResult(
            success=False, message="You can only remove a positive number of items."
        )

    new_state = state.model_copy(deep=True)
    existing = _find_item(new_state, name)
    if existing is None:
        return ActionResult(
            success=False, message=f"You don't have any {name} to remove."
        )
    if existing.quantity < quantity:
        return ActionResult(
            success=False,
            message=(
                f"You only have {existing.quantity}x {existing.name}, "
                f"can't remove {quantity}."
            ),
        )

    existing.quantity -= quantity
    if existing.quantity == 0:
        new_state.inventory = [i for i in new_state.inventory if i is not existing]

    return ActionResult(
        success=True,
        message=f"Removed {quantity}x {name}.",
        new_state=new_state,
    )


# --- Resource rules: gold and HP ---------------------------------------------
#
# These make the player's attributes finally *matter*. Like the inventory rules,
# each is a pure function returning an ActionResult; a rule violation fails safely
# with a friendly message and leaves the state unchanged.


def spend_gold(state: GameState, amount: int) -> ActionResult:
    """Spend `amount` of gold, returning the new state.

    Rules enforced:
    - amount must be positive.
    - You cannot spend more gold than you have (gold can never go negative — the
      Player model already forbids negative gold, so this rule is what keeps the
      invariant satisfiable rather than letting a purchase attempt it and fail).
    """
    if amount < 1:
        return ActionResult(
            success=False, message="You can only spend a positive amount of gold."
        )
    if amount > state.player.gold:
        return ActionResult(
            success=False,
            message=f"You only have {state.player.gold} gold, can't spend {amount}.",
        )

    new_state = state.model_copy(deep=True)
    new_state.player.gold -= amount
    return ActionResult(
        success=True,
        message=f"Spent {amount} gold ({new_state.player.gold} left).",
        new_state=new_state,
    )


def earn_gold(state: GameState, amount: int) -> ActionResult:
    """Add `amount` of gold to the player, returning the new state."""
    if amount < 1:
        return ActionResult(
            success=False, message="You can only earn a positive amount of gold."
        )
    new_state = state.model_copy(deep=True)
    new_state.player.gold += amount
    return ActionResult(
        success=True,
        message=f"Earned {amount} gold ({new_state.player.gold} total).",
        new_state=new_state,
    )


def change_hp(state: GameState, delta: int) -> ActionResult:
    """Apply a health change (`delta` may be negative for damage).

    HP is clamped to [0, max_hp]: damage can't push it below 0, and healing can't
    push it above the player's maximum. Clamping here means the caller never has
    to worry about producing an invalid Player — the rule guarantees the result
    is in range. A message notes when the player falls (reaches 0).
    """
    new_state = state.model_copy(deep=True)
    player = new_state.player
    # Clamp into the valid range rather than letting the model raise.
    player.hp = max(0, min(player.hp + delta, player.max_hp))

    if player.hp == 0:
        message = f"{player.name} has fallen! (HP reached 0)"
    elif delta < 0:
        message = f"{player.name} takes {-delta} damage (HP now {player.hp})."
    else:
        message = f"{player.name} recovers {delta} HP (HP now {player.hp})."

    return ActionResult(success=True, message=message, new_state=new_state)


# --- Win / lose conditions ---------------------------------------------------
#
# The game finally has a way to *end*. These are deterministic checks over the
# state — the model decides how the story unfolds, but whether the game is won or
# lost is decided here, in tested code, not improvised by the narrator.


def complete_quest(state: GameState) -> ActionResult:
    """Mark the active quest as completed — the game's win condition.

    Rules enforced:
    - There must be an active quest to complete.
    - A quest already completed can't be completed again.
    On success, the returned state has `active_quest.completed = True`, which
    `is_game_won` then recognizes.
    """
    if state.active_quest is None:
        return ActionResult(
            success=False, message="There is no active quest to complete."
        )
    if state.active_quest.completed:
        return ActionResult(
            success=False, message="That quest is already completed."
        )

    new_state = state.model_copy(deep=True)
    new_state.active_quest.completed = True
    return ActionResult(
        success=True,
        message=f"Quest completed: {new_state.active_quest.title}! You have won.",
        new_state=new_state,
    )


def is_game_won(state: GameState) -> bool:
    """True when the active quest exists and is completed (victory)."""
    return state.active_quest is not None and state.active_quest.completed


def is_game_over(state: GameState) -> bool:
    """True when the player has fallen (HP reached 0) — the lose condition."""
    return state.player.hp == 0
