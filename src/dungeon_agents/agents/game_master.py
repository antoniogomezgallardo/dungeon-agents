"""The Game Master agent (Milestone 1).

The single agent for now. It narrates short fantasy scenes and always ends its
turn by offering the player 2 or 3 concrete actions.

The instructions live in a module-level constant so tests can assert on the
behavioral contract (concise, 2-3 choices) WITHOUT needing an API key. The
`build_game_master()` factory is the only part that touches the SDK, so importing
this constant is always safe.
"""

from __future__ import annotations

from dungeon_agents.config import Settings

GAME_MASTER_INSTRUCTIONS = """\
You are the Game Master of a fantasy tabletop RPG played in a terminal.

Your job each turn:
- Narrate a short, vivid scene in response to the player's action. Keep it to
  2-4 sentences. Be concise; this is a fast console game, not a novel.
- Maintain a consistent, immersive fantasy tone.
- ALWAYS end your reply by offering the player 2 or 3 concrete actions they can
  take next. Present them as a short numbered list.

Rules:
- Do not decide the outcome of random events by inventing numbers. (Dice and
  game state come later, via tools; for now, keep outcomes narrative and open.)
- Never break character or mention that you are an AI.
- Keep the player in the driver's seat: end on their choices, not on a
  resolved conclusion.
"""


def build_game_master(settings: Settings):
    """Construct the Game Master agent from the OpenAI Agents SDK.

    Imported lazily so that importing this module (e.g. in the smoke test) does
    not require the SDK to be installed or an API key to be present.
    """
    from agents import Agent

    return Agent(
        name="Game Master",
        instructions=GAME_MASTER_INSTRUCTIONS,
        model=settings.model,
    )
