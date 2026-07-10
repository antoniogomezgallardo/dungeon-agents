# CLAUDE.md — Dungeon Agents

Notes for future Claude Code sessions working in this repo.

## What this is

A learning project (NOT a production game). A console fantasy RPG used to
practice agentic AI patterns in Python, with the explicit goal of later
migrating the same patterns into a QA/Testing product, **TestOps AI**. Optimize
for testability, reproducibility, safe failure, and clarity — not for game
features.

## Build discipline

- Work **one milestone at a time**. Never scaffold future milestones' files.
- Before proposing a change, state: (1) what changes, (2) why it matters,
  (3) how to test it, (4) risk/tradeoff.
- Explain important design decisions briefly before implementing.
- Keep functions small, names explicit, type hints on. Comment only for intent.
- Business rules belong in deterministic Python (`domain/`), never hidden in
  agent prompts. Keep agent instructions short and specific.
- Update this file and the README after each milestone.
- **Write a deep-dive learning doc per milestone** in `docs/milestones/`
  (e.g. `milestone-02-tools.md`) following the fixed 8-section structure in
  `docs/milestones/README.md`. Re-read the source before writing so the doc
  matches the code. Update the index table there. Do this before calling a
  milestone done.

## Architecture rules

- **`config.py` is the only module that reads environment variables.**
- **The domain layer (`domain/`) must have zero SDK dependency** — pure Python,
  unit-testable without an API key. Introduced in M2; the rule is established.
  Only `agents/` and `tools/` touch the OpenAI Agents SDK (import name: `agents`).
- Agent definitions live in `agents/*.py`; console I/O lives in `main.py`.
- Keep agent instructions as module-level constants so their behavioral
  contract can be asserted in tests without an API key.

## Testing

- Deterministic tests must pass with **no API key** and are the default suite.
- LLM tests use `@pytest.mark.llm` and are kept separate.
- Run: `python -m pytest -m "not llm"` (deterministic) or `python -m pytest`.

## Runtime decision

OpenAI Agents SDK (chosen 2026-07-08). **Provider is selectable** via
`DUNGEON_PROVIDER` (added 2026-07-09): `anthropic` (default) or `openai`.
- `anthropic` → `ANTHROPIC_API_KEY`, default model `claude-haiku-4-5`, routed
  through the SDK's LiteLLM adapter (`agents.extensions.models.litellm_model`,
  model string `anthropic/<id>`). Needs the `openai-agents[litellm]` extra.
- `openai` → `OPENAI_API_KEY`, default model `gpt-4o-mini`, native SDK path.
Override either default with `DUNGEON_MODEL`. Only `config.py` reads env vars;
only `game_master.py` touches the SDK/LiteLLM.

**Dependency constraint (2026-07-10):** `openai` is pinned to `>=2.36,<2.37`
because `openai 2.37+` made `cache_write_tokens` required on
`InputTokensDetails`, which `litellm 1.91.x` does not set — causing a pydantic
`ValidationError` on every model call through the LiteLLM adapter. Revisit when
litellm ships support for the newer token schema.

**First-run startup delay:** the SDK and LiteLLM adapter take ~20 seconds to
import on first launch. `main.py` shows a `console.status` spinner ("Loading the
game engine…") during this window so it doesn't look frozen.

## Development environment

Use a virtual environment (`.venv/`). The blessed workflow:

```bash
python -m venv .venv
# Windows PowerShell (one-time: Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned)
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

`.venv/` is in `.gitignore` and is never committed. `pytest` comes from the
`[dev]` extra — no separate install step.

## Milestone status

- **M1 — Single Game Master agent: DONE.** Console loop, `exit`/`quit`/Ctrl+C
  to quit, GM ends turns with 2–3 choices, graceful no-key message, 8 smoke
  tests passing with no API key.
- **M2 — Deterministic tools: DONE.** `domain/` layer (pure Python, zero SDK):
  `dice.py` (`roll_dice`, `InvalidDiceError`, seeded-rng injection) and
  `state.py` (`save_game_state`, `load_game_state`, `StateError`, bounded writes,
  JSON validation, `tmp_path` injection). `tools/` layer: thin `@function_tool`
  wrappers for all three. Game Master wired with `tools=[roll_dice,
  save_game_state, load_game_state]`; instructions updated to call `roll_dice`
  for chance. `main.py`: SDK hooks (`RunHooks` subclass) print dim `[tool]`
  lines for each tool call (observability, not behavior change); startup help
  panel + `help`/`?`/`/help` meta-command (no game turn consumed); input prompt
  clarified to show free-text is allowed; all console output is ASCII-only for
  Windows `cp1252` portability. 26 deterministic tests passing with no API key
  (8 smoke + 12 dice + 6 state). Saved state lives in `data/` (git-ignored).
- M3–M8: not started. See README roadmap.
