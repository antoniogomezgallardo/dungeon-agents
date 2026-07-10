"""Tests for the dice domain logic (Milestone 2).

Deterministic, no API key, no SDK. Covers the happy path, the boundaries, and
every invalid-input branch — because "the agent must never invent dice results"
is only trustworthy if the rules are actually enforced and tested.
"""

from __future__ import annotations

import random

import pytest

from dungeon_agents.domain.dice import (
    MAX_SIDES,
    MIN_SIDES,
    InvalidDiceError,
    roll_dice,
)


def test_roll_is_within_bounds() -> None:
    """A roll always lands in [1, sides] across many samples."""
    for _ in range(1000):
        value = roll_dice(20)
        assert 1 <= value <= 20


def test_roll_is_reproducible_with_seeded_rng() -> None:
    """Injecting a seeded RNG makes the exact result reproducible."""
    a = roll_dice(100, rng=random.Random(42))
    b = roll_dice(100, rng=random.Random(42))
    assert a == b  # same seed -> same roll: deterministic under test


def test_min_and_max_sides_are_allowed() -> None:
    """The boundary values (2 and 100) are valid."""
    assert 1 <= roll_dice(MIN_SIDES) <= MIN_SIDES
    assert 1 <= roll_dice(MAX_SIDES) <= MAX_SIDES


@pytest.mark.parametrize("bad_sides", [1, 0, -5, MAX_SIDES + 1, 1000])
def test_out_of_range_sides_are_rejected(bad_sides: int) -> None:
    """Side counts outside [2, 100] raise InvalidDiceError."""
    with pytest.raises(InvalidDiceError):
        roll_dice(bad_sides)


@pytest.mark.parametrize("bad_type", [2.0, "20", None, True])
def test_non_integer_sides_are_rejected(bad_type: object) -> None:
    """Non-integer (incl. bool) side counts raise InvalidDiceError."""
    with pytest.raises(InvalidDiceError):
        roll_dice(bad_type)  # type: ignore[arg-type]
