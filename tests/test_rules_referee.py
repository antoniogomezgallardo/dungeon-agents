"""Contract tests for the Rules Referee agent (Milestone 6).

Like the Game Master smoke tests, these run WITHOUT an API key and WITHOUT a real
model call. They assert the Referee's behavioral contract lives in its
instructions constant, and that the Game Master is wired to consult it — the
agent-as-tool coordination pattern — at the level we can check without the SDK.
"""

from __future__ import annotations

from dungeon_agents.agents.game_master import GAME_MASTER_INSTRUCTIONS
from dungeon_agents.agents.rules_referee import RULES_REFEREE_INSTRUCTIONS


def test_referee_instructions_exist_and_nonempty() -> None:
    """The behavioral contract is a real, non-trivial constant."""
    assert isinstance(RULES_REFEREE_INSTRUCTIONS, str)
    assert len(RULES_REFEREE_INSTRUCTIONS.strip()) > 0


def test_referee_is_an_arbiter_not_a_narrator() -> None:
    """The Referee rules on outcomes; it explicitly does not tell the story."""
    text = RULES_REFEREE_INSTRUCTIONS.lower()
    assert "referee" in text
    assert "ruling" in text
    # Its hard limit: it must NOT narrate — that's the Game Master's job.
    assert "not narrate" in text or "do not narrate" in text


def test_referee_uses_skill_check_for_uncertain_outcomes() -> None:
    """Uncertain outcomes are decided by skill_check (roll vs difficulty in code)."""
    text = RULES_REFEREE_INSTRUCTIONS.lower()
    assert "skill_check" in text
    assert "cannot overrule" in text


def test_referee_persists_resource_consequences() -> None:
    """The Referee is told to persist gold/HP changes it rules on."""
    text = RULES_REFEREE_INSTRUCTIONS.lower()
    assert "earn_gold" in text and "spend_gold" in text
    assert "change_hp" in text
    # And the reason why: without persisting, changes are lost on reload.
    assert "lost on reload" in text


def test_referee_validates_resource_actions() -> None:
    """The Referee checks resource-spending actions before allowing them."""
    text = RULES_REFEREE_INSTRUCTIONS.lower()
    assert "check_can_afford" in text


def test_referee_fails_honestly_when_it_cannot_rule() -> None:
    """Honest-gap principle: an unknown must be admitted, never fabricated."""
    text = RULES_REFEREE_INSTRUCTIONS.lower()
    assert "do not invent" in text or "cannot rule" in text


def test_game_master_consults_the_referee() -> None:
    """The GM's contract now delegates contested outcomes to the referee tool.

    This is the agent-as-tool wiring visible at the instruction level: the Game
    Master is told to consult `rules_referee` rather than resolve chance itself.
    """
    text = GAME_MASTER_INSTRUCTIONS.lower()
    assert "rules_referee" in text
