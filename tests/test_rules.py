"""Tests for the game rules (Milestone 4).

Deterministic, no API key, no SDK. Each rule is a pure function: give it a state,
assert the ActionResult. We test the happy path AND that invalid operations fail
safely (success=False, friendly message, state unchanged) — the M4 acceptance
criterion "invalid inventory operations fail safely".
"""

from __future__ import annotations

import pytest

from dungeon_agents.domain.models import (
    MAX_HP,
    GameState,
    InventoryItem,
    Player,
    Quest,
)
from dungeon_agents.domain.rules import (
    add_item,
    can_afford,
    change_hp,
    complete_quest,
    earn_gold,
    get_inventory,
    is_game_over,
    is_game_won,
    remove_item,
    spend_gold,
)


def _fresh_state(**player_kwargs) -> GameState:
    """A minimal valid GameState for a player with the given attributes."""
    return GameState(player=Player(name="Aria", **player_kwargs))


# --- get_inventory -----------------------------------------------------------

def test_get_inventory_empty() -> None:
    assert get_inventory(_fresh_state()) == "The inventory is empty."


def test_get_inventory_lists_items() -> None:
    state = GameState(
        player=Player(name="Aria"),
        inventory=[InventoryItem(name="Torch", quantity=2)],
    )
    summary = get_inventory(state)
    assert "Torch x2" in summary


# --- add_item ----------------------------------------------------------------

def test_add_item_to_empty_inventory() -> None:
    result = add_item(_fresh_state(), "Health Potion", 2)
    assert result.success is True
    assert result.new_state.inventory[0].name == "Health Potion"
    assert result.new_state.inventory[0].quantity == 2


def test_add_item_stacks_existing() -> None:
    state = GameState(
        player=Player(name="Aria"),
        inventory=[InventoryItem(name="Torch", quantity=1)],
    )
    result = add_item(state, "torch", 3)  # case-insensitive match
    assert result.success is True
    assert len(result.new_state.inventory) == 1
    assert result.new_state.inventory[0].quantity == 4


def test_add_item_does_not_mutate_input_state() -> None:
    """Rules are pure: the original state must be untouched."""
    state = _fresh_state()
    add_item(state, "Torch", 1)
    assert state.inventory == []  # original unchanged


@pytest.mark.parametrize("bad_qty", [0, -3])
def test_add_item_rejects_non_positive_quantity(bad_qty: int) -> None:
    result = add_item(_fresh_state(), "Torch", bad_qty)
    assert result.success is False
    assert result.new_state is None


def test_add_item_rejects_empty_name() -> None:
    result = add_item(_fresh_state(), "   ", 1)
    assert result.success is False


# --- remove_item -------------------------------------------------------------

def test_remove_item_success() -> None:
    state = GameState(
        player=Player(name="Aria"),
        inventory=[InventoryItem(name="Torch", quantity=3)],
    )
    result = remove_item(state, "Torch", 2)
    assert result.success is True
    assert result.new_state.inventory[0].quantity == 1


def test_remove_item_drops_stack_at_zero() -> None:
    state = GameState(
        player=Player(name="Aria"),
        inventory=[InventoryItem(name="Torch", quantity=1)],
    )
    result = remove_item(state, "Torch", 1)
    assert result.success is True
    assert result.new_state.inventory == []  # stack removed entirely


def test_cannot_remove_item_you_dont_have() -> None:
    """The M4 rule: you can't use/remove an item you don't have."""
    result = remove_item(_fresh_state(), "Sword", 1)
    assert result.success is False
    assert "don't have" in result.message.lower()
    assert result.new_state is None  # nothing changed


def test_cannot_remove_more_than_you_carry() -> None:
    state = GameState(
        player=Player(name="Aria"),
        inventory=[InventoryItem(name="Arrow", quantity=2)],
    )
    result = remove_item(state, "Arrow", 5)
    assert result.success is False
    assert "only have 2" in result.message.lower()


def test_remove_item_does_not_mutate_input_state() -> None:
    state = GameState(
        player=Player(name="Aria"),
        inventory=[InventoryItem(name="Torch", quantity=2)],
    )
    remove_item(state, "Torch", 1)
    assert state.inventory[0].quantity == 2  # original unchanged


# --- spend_gold / earn_gold --------------------------------------------------

def test_spend_gold_success() -> None:
    result = spend_gold(_fresh_state(gold=10), 4)
    assert result.success is True
    assert result.new_state.player.gold == 6


def test_cannot_spend_more_gold_than_you_have() -> None:
    """The M4 rule: you can't spend more gold than you have."""
    result = spend_gold(_fresh_state(gold=3), 10)
    assert result.success is False
    assert "only have 3 gold" in result.message.lower()
    assert result.new_state is None  # unchanged


@pytest.mark.parametrize("bad_amount", [0, -5])
def test_spend_gold_rejects_non_positive(bad_amount: int) -> None:
    result = spend_gold(_fresh_state(gold=10), bad_amount)
    assert result.success is False


def test_spend_gold_does_not_mutate_input_state() -> None:
    state = _fresh_state(gold=10)
    spend_gold(state, 5)
    assert state.player.gold == 10  # original unchanged


def test_earn_gold_success() -> None:
    result = earn_gold(_fresh_state(gold=5), 20)
    assert result.success is True
    assert result.new_state.player.gold == 25


# --- change_hp ---------------------------------------------------------------

def test_change_hp_damage() -> None:
    result = change_hp(_fresh_state(hp=50), -20)
    assert result.success is True
    assert result.new_state.player.hp == 30


def test_change_hp_healing() -> None:
    result = change_hp(_fresh_state(hp=50), 10)
    assert result.new_state.player.hp == 60


def test_hp_cannot_go_below_zero() -> None:
    """Damage clamps at 0, never negative — and flags the player has fallen."""
    result = change_hp(_fresh_state(hp=10), -999)
    assert result.new_state.player.hp == 0
    assert "fallen" in result.message.lower()


def test_hp_cannot_exceed_max() -> None:
    """Healing clamps at max_hp, never above."""
    result = change_hp(_fresh_state(hp=MAX_HP - 5), 999)
    assert result.new_state.player.hp == MAX_HP


def test_change_hp_does_not_mutate_input_state() -> None:
    state = _fresh_state(hp=50)
    change_hp(state, -20)
    assert state.player.hp == 50  # original unchanged


# --- win / lose conditions ---------------------------------------------------

def _state_with_quest(completed: bool = False) -> GameState:
    return GameState(
        player=Player(name="Aria"),
        active_quest=Quest(title="Save the town", completed=completed),
    )


def test_complete_quest_wins_the_game() -> None:
    state = _state_with_quest()
    assert is_game_won(state) is False  # not yet

    result = complete_quest(state)
    assert result.success is True
    assert result.new_state.active_quest.completed is True
    assert is_game_won(result.new_state) is True  # now won
    assert "won" in result.message.lower()


def test_cannot_complete_when_no_active_quest() -> None:
    result = complete_quest(_fresh_state())  # no quest
    assert result.success is False
    assert "no active quest" in result.message.lower()


def test_cannot_complete_an_already_completed_quest() -> None:
    result = complete_quest(_state_with_quest(completed=True))
    assert result.success is False
    assert "already completed" in result.message.lower()


def test_is_game_won_false_without_quest() -> None:
    assert is_game_won(_fresh_state()) is False


def test_is_game_over_when_hp_zero() -> None:
    assert is_game_over(_fresh_state(hp=0)) is True
    assert is_game_over(_fresh_state(hp=1)) is False


# --- can_afford (M6 — the honest, deterministic resource pre-check) ----------

def test_can_afford_no_cost_is_trivially_true() -> None:
    """An action that costs nothing is always affordable."""
    result = can_afford(_fresh_state())
    assert result.success is True


def test_can_afford_enough_gold() -> None:
    result = can_afford(_fresh_state(gold=50), gold_cost=30)
    assert result.success is True


def test_can_afford_not_enough_gold_fails_with_reason() -> None:
    """Too little gold fails, and the message names exactly what's short."""
    result = can_afford(_fresh_state(gold=3), gold_cost=5)
    assert result.success is False
    assert "3" in result.message and "5" in result.message


def test_can_afford_negative_cost_rejected() -> None:
    result = can_afford(_fresh_state(gold=10), gold_cost=-1)
    assert result.success is False


def test_can_afford_has_the_item() -> None:
    state = _fresh_state()
    state.inventory.append(InventoryItem(name="Potion", quantity=2))
    result = can_afford(state, item_name="potion", item_quantity=2)
    assert result.success is True


def test_can_afford_missing_item_fails() -> None:
    result = can_afford(_fresh_state(), item_name="Rope", item_quantity=1)
    assert result.success is False
    assert "rope" in result.message.lower()


def test_can_afford_not_enough_of_the_item_fails() -> None:
    state = _fresh_state()
    state.inventory.append(InventoryItem(name="Arrow", quantity=1))
    result = can_afford(state, item_name="Arrow", item_quantity=3)
    assert result.success is False


def test_can_afford_checks_gold_and_item_together() -> None:
    """Both shortfalls are reported when both gold and an item are lacking."""
    result = can_afford(_fresh_state(gold=0), gold_cost=5, item_name="Key")
    assert result.success is False
    assert "gold" in result.message.lower() and "key" in result.message.lower()


def test_can_afford_does_not_mutate_state() -> None:
    """The pre-check is read-only: gold and inventory are untouched."""
    state = _fresh_state(gold=10)
    state.inventory.append(InventoryItem(name="Coin", quantity=1))
    can_afford(state, gold_cost=5, item_name="Coin", item_quantity=1)
    assert state.player.gold == 10
    assert state.inventory[0].quantity == 1
