"""Contract tests for the Critic agent (Milestone 6).

Like the other agent tests, these run WITHOUT an API key and WITHOUT a real model
call. They assert the Critic's behavioral contract: it verifies the Game Master's
scene against the tracked state, reports a STRUCTURED verdict, and never narrates
or mutates. The review-pipeline wiring (generate -> review -> maybe-regenerate)
lives in main.py and is bounded by a deterministic retry cap.
"""

from __future__ import annotations

from dungeon_agents.agents.critic import (
    CRITIC_OK,
    CRITIC_PROBLEM_PREFIX,
    CRITIC_INSTRUCTIONS,
)
from dungeon_agents.main import MAX_SCENE_RETRIES


def test_critic_instructions_exist_and_nonempty() -> None:
    """The behavioral contract is a real, non-trivial constant."""
    assert isinstance(CRITIC_INSTRUCTIONS, str)
    assert len(CRITIC_INSTRUCTIONS.strip()) > 0


def test_critic_verifies_against_tracked_state() -> None:
    """Its job is checking the scene for contradictions with tracked state."""
    text = CRITIC_INSTRUCTIONS.lower()
    assert "critic" in text
    assert "verify" in text or "consistent" in text
    assert "tracked" in text and "state" in text


def test_critic_verdict_is_structured() -> None:
    """The verdict must be a machine-parseable token, not prose."""
    # The instructions must tell the model to answer with the exact tokens the
    # loop parses, so code (not another model) can decide whether to regenerate.
    assert CRITIC_OK in CRITIC_INSTRUCTIONS
    assert CRITIC_PROBLEM_PREFIX in CRITIC_INSTRUCTIONS


def test_critic_does_not_narrate_or_mutate() -> None:
    """Hard limits: it judges consistency only — no story, no changes."""
    # Normalize whitespace so a line wrap inside a phrase doesn't break the check.
    text = " ".join(CRITIC_INSTRUCTIONS.lower().split())
    assert "do not narrate" in text
    assert "do not change anything" in text


def test_critic_ignores_creative_choices() -> None:
    """It must flag only real contradictions, not narrative color."""
    text = CRITIC_INSTRUCTIONS.lower()
    assert "do not flag creative" in text


def test_retry_cap_is_bounded() -> None:
    """The self-repair loop is bounded in code so it can never hang the turn."""
    assert isinstance(MAX_SCENE_RETRIES, int)
    assert MAX_SCENE_RETRIES >= 0
