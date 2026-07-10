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

Rules:
- Do not decide the outcome of random events by inventing numbers. When an
  action depends on chance, call the `roll_dice` tool and narrate the result it
  returns. Never make up a dice number yourself.
- You may use `save_game_state` to persist progress and `load_game_state` to
  resume a saved adventure.
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

    Imported lazily so that importing this module (e.g. in the smoke test) does
    not require the SDK to be installed or an API key to be present.
    """
    from agents import Agent, set_tracing_disabled

    # Imported here (not at module top) to keep the SDK out of the import path
    # for API-key-free tests. The tools themselves wrap pure domain functions.
    from dungeon_agents.tools.game_tools import (
        load_game_state,
        roll_dice,
        save_game_state,
    )

    # The SDK's tracing exports run traces to OpenAI's platform and require an
    # OPENAI_API_KEY. Our default provider is Anthropic, so tracing has nothing
    # to export and would log a confusing "OPENAI_API_KEY is not set, skipping
    # trace export" warning every turn. We don't use that dashboard here, so
    # disable tracing outright for a clean console.
    set_tracing_disabled(True)

    return Agent(
        name="Game Master",
        instructions=GAME_MASTER_INSTRUCTIONS,
        model=_resolve_model(settings),
        tools=[roll_dice, save_game_state, load_game_state],
    )
