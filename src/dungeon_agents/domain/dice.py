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


# --- Skill checks: a die roll that is TIED to a deterministic consequence (M6) -
#
# A bare `roll_dice` produces a number, but nothing decides what the number
# *means* — the model was free to interpret a 14 as success or failure at whim,
# so the die had no mechanical weight. A skill check fixes that: the code compares
# the roll against a difficulty threshold and DECIDES success or failure. The
# model may judge *how hard* something is (subjective, fine for an LLM); the code
# decides *whether it succeeds* (deterministic). Same lesson as the rules: the
# outcome lives in tested Python, not in the narrator's discretion.

CHECK_DIE = 20  # skill checks always roll 1d20, the classic RPG resolution die.

# Named difficulty levels -> the minimum d20 roll needed to succeed. Kept as a
# named mapping (not magic numbers scattered around) so the thresholds are
# testable, reusable, and easy to tune in one place.
DIFFICULTY_THRESHOLDS = {
    "trivial": 3,
    "easy": 5,
    "moderate": 10,
    "hard": 15,
    "very_hard": 18,
}
DEFAULT_DIFFICULTY = "moderate"


class CheckResult:
    """The outcome of a skill check — a small, explicit result object.

    Carries everything needed to narrate and verify the check: whether it
    succeeded, the die roll, the difficulty name, and the threshold it had to
    meet. Plain attributes (not a dataclass) to keep this module dependency-free.
    """

    def __init__(self, *, success: bool, roll: int, difficulty: str, threshold: int) -> None:
        self.success = success
        self.roll = roll
        self.difficulty = difficulty
        self.threshold = threshold

    def __repr__(self) -> str:  # helps test failure messages read clearly
        return (
            f"CheckResult(success={self.success}, roll={self.roll}, "
            f"difficulty={self.difficulty!r}, threshold={self.threshold})"
        )


class InvalidDifficultyError(ValueError):
    """Raised when a skill check is requested with an unknown difficulty name."""


def resolve_check(
    difficulty: str = DEFAULT_DIFFICULTY, *, rng: random.Random | None = None
) -> CheckResult:
    """Roll 1d20 against a named difficulty and DECIDE success in code.

    The roll succeeds when it meets or exceeds the difficulty's threshold. This is
    the deterministic heart of the mechanic: given the same roll and difficulty,
    the outcome is always the same — the narrator cannot overrule it.

    Args:
        difficulty: A named level from DIFFICULTY_THRESHOLDS (e.g. "moderate").
        rng: Optional seeded random source for reproducible checks under test.

    Raises:
        InvalidDifficultyError: If `difficulty` is not a known level — failing
            loudly rather than silently guessing a threshold.
    """
    key = difficulty.strip().lower()
    if key not in DIFFICULTY_THRESHOLDS:
        known = ", ".join(sorted(DIFFICULTY_THRESHOLDS))
        raise InvalidDifficultyError(
            f"unknown difficulty {difficulty!r}; expected one of: {known}"
        )

    threshold = DIFFICULTY_THRESHOLDS[key]
    roll = roll_dice(CHECK_DIE, rng=rng)
    return CheckResult(
        success=roll >= threshold, roll=roll, difficulty=key, threshold=threshold
    )
