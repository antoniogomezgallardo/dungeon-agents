# Dungeon Agents

A small console fantasy RPG driven by AI agents.

> **This is a learning project, not a game product.** Its real purpose is to
> practice designing, coding, testing, observing, and evolving AI agents in
> Python — patterns that will later migrate into a QA/Testing product,
> **TestOps AI**. The RPG is the pretext; testability and clarity are the goal.

## Current milestone: **M3 — Domain models**

Five Pydantic domain models now define the validated shape of the game state:
**`InventoryItem`**, **`Player`** (hp clamped to `[0, MAX_HP]`, gold non-negative),
**`Quest`** (data only; rules come in M4), **`GameState`** (the container; nested
validation cascades through the whole tree so nothing malformed can be built
silently), and **`ActionResult`** (the explicit return type for M4 rules —
`success` is required with no default). Two new persistence functions,
`save_state` / `load_state`, serialize and validate against the schema; loading a
file that violates the `GameState` schema raises `StateError` immediately. The M2
raw-JSON tools are kept intact so the existing agent behavior is unchanged.
The deterministic test suite is now **49 tests**, all passing without an API key.

**M2 — Deterministic tools (done).** `roll_dice` (validated, reproducible dice
rolls from Python — never invented by the model), `save_game_state`, and
`load_game_state` (bounded, JSON-validated persistence in `data/`). Domain layer
(`domain/`) and tools layer (`tools/`) introduced. SDK hooks surface each tool
call as a dim `[tool] roll_dice -> ...` line in the console. 26 deterministic
tests.

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

The game is **free-text**: type an action in your own words (`I search the room`,
`I attack the goblin`) *or* a numbered choice the Game Master offers — both work.
A brief help panel appears at startup. Type `help` at any time to see it again
(no game turn is consumed). Type `exit` or `quit` (or press Ctrl+C) to leave.

Meta-commands: `help`, `save`, `load`, `exit`.

Without the API key for your selected provider, the app prints a friendly
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

- **Deterministic tests** (no `llm` marker): imports, config, agent contract,
  dice logic, and state persistence. These are the CI-safe, reproducible checks.
- **LLM tests** (`@pytest.mark.llm`): make real model calls. None exist yet;
  they arrive in Milestone 7 and stay separate from the deterministic suite.

## Project structure (M3)

```text
dungeon-agents/
  pyproject.toml
  .env.example
  data/                  # git-ignored; holds game_state.json when saved
  src/dungeon_agents/
    config.py            # the ONLY place env vars are read
    main.py              # console loop + I/O
    domain/              # pure Python, zero SDK — testable business logic
      models.py          # 5 Pydantic models: InventoryItem, Player, Quest, GameState, ActionResult
      dice.py            # roll_dice(), InvalidDiceError, MIN/MAX_SIDES
      state.py           # save_game_state/load_game_state (M2 raw-JSON) +
                         # save_state/load_state (M3 validated) + StateError
    tools/               # thin @function_tool wrappers; one of two SDK-touching layers
      game_tools.py      # roll_dice, save_game_state, load_game_state tools
    agents/
      game_master.py     # Game Master agent + GAME_MASTER_INSTRUCTIONS constant
  tests/
    test_smoke.py        # 8 tests  — imports, config, provider, agent contract
    test_dice.py         # 12 tests — dice domain logic
    test_state.py        # 9 tests  — state persistence (6 M2 + 3 M3 validated)
    test_models.py       # 20 tests — Pydantic model validation
```

The structure grows one milestone at a time — files appear when their milestone
needs them, rather than being scaffolded empty up front.

## Learning documents

Because this is an educational project, each milestone has a **deep-dive
document** explaining what was built and *why* — see
[docs/milestones/](docs/milestones/). Start with
[Milestone 1](docs/milestones/milestone-01-game-master.md).

## Roadmap

1. **Single Game Master agent** ✅ done
2. **Deterministic tools** (`roll_dice`, load/save state) ✅ done
3. **Pydantic domain models** (`Player`, `GameState`, `InventoryItem`, `Quest`, `ActionResult`) ← *you are here*
4. Inventory & game rules
5. Multi-agent (Game Master, Rules Referee, Inventory Keeper, Lore Keeper, Critic)
6. Guardrails & safety constraints
7. Evaluation & tests
8. Bridge to QA/TestOps AI (`docs/qa_migration_notes.md`)
