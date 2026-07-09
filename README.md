# Dungeon Agents

A small console fantasy RPG driven by AI agents.

> **This is a learning project, not a game product.** Its real purpose is to
> practice designing, coding, testing, observing, and evolving AI agents in
> Python — patterns that will later migrate into a QA/Testing product,
> **TestOps AI**. The RPG is the pretext; testability and clarity are the goal.

## Current milestone: **M1 — Single Game Master agent**

A terminal loop where you type an action and a single Game Master agent replies
with a short scene, always ending with 2–3 choices. No persistence, no tools,
no multi-agent setup yet — those arrive in later milestones.

## Tech stack

- Python 3.11+ (developed on 3.12)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) — agent runtime
- **Model provider: Anthropic (Claude) by default, or OpenAI** — selectable via
  `DUNGEON_PROVIDER`. Anthropic is routed through the SDK's LiteLLM adapter, so
  the game logic is identical regardless of vendor.
- Pydantic — models & validation (from M3)
- pytest — tests
- python-dotenv — environment variables
- Rich — console output

### Choosing a provider

| `DUNGEON_PROVIDER` | Key env var         | Default model (cheapest for that vendor)        |
|--------------------|---------------------|-------------------------------------------------|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | `claude-haiku-4-5` — $1 / $5 per 1M tokens      |
| `openai`           | `OPENAI_API_KEY`    | `gpt-4o-mini`                                   |

Override the model for either with `DUNGEON_MODEL`. Get an Anthropic key at
<https://console.anthropic.com/>.

## Setup

A virtual environment keeps the project's dependencies isolated from your
system Python and from other projects — install the right versions here, and
they never interfere with anything else.

```bash
# 1. Create a virtual environment
python -m venv .venv

# 2. Activate it
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
```

> **Windows PowerShell one-time gotcha:** if activation is blocked, run
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` once,
> then try again.

```bash
# 3. Install the project and all dependencies (including dev tools like pytest)
pip install -e ".[dev]"

# 4. Configure your API key
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux
# then edit .env: keep DUNGEON_PROVIDER=anthropic and set ANTHROPIC_API_KEY
# (or set DUNGEON_PROVIDER=openai and OPENAI_API_KEY)
```

The `.venv/` directory is listed in `.gitignore` and is never committed.

## Run

```bash
# Either the console script:
dungeon-agents

# ...or the module:
python -m dungeon_agents.main
```

Type an action and press Enter. Type `exit` or `quit` (or press Ctrl+C) to
leave. Without the API key for your selected provider, the app prints a friendly
message and exits cleanly instead of crashing.

**First launch takes ~20 seconds** — this is normal. The OpenAI Agents SDK and
the LiteLLM adapter are heavy to import; the app shows a "Loading the game
engine…" spinner while they load. Subsequent launches in the same session are
instant.

## Tests

Deterministic tests run **without an API key** (and without a real model call):

```bash
python -m pytest -m "not llm"     # deterministic tests only (default in M1)
python -m pytest                  # everything
```

`pytest` is included in the `[dev]` extra installed in the Setup step above —
no separate install needed.

- **Deterministic tests** (no `llm` marker): imports, config, agent contract.
  These are the CI-safe, reproducible checks.
- **LLM tests** (`@pytest.mark.llm`): make real model calls. None exist yet;
  they arrive in Milestone 7 and stay separate from the deterministic suite.

## Project structure (M1)

```text
dungeon-agents/
  pyproject.toml
  .env.example
  src/dungeon_agents/
    config.py            # the ONLY place env vars are read
    main.py              # console loop + I/O
    agents/game_master.py# the single Game Master agent + its instructions
  tests/
    test_smoke.py        # runs with no API key
```

The structure grows one milestone at a time — files appear when their milestone
needs them, rather than being scaffolded empty up front.

## Learning documents

Because this is an educational project, each milestone has a **deep-dive
document** explaining what was built and *why* — see
[docs/milestones/](docs/milestones/). Start with
[Milestone 1](docs/milestones/milestone-01-game-master.md).

## Roadmap

1. **Single Game Master agent** ← *you are here*
2. Deterministic tools (`roll_dice`, load/save state)
3. Pydantic domain models (`Player`, `GameState`, `InventoryItem`, `Quest`, `ActionResult`)
4. Inventory & game rules
5. Multi-agent (Game Master, Rules Referee, Inventory Keeper, Lore Keeper, Critic)
6. Guardrails & safety constraints
7. Evaluation & tests
8. Bridge to QA/TestOps AI (`docs/qa_migration_notes.md`)
