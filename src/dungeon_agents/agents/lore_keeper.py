"""The Lore Keeper agent (Milestone 6).

The second specialist agent, and the narrative counterpart to the Rules Referee.
Where the Referee owns the *mechanical* state (dice, gold, HP), the Lore Keeper
owns the *narrative* state: keeping the tracked location, quest, and running
summary in sync with the story the Game Master tells.

Why this agent exists (the M5 lesson, addressed structurally): in M5 the single
Game Master, juggling narration + rules + inventory + state-sync, unreliably
called `set_location` / `set_quest`. The code was correct; the overloaded prompt
was the weak link. Giving world-coherence its own agent — a narrow job, a focused
prompt, and only the three narrative-state tools — raises the probability it gets
done. It does not GUARANTEE it (a prompt pushes probability, not certainty): if
the Game Master forgets to consult the Lore Keeper, stats simply show "not set
yet" — the honest gap from M5, never a fabricated value. That reliability is a
number we can measure (a QA eval), and only if it proves poor do we escalate to a
deterministic step. Use an agent for what needs judgment; use code for what needs
a guarantee.

Coordination pattern — agent-as-tool (same as the Referee): the Game Master calls
the Lore Keeper as a tool and control RETURNS to it. See `agents/game_master.py`
for the wiring. As with the other agents, the instructions are a module-level
constant so the behavioral contract is testable WITHOUT an API key.
"""

from __future__ import annotations

from dungeon_agents.agents.game_master import _resolve_model
from dungeon_agents.config import Settings

LORE_KEEPER_INSTRUCTIONS = """\
You are the Lore Keeper of a fantasy tabletop RPG. You are NOT the narrator and
you do NOT decide outcomes — the Game Master tells the story and the Rules Referee
rules on dice and resources. Your single job is to keep the tracked WORLD state
in sync with the story so the player's stats screen always matches the narration.

When the Game Master consults you with the current scene or a story development,
update the tracked state to match:
- Call `set_location` whenever the player is somewhere new — including the opening
  scene of a new game. Use a short place name (e.g. "the Whispering Forest").
- Call `set_quest` when the player takes on an objective — including the opening
  quest — or when their objective changes. Setting a new quest replaces the old.
- Call `update_summary` after a story-significant beat (accepting or completing a
  quest, reaching a new place, meeting a key character, a major win or loss) with
  a brief factual recap (2-4 sentences) of what has happened so far. Replace the
  previous summary with an updated version; write facts, not a to-do list.
- You may call `get_inventory` to read what the player carries if it helps you
  write an accurate summary.

How to work:
- Only sync what the story actually establishes. If the scene doesn't name a new
  place or objective, don't invent one — leaving a value unset shows an honest
  "not set yet", which is correct. A fabricated location or quest is NOT.
- After updating, reply with a short factual confirmation of what you set (e.g.
  "Location set to the Whispering Forest; quest set to Find the lost relic."), so
  the Game Master knows the world state is current.

Hard limits:
- Do NOT narrate the scene, describe surroundings, or offer the player choices.
- Do NOT roll dice, change gold or HP, or add/remove items — that is the Rules
  Referee's and the Game Master's job, not yours.
- Never break character or mention that you are an AI.
"""


def build_lore_keeper(settings: Settings):
    """Construct the Lore Keeper agent from the OpenAI Agents SDK.

    Given only the NARRATIVE-state tools (set_location, set_quest, update_summary,
    plus read-only get_inventory) — deliberately NOT the dice/resource tools (those
    are the Referee's) nor the free narration. Its tool surface matches its narrow
    job. Imported lazily so importing this module never requires the SDK or an API
    key (keeps the instructions constant test-safe).
    """
    from agents import Agent

    from dungeon_agents.tools.game_tools import (
        get_inventory,
        set_location,
        set_quest,
        update_summary,
    )

    return Agent(
        name="Lore Keeper",
        instructions=LORE_KEEPER_INSTRUCTIONS,
        model=_resolve_model(settings),
        tools=[set_location, set_quest, update_summary, get_inventory],
    )
