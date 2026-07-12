"""Tests for the domain models (Milestone 3).

Deterministic, no API key, no SDK. The point of these tests is the M3 acceptance
criterion: invalid state must be rejected loudly, never built silently. So for
each model we assert both the happy path AND that bad values raise
ValidationError.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dungeon_agents.domain.models import (
    MAX_HP,
    ActionResult,
    GameState,
    InventoryItem,
    Player,
    Quest,
)


# --- InventoryItem -----------------------------------------------------------

def test_inventory_item_valid() -> None:
    """A well-formed item builds and keeps its values."""
    item = InventoryItem(name="Health Potion", quantity=3)
    assert item.name == "Health Potion"
    assert item.quantity == 3


def test_inventory_item_quantity_defaults_are_enforced() -> None:
    """Quantity below 1 is rejected — a zero/negative stack is meaningless."""
    with pytest.raises(ValidationError):
        InventoryItem(name="Torch", quantity=0)
    with pytest.raises(ValidationError):
        InventoryItem(name="Torch", quantity=-2)


def test_inventory_item_name_cannot_be_empty() -> None:
    """An empty item name is rejected."""
    with pytest.raises(ValidationError):
        InventoryItem(name="", quantity=1)


# --- Player ------------------------------------------------------------------

def test_player_valid_with_defaults() -> None:
    """A player with just a name gets sensible, in-bounds defaults."""
    hero = Player(name="Aria")
    assert hero.name == "Aria"
    assert hero.hp == MAX_HP
    assert hero.max_hp == MAX_HP
    assert hero.gold == 0


def test_player_accepts_valid_custom_values() -> None:
    """Explicit in-range values are accepted."""
    hero = Player(name="Borin", hp=30, max_hp=80, gold=15)
    assert (hero.hp, hero.max_hp, hero.gold) == (30, 80, 15)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "X", "hp": -1},            # hp below 0
        {"name": "X", "hp": MAX_HP + 1},    # hp above max
        {"name": "X", "gold": -5},          # negative gold
        {"name": ""},                        # empty name
    ],
)
def test_player_rejects_invalid_state(kwargs: dict) -> None:
    """Out-of-bounds or malformed player state raises, never builds silently."""
    with pytest.raises(ValidationError):
        Player(**kwargs)


def test_player_rejects_wrong_types() -> None:
    """Non-integer hp is rejected (data contract enforces types)."""
    with pytest.raises(ValidationError):
        Player(name="X", hp="lots")  # type: ignore[arg-type]


# --- Quest -------------------------------------------------------------------

def test_quest_valid_with_defaults() -> None:
    """A quest needs only a title; it defaults to not-completed."""
    q = Quest(title="Find the lost amulet")
    assert q.title == "Find the lost amulet"
    assert q.completed is False
    assert q.description == ""


def test_quest_title_cannot_be_empty() -> None:
    """An empty quest title is rejected."""
    with pytest.raises(ValidationError):
        Quest(title="")


# --- GameState (the container) -----------------------------------------------

def test_game_state_minimal_valid() -> None:
    """A GameState needs only a player; the rest gets safe defaults."""
    state = GameState(player=Player(name="Aria"))
    assert state.player.name == "Aria"
    assert state.inventory == []
    assert state.location == "unknown"
    assert state.active_quest is None
    assert state.session_summary == ""
    assert state.last_scene == ""


def test_game_state_carries_last_scene_and_summary() -> None:
    """last_scene and session_summary persist for deterministic resume (M5)."""
    state = GameState(
        player=Player(name="Aria"),
        session_summary="Aria reached the inn and took a cellar-clearing job.",
        last_scene="You stand at the cellar door, torch in hand. What do you do?",
    )
    assert "cellar-clearing" in state.session_summary
    assert state.last_scene.startswith("You stand at the cellar door")


def test_game_state_full_tree_valid() -> None:
    """A fully populated state validates all nested models together."""
    state = GameState(
        player=Player(name="Borin", hp=40, gold=10),
        inventory=[InventoryItem(name="Torch", quantity=2)],
        location="Millhaven",
        active_quest=Quest(title="Clear the cellar"),
        session_summary="Arrived in town, took a cellar-clearing job.",
    )
    assert state.inventory[0].name == "Torch"
    assert state.active_quest.title == "Clear the cellar"


def test_game_state_rejects_invalid_nested_player() -> None:
    """An out-of-range hp on the nested player invalidates the whole state.

    We pass raw dict data (not a pre-built Player) so Pydantic actually validates
    the nested fields — building a GameState from raw input revalidates the tree.
    """
    with pytest.raises(ValidationError):
        GameState(player={"name": "X", "hp": -99})  # hp below 0


def test_game_state_rejects_invalid_nested_item() -> None:
    """A bad inventory item makes the entire GameState invalid — validation
    cascades through the nested models, so nothing malformed slips through."""
    with pytest.raises(ValidationError):
        GameState(
            player=Player(name="Aria"),
            inventory=[{"name": "Torch", "quantity": 0}],  # quantity < 1
        )


# --- ActionResult ------------------------------------------------------------

def test_action_result_success_minimal() -> None:
    """A successful result needs only the success flag."""
    result = ActionResult(success=True)
    assert result.success is True
    assert result.message == ""
    assert result.new_state is None


def test_action_result_failure_with_message() -> None:
    """A failure carries an explanatory message (e.g. a rule violation)."""
    result = ActionResult(success=False, message="You only have 10 gold.")
    assert result.success is False
    assert "10 gold" in result.message


def test_action_result_can_carry_new_state() -> None:
    """A result can carry the resulting GameState the action produced."""
    state = GameState(player=Player(name="Aria", gold=5))
    result = ActionResult(success=True, message="Bought a torch.", new_state=state)
    assert result.new_state.player.gold == 5


def test_action_result_requires_success_flag() -> None:
    """`success` has no default — omitting it is a validation error."""
    with pytest.raises(ValidationError):
        ActionResult(message="no success flag given")
