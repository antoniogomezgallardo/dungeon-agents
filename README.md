# Dungeon Agents

A small console fantasy RPG driven by AI agents.

> **This is a learning project, not a game product.** Its real purpose is to
> practice designing, coding, testing, observing, and evolving AI agents in
> Python — patterns that will later migrate into a QA/Testing product,
> **TestOps AI**. The RPG is the pretext; testability and clarity are the goal.

## Current milestone: **M4 — Inventory & game rules**

Nine deterministic rule functions in `domain/rules.py` give the game its first
enforced mechanics: **`add_item`** / **`remove_item`** (can't use an item you
don't have), **`spend_gold`** / **`earn_gold`** (can't spend more than you carry),
**`change_hp`** (HP clamped to `[0, max_hp]` — damage and healing both safe),
**`complete_quest`** / **`is_game_won`** / **`is_game_over`** (win by completing
the active quest; lose when HP hits 0). Four new agent tools (`get_inventory`,
`add_item`, `remove_item`, `validate_action`) follow a **load-modify-save** pattern:
load current state, apply the rule, persist the new state on success, return the
rule's message for the GM to narrate. All rules are pure functions (no mutation,
no SDK), so each is trivially tested in isolation. The deterministic test suite is
now **78 tests**, all passing without an API key.

**M3 — Domain models (done).** Five Pydantic models (`InventoryItem`, `Player`,
`Quest`, `GameState`, `ActionResult`) and two validated persistence functions
(`save_state` / `load_state`). Invalid state cannot be built, saved, or loaded
silently. 49 deterministic tests.

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

- **Deterministic tests** (no `llm` marker): **78 tests** across five files, all
  passing without an API key:
  - `test_smoke.py` — 8 tests: imports, config, provider selection, agent contract
  - `test_dice.py` — 12 tests: dice domain logic, seeded RNG, bounds
  - `test_state.py` — 9 tests: raw-JSON persistence (M2) + validated persistence (M3)
  - `test_models.py` — 20 tests: Pydantic model validation and cascade
  - `test_rules.py` — 29 tests: inventory rules, gold/HP rules, win/lose conditions
- **LLM tests** (`@pytest.mark.llm`): make real model calls. None exist yet;
  they arrive in Milestone 7 and stay separate from the deterministic suite.

## Project structure (M4)

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
      rules.py           # 9 pure rule functions: inventory, gold, HP, win/lose (M4)
    tools/               # thin @function_tool wrappers; one of two SDK-touching layers
      game_tools.py      # 7 tools: roll_dice, save/load state (M2), get_inventory,
                         # add_item, remove_item, validate_action (M4)
    agents/
      game_master.py     # Game Master agent + GAME_MASTER_INSTRUCTIONS constant
  tests/
    test_smoke.py        # 8 tests  — imports, config, provider, agent contract
    test_dice.py         # 12 tests — dice domain logic
    test_state.py        # 9 tests  — state persistence (6 M2 + 3 M3 validated)
    test_models.py       # 20 tests — Pydantic model validation
    test_rules.py        # 29 tests — inventory, gold, HP, win/lose rules (M4)
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
3. **Pydantic domain models** (`Player`, `GameState`, `InventoryItem`, `Quest`, `ActionResult`) ✅ done
4. **Inventory & game rules** (pure rule functions, 4 new tools, win/lose conditions) ✅ done ← *you are here*
5. Multi-agent (Game Master, Rules Referee, Inventory Keeper, Lore Keeper, Critic)
6. Guardrails & safety constraints
7. Evaluation & tests
8. Bridge to QA/TestOps AI (`docs/qa_migration_notes.md`)
