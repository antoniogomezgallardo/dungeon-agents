"""Contract tests for the Lore Keeper agent (Milestone 6).

Like the Game Master and Rules Referee tests, these run WITHOUT an API key and
WITHOUT a real model call. They assert the Lore Keeper's behavioral contract
(keep the tracked world in sync; do not narrate or touch dice/resources) and that
the Game Master delegates world-state sync to it — the agent-as-tool pattern.
"""

from __future__ import annotations

from dungeon_agents.agents.game_master import GAME_MASTER_INSTRUCTIONS
from dungeon_agents.agents.lore_keeper import LORE_KEEPER_INSTRUCTIONS


def test_lore_keeper_instructions_exist_and_nonempty() -> None:
    """The behavioral contract is a real, non-trivial constant."""
    assert isinstance(LORE_KEEPER_INSTRUCTIONS, str)
    assert len(LORE_KEEPER_INSTRUCTIONS.strip()) > 0


def test_lore_keeper_owns_world_state_sync() -> None:
    """Its job is keeping location, quest, and summary in sync with the story."""
    text = LORE_KEEPER_INSTRUCTIONS.lower()
    assert "lore keeper" in text
    assert "set_location" in text
    assert "set_quest" in text
    assert "update_summary" in text


def test_lore_keeper_does_not_narrate_or_arbitrate() -> None:
    """Hard limits: it doesn't tell the story or touch dice/gold/HP/items."""
    text = LORE_KEEPER_INSTRUCTIONS.lower()
    assert "do not narrate" in text
    # It must not step on the Referee's job (dice / gold / HP).
    assert "do not roll dice" in text


def test_lore_keeper_fails_honestly_not_fabricating() -> None:
    """Honest-gap principle: don't invent a location/quest the story didn't set."""
    text = LORE_KEEPER_INSTRUCTIONS.lower()
    assert "not set yet" in text
    assert "don't invent" in text or "do not invent" in text


def test_game_master_delegates_world_sync_to_lore_keeper() -> None:
    """The GM's contract now routes world-state sync through the lore_keeper tool.

    Visible at the instruction level: the Game Master is told to consult
    `lore_keeper` rather than call set_location/set_quest itself.
    """
    text = GAME_MASTER_INSTRUCTIONS.lower()
    assert "lore_keeper" in text
    # The GM no longer manages these directly — it delegates them. (Compare on
    # whitespace-normalized text so a line wrap inside the phrase doesn't matter.)
    normalized = " ".join(text.split())
    assert "not update it yourself" in normalized
