"""Dice rolling — deterministic domain logic (Milestone 2).

The whole point of this module: a dice result must come from real randomness
with validated bounds, NOT from the language model inventing a number. The agent
decides *when* to roll; this code decides *what* the roll is. That separation —
letting the model orchestrate but forcing exact/verifiable outcomes into tested
Python — is the core lesson of Milestone 2 and the pattern we carry to TestOps AI.

Pure Python, no SDK. Fully unit-testable without an API key.
"""

from __future__ import annotations

import random

# Dice bounds are a business rule, so they live here as named constants — not
# buried in an agent prompt where they couldn't be tested or enforced.
MIN_SIDES = 2
MAX_SIDES = 100


class InvalidDiceError(ValueError):
    """Raised when a dice roll is requested with an out-of-range side count."""


def roll_dice(sides: int, *, rng: random.Random | None = None) -> int:
    """Roll a single dice with `sides` faces and return a value in [1, sides].

    Args:
        sides: Number of faces. Must be an integer in [MIN_SIDES, MAX_SIDES].
        rng: Optional random source. Injecting a seeded `random.Random` makes
            rolls reproducible in tests — real randomness in play, deterministic
            randomness under test. (Observability + reproducibility.)

    Raises:
        InvalidDiceError: If `sides` is not an int in range. Failing loudly here
            means an impossible roll can never silently produce a bogus result.
    """
    # `bool` is a subclass of `int`; reject it explicitly so roll_dice(True)
    # doesn't sneak through as sides=1.
    if isinstance(sides, bool) or not isinstance(sides, int):
        raise InvalidDiceError(f"sides must be an integer, got {type(sides).__name__}")
    if sides < MIN_SIDES or sides > MAX_SIDES:
        raise InvalidDiceError(
            f"sides must be between {MIN_SIDES} and {MAX_SIDES}, got {sides}"
        )

    source = rng or random
    return source.randint(1, sides)
