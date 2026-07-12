"""The Critic agent (Milestone 6).

The fourth and final specialist — and the one that introduces a DIFFERENT
coordination pattern. The Rules Referee and Lore Keeper are agent-as-tool: the
Game Master calls them *during* its turn. The Critic runs *after* the Game Master
has produced a scene, reviewing it *before* the player sees it — a review pipeline
(see `main.py`, which orchestrates the generate -> review -> maybe-regenerate
loop). The pipeline step is deterministic code, so review is GUARANTEED to happen,
not left to the model's discretion. A verifier that only sometimes verifies is
worthless — the guarantee is the point.

The Critic is, in QA terms, a tester: an agent whose only job is to VERIFY another
agent's output against a source of truth. It checks the Game Master's narration
against the validated game state (passed in as hard data), not against its own
opinion — so it catches the narration claiming something the tracked state
contradicts (wrong HP, gold the player doesn't have, a place the state says they
left). This is the LLM-as-a-judge pattern and the foundation of Milestone 8's
evaluation work.

Structured verdict: the Critic must answer in a machine-parseable shape ("OK" or
"PROBLEM: <reason>") so the CODE — not another model call — decides whether to
regenerate. A structured contract between the verifier and the loop removes the
ambiguity a prose verdict would introduce.

As with the other agents, the instructions are a module-level constant so the
behavioral contract is testable WITHOUT an API key.
"""

from __future__ import annotations

from dungeon_agents.agents.game_master import _resolve_model
from dungeon_agents.config import Settings

# The exact tokens the loop looks for. Kept as constants so the contract between
# the Critic's output and main.py's parser is defined in one place and testable.
CRITIC_OK = "OK"
CRITIC_PROBLEM_PREFIX = "PROBLEM:"

CRITIC_INSTRUCTIONS = f"""\
You are the Critic of a fantasy tabletop RPG. You do NOT narrate and you do NOT
change anything. Your only job is to VERIFY the Game Master's latest scene against
the tracked, validated game state you are given, and report whether it is
consistent.

You will be given the current game state (the player's HP, gold, location, active
quest, and inventory) and the scene the Game Master just wrote. Check the scene
for CONTRADICTIONS with that state, such as:
- Claiming the player has, spends, or gains an amount of gold that disagrees with
  the tracked gold.
- Describing the player using or holding an item that is not in their inventory.
- Placing the player somewhere that contradicts the tracked location, or
  referring to a quest that contradicts the tracked active quest.
- Stating an HP/health outcome that contradicts the tracked HP (e.g. narrating the
  player as gravely wounded when HP is full, or fine when HP is 0).

Do NOT flag creative or narrative choices — only real contradictions with the
tracked state. Ambiguity or added color that does not conflict with the state is
fine; leave it alone.

Answer in EXACTLY one of these two forms, and nothing else:
- `{CRITIC_OK}` if the scene is consistent with the tracked state.
- `{CRITIC_PROBLEM_PREFIX} <one short sentence naming the specific contradiction>`
  if it is not.

Never break character or mention that you are an AI. Never narrate the story or
offer choices — you only judge consistency.
"""


def build_critic(settings: Settings):
    """Construct the Critic agent from the OpenAI Agents SDK.

    Given only a read-only inventory tool — it inspects and judges, it never
    mutates. Imported lazily so importing this module never requires the SDK or an
    API key (keeps the instructions constant test-safe).
    """
    from agents import Agent

    from dungeon_agents.tools.game_tools import get_inventory

    return Agent(
        name="Critic",
        instructions=CRITIC_INSTRUCTIONS,
        model=_resolve_model(settings),
        tools=[get_inventory],
    )
