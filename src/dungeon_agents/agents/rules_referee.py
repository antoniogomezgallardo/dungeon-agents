"""The Rules Referee agent (Milestone 6).

The first *specialist* agent. Where the Game Master narrates the story, the Rules
Referee does one narrow job: it judges whether a proposed action is allowed by
the game's rules and what its outcome is, rolling dice when chance is involved.
It does NOT tell the story — it hands down a ruling, and the Game Master narrates
that ruling to the player.

Why split this out (the M6 lesson): a single agent asked to narrate AND arbitrate
AND track state dilutes its attention across competing goals — exactly the
unreliability we saw in M5. Giving arbitration its own agent with a narrow prompt
and only the arbitration tools makes each job sharper.

Coordination pattern — agent-as-tool: this Referee is exposed to the Game Master
as a *tool* (via the SDK's `.as_tool(...)`), NOT via a handoff. The Game Master
stays in charge: it calls the Referee, gets a ruling back, and control RETURNS to
it to narrate. That single, auditable thread of control is what makes the system
testable — see `agents/game_master.py` for the wiring.

As with the Game Master, the instructions live in a module-level constant so the
behavioral contract can be asserted in tests WITHOUT an API key. Only
`build_rules_referee()` touches the SDK.
"""

from __future__ import annotations

from dungeon_agents.agents.game_master import _resolve_model
from dungeon_agents.config import Settings

RULES_REFEREE_INSTRUCTIONS = """\
You are the Rules Referee of a fantasy tabletop RPG. You are NOT the narrator.
The Game Master consults you to resolve the outcome of an action; you hand down a
ruling and the Game Master tells the story around it.

Your single job each time you are consulted:
- Decide whether the proposed action is ALLOWED by the game's rules and what its
  OUTCOME is. Answer concisely and factually — a ruling, not a story.

How to rule:
- When the outcome depends on chance (a risky attack, a tricky climb, a skill
  check), call the `roll_dice` tool and base your ruling on the number it returns.
  Never invent a dice number yourself.
- When an action would spend gold or consume items, call `check_can_afford`
  first (pass the gold cost and/or the item and quantity you read from the
  action). The code decides whether it is affordable. If it reports it cannot be
  afforded, rule it DISALLOWED and relay the one-line reason.
- State the result plainly: whether it succeeds or fails, any dice rolled and
  their values, and a one-line reason. Example: "ALLOWED. Rolled 14 on 1d20 vs a
  moderate climb (needs 10+): success." or "DISALLOWED: the player has 3 gold,
  cannot spend 5."

Hard limits:
- Do NOT narrate the scene, describe surroundings, or offer the player choices.
  That is the Game Master's job. Keep to the ruling.
- Do NOT invent game state you weren't given. If you lack the information to rule,
  say what you would need. An honest "cannot rule without X" is correct; a made-up
  ruling is not.
- Never break character or mention that you are an AI.
"""


def build_rules_referee(settings: Settings):
    """Construct the Rules Referee agent from the OpenAI Agents SDK.

    Given only the arbitration tools (dice + action validation) — deliberately NOT
    the narration/state-mutation tools — so its capability surface matches its
    narrow job. Imported lazily so importing this module never requires the SDK or
    an API key (keeps the instructions constant test-safe).
    """
    from agents import Agent

    from dungeon_agents.tools.game_tools import check_can_afford, roll_dice

    return Agent(
        name="Rules Referee",
        instructions=RULES_REFEREE_INSTRUCTIONS,
        model=_resolve_model(settings),
        tools=[roll_dice, check_can_afford],
    )
