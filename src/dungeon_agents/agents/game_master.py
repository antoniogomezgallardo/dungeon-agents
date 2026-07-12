"""The Game Master agent (Milestone 1).

The single agent for now. It narrates short fantasy scenes and always ends its
turn by offering the player 2 or 3 concrete actions.

The instructions live in a module-level constant so tests can assert on the
behavioral contract (concise, 2-3 choices) WITHOUT needing an API key. The
`build_game_master()` factory is the only part that touches the SDK, so importing
this constant is always safe.
"""

from __future__ import annotations

from dungeon_agents.config import PROVIDER_ANTHROPIC, Settings

GAME_MASTER_INSTRUCTIONS = """\
You are the Game Master of a fantasy tabletop RPG played in a terminal.

Your job each turn:
- Narrate a short, vivid scene in response to the player's action. Keep it to
  2-4 sentences. Be concise; this is a fast console game, not a novel.
- Maintain a consistent, immersive fantasy tone.
- ALWAYS end your reply by offering the player 2 or 3 concrete actions they can
  take next. Present them as a short numbered list.

Keep the tracked game state in sync with your story. The player can open a stats
screen that reads this tracked state, so it should match your narration.
- On the first scene of a new game, call `set_location` (the place you describe)
  and `set_quest` (the opening objective) so stats reflect the story.
- When the player travels to a new place, call `set_location` again; when they
  take on a new objective, call `set_quest` again.
- Prefer keeping these in sync as you go. (If a value hasn't been set yet, the
  player's stats simply show "not set yet" — an honest gap, never a wrong value.)

Rules:
- To resolve the OUTCOME of an action that is risky or depends on chance (an
  attack, a climb, a skill check), or that spends gold or uses items, consult the
  `rules_referee` tool. Describe the action to it; it returns a ruling (allowed or
  disallowed, any dice rolled, a one-line reason). Narrate the story around
  whatever it rules — the Referee decides the outcome, you tell the tale.
- The `rules_referee` handles dice and affordability checks for you, so for a
  contested outcome you do not roll dice or check resources yourself — ask the
  Referee and narrate its ruling. Never invent a dice number or overrule it.
- The game's rules are enforced by tools, not by you. Use them and narrate what
  they return; never let the player do something the rules forbid:
  - `get_inventory` to see what the player carries.
  - `add_item` / `remove_item` when the player gains or loses items. A player
    cannot lose an item they do not have — the tool will say so.
- When a rule tool reports a failure, explain it to the player in a friendly,
  in-character way rather than ignoring it.
- You may use `save_game` to persist progress and `load_game` to resume a saved
  adventure.
- After a story-significant moment (accepting or completing a quest, reaching a
  new place, meeting a key character, a major win or loss), call `update_summary`
  with a brief factual recap of what has happened so far, so the player can
  review it or resume later with proper context.
- Never break character or mention that you are an AI or that you are using tools.
- Keep the player in the driver's seat: end on their choices, not on a
  resolved conclusion.
"""


def _resolve_model(settings: Settings):
    """Return the model object/name for the configured provider.

    - OpenAI: pass the bare model name; the SDK's default OpenAI client handles it.
    - Anthropic: wrap the model in the SDK's LiteLLM adapter, which translates
      calls to the Anthropic API. Same Agent/Runner code path either way.

    Imported lazily so importing this module (e.g. in the smoke test) never
    requires the SDK, the litellm extra, or an API key.
    """
    if settings.provider == PROVIDER_ANTHROPIC:
        from agents.extensions.models.litellm_model import LitellmModel

        # LiteLLM identifies Anthropic models as "anthropic/<model-id>".
        return LitellmModel(model=f"anthropic/{settings.model}", api_key=settings.api_key)

    return settings.model


def build_game_master(settings: Settings):
    """Construct the Game Master agent from the OpenAI Agents SDK.

    From M6 the Game Master is an *orchestrator*: it narrates and, to resolve
    contested outcomes, it consults the Rules Referee — which is wired in below as
    a tool (the agent-as-tool coordination pattern). Imported lazily so that
    importing this module (e.g. in the smoke test) does not require the SDK to be
    installed or an API key to be present.
    """
    from agents import Agent, set_tracing_disabled

    # Built here (not module top) to keep the SDK out of the import path for
    # API-key-free tests. Deferred import to avoid a circular import: rules_referee
    # imports _resolve_model from this module.
    from dungeon_agents.agents.rules_referee import build_rules_referee

    # Imported here (not at module top) to keep the SDK out of the import path
    # for API-key-free tests. The tools themselves wrap pure domain functions.
    from dungeon_agents.tools.game_tools import (
        add_item,
        get_inventory,
        load_game,
        remove_item,
        save_game,
        set_location,
        set_quest,
        update_summary,
    )

    # The SDK's tracing exports run traces to OpenAI's platform and require an
    # OPENAI_API_KEY. Our default provider is Anthropic, so tracing has nothing
    # to export and would log a confusing "OPENAI_API_KEY is not set, skipping
    # trace export" warning every turn. We don't use that dashboard here, so
    # disable tracing outright for a clean console.
    set_tracing_disabled(True)

    # === The agent-as-tool coordination pattern (M6) ===
    # We build the Rules Referee as a full Agent, then expose it to the Game
    # Master as a single tool via `.as_tool(...)`. When the Game Master "calls"
    # rules_referee, the SDK runs the Referee agent to completion (it may roll
    # dice / validate internally) and returns its final ruling as the tool's
    # result. Crucially, control RETURNS to the Game Master afterwards — it stays
    # the orchestrator. This is what makes the flow a single, auditable thread
    # (contrast: a handoff would transfer control away and not return it).
    referee = build_rules_referee(settings)
    rules_referee_tool = referee.as_tool(
        tool_name="rules_referee",
        tool_description=(
            "Consult the Rules Referee to resolve the outcome of a risky or "
            "resource-spending action. Describe the action; it returns a ruling "
            "(allowed/disallowed, any dice rolled, a one-line reason)."
        ),
    )

    return Agent(
        name="Game Master",
        instructions=GAME_MASTER_INSTRUCTIONS,
        model=_resolve_model(settings),
        tools=[
            rules_referee_tool,  # <-- the Rules Referee agent, exposed as a tool
            save_game,
            load_game,
            get_inventory,
            add_item,
            remove_item,
            update_summary,
            set_location,
            set_quest,
        ],
    )
