"""Tests for end-of-game detection wired into the loop (M6 carryover).

Deterministic, no API key. `is_game_won` / `is_game_over` were written and tested
in M4 but never called; M6 wires them into `main.py` via `_check_end_of_game`,
which decides win/lose from the validated state — not the narration. These tests
inject a GameState directly (dependency injection) so they never touch disk or a
model.
"""

from __future__ import annotations

from dungeon_agents.domain.models import GameState, Player, Quest
from dungeon_agents.main import _check_end_of_game


def _state(**player_kwargs) -> GameState:
    return GameState(player=Player(name="Aria", **player_kwargs))


def test_game_continues_when_alive_and_quest_unfinished() -> None:
    """A healthy hero with an open quest keeps playing (None)."""
    state = _state(hp=50)
    state.active_quest = Quest(title="Find the relic")
    assert _check_end_of_game(state) is None


def test_defeat_when_hp_zero() -> None:
    """HP at 0 ends the game as a loss."""
    assert _check_end_of_game(_state(hp=0)) == "lost"


def test_victory_when_quest_completed() -> None:
    """A completed active quest ends the game as a win."""
    state = _state(hp=30)
    state.active_quest = Quest(title="Slay the dragon", completed=True)
    assert _check_end_of_game(state) == "won"


def test_defeat_takes_precedence_over_victory() -> None:
    """A hero who fell (HP 0) does not also win, even with a completed quest."""
    state = _state(hp=0)
    state.active_quest = Quest(title="Slay the dragon", completed=True)
    assert _check_end_of_game(state) == "lost"


def test_full_hp_no_quest_continues() -> None:
    """A brand-new hero (full HP, no quest yet) is neither won nor lost."""
    assert _check_end_of_game(_state()) is None
