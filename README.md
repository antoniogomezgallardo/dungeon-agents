# Dungeon Agents

A small console fantasy RPG driven by AI agents.

> **This is a learning project, not a game product.** Its real purpose is to
> practice designing, coding, testing, observing, and evolving AI agents in
> Python — patterns that will later migrate into a QA/Testing product,
> **TestOps AI**. The RPG is the pretext; testability and clarity are the goal.

## Current milestone: **M7 — Guardrails & Safety** (done)

**M7 — Guardrails & safety constraints (done).** A three-block **defense in
depth** that screens every player message before the model sees it and every GM
scene before the player sees it. **Block 1:** `detect_injection` in
`domain/guardrails.py` — a pure-Python, pattern-based detector for 13 known
injection shapes (zero SDK, no API key, fully unit-testable). Wired into the
Game Master via the SDK's `@input_guardrail` in `agents/guardrails.py`. Blocked
messages are discarded from history so they cannot poison future turns.
**Block 2:** the **Injection Judge** (`agents/injection_judge.py`) — a tiny
specialist that reads every message passing Block 1 and gives a one-word verdict
(`SAFE` / `INJECTION`) for cases the patterns cannot reach (e.g. "Pretend to be a
calculator"). `INJECTION_JUDGE_INSTRUCTIONS` is a module-level constant, so the
behavioral contract is testable without an API key. The two-layer guardrail now
reports `blocked_by: pattern:<label>` or `blocked_by: llm`. **Block 3:** the
**Character Judge** (`agents/character_judge.py`) — an output-side reviewer that
checks the GM's scene before it reaches the player. Its one question:
`IN_CHARACTER` or `LEAK`? A leak (admitting AI nature, quoting its prompt, obeying
an out-of-world command) triggers a bounded regeneration alongside the Critic,
reusing the self-repair loop already in `_play_turn`. Integrated in the pipeline
rather than via the SDK's `@output_guardrail` to avoid fighting the tripwire
exception and reuse the existing retry cap. The complete pipeline: input pattern
check -> LLM judge -> Game Master -> Critic (coherence) + Character Judge (safety)
-> player. M7 also introduces the project's **first `@pytest.mark.llm` tests** —
5 for the Injection Judge and 6 for the Character Judge — using a weak oracle
(`startswith(verdict_token)`) appropriate for non-deterministic classifiers.
**160 deterministic tests** passing without an API key; **11 LLM tests** requiring
a live key (skipped automatically when no key is set). See the deep-dive at
[docs/milestones/milestone-07-guardrails.md](docs/milestones/milestone-07-guardrails.md).

**M6 — Multi-agent (done).** The single Game Master became an **orchestrator** of a
team of four agents, demonstrating two coordination patterns. The **Rules Referee**
arbitrates contested outcomes (dice, gold, HP) and the **Lore Keeper** keeps the
tracked world (location, quest, summary) in sync with the story — both wired to the
Game Master via `.as_tool()` (the **agent-as-tool** pattern: the GM calls them and
control returns to it). The **Critic** is different: a **review pipeline** run
deterministically in `main.py` — after the GM writes a scene, the Critic checks it
against the *validated state*, and on a real contradiction the GM regenerates
(a self-repair loop bounded by a retry cap in code, never at the model's
discretion). Two fixes came from playtesting: gold/HP now **persist** (the M4 rule
functions were finally exposed as tools), and dice were **tied to consequence**
(`skill_check` rolls against a named difficulty and the *code* decides success,
replacing a bare roll the model interpreted at whim). The design lesson: guarantee
what MUST always happen in code (the Critic always reviews; the retry cap is fixed),
and let agents handle what tolerates an honest gap. See the reference guide
[docs/principios-y-patrones-de-agentes.md](docs/principios-y-patrones-de-agentes.md).

**M5 — Session state & UX (done).** Five blocks delivering a stable, honest
session experience: **persistence unification** (retired the M2 free-form JSON
save tools; unified on the single validated `GameState` schema; added a tolerant
`load_state_or_none` that discards incompatible saves instead of crashing);
**session management** (`last_scene` field persisted verbatim for a deterministic
resume — exact scene reprinted on startup; `new` command to start fresh);
**state on demand** (`stats`, `inventory`, `summary` console commands that read
validated `GameState` directly — deterministic, not AI-narrated); **debug mode**
(`DUNGEON_DEBUG` env var + in-game `debug` toggle; enriched `RunHooks` showing
which agent is working, tool calls, and timing — off by default, opt-in);
**UX refinements** (state seeded at game start so stats work from turn 0;
`update_summary` tool writes story beats to persisted state; `set_location` /
`set_quest` tools sync tracked state to the GM's improvised story). The key
lesson: a prompt raises the probability that the model calls a tool; tested Python
is the only guarantee. 81 deterministic tests passing without an API key.

**M4 — Inventory & game rules (done).** Nine deterministic rule functions in
`domain/rules.py` give the game its first enforced mechanics: **`add_item`** /
**`remove_item`** (can't use an item you don't have), **`spend_gold`** /
**`earn_gold`** (can't spend more than you carry), **`change_hp`** (HP clamped
to `[0, max_hp]` — damage and healing both safe), **`complete_quest`** /
**`is_game_won`** / **`is_game_over`** (win by completing the active quest; lose
when HP hits 0). Four new agent tools follow a **load-modify-save** pattern. 78
deterministic tests.

**M3 — Domain models (done).** Five Pydantic models (`InventoryItem`, `Player`,
`Quest`, `GameState`, `ActionResult`) and two validated persistence functions
(`save_state` / `load_state`). Invalid state cannot be built, saved, or loaded
silently. 49 deterministic tests.

**M2 — Deterministic tools (done).** `roll_dice` (validated, reproducible dice
rolls from Python — never invented by the model), bounded JSON-validated
persistence in `data/`. Domain layer (`domain/`) and tools layer (`tools/`)
introduced. SDK hooks surface tool calls in debug mode. 26 deterministic tests.

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
Startup shows an ASCII-art title and a short welcome; type `help` at any time to
see how to play (no game turn is consumed). Type `exit` or `quit` (or press
Ctrl+C) to leave.

Meta-commands (no game turn consumed):

| Command | What it does |
|---------|-------------|
| `stats` / `status` | HP, gold, location, quest — read directly from validated state, not AI-narrated |
| `inventory` / `inv` | What you're carrying — same source |
| `summary` / `recap` | Running story recap the GM has been keeping |
| `help` | How to play (then re-shows your current scene) |
| `save <name>` | Save a named checkpoint you can return to exactly (e.g. `save before boss`) |
| `load <name>` | Restore a named checkpoint — state and full conversation history |
| `saves` | List all named checkpoints |
| `new` | Discard the current game and start a fresh adventure (asks to confirm) |
| `debug` | Toggle debug mode (see tool calls and timing; see `DUNGEON_DEBUG` below) |
| `exit` / `quit` | Quit (progress is saved automatically as you play) |

**Startup menu.** When you launch with a saved game, the game asks whether to
`continue` it or start `new`. Without a saved game, it starts immediately — no
menu. Choosing `new` at the startup prompt, or typing `new` mid-game, asks for
confirmation before discarding the current game so an accidental keypress never
loses progress.

**Autosave vs checkpoints.** Progress is saved automatically after every action
— you never lose your place. Autosave is a single timeline: every action
overwrites the previous save, so you cannot go back. A named checkpoint (`save
<name>`) is a frozen snapshot that is never overwritten. It is the only way to
return to an exact earlier moment. Checkpoints capture both the game state and
the full conversation history, so `load <name>` restores the exact point — the
model resumes with its full memory, not a re-improvised summary.

**Learning note: why checkpoints capture two things.** An agent's state is two
separate artifacts: (1) the validated data store (HP, gold, inventory, location —
what `stats` reads), and (2) the conversation history (the model's memory of what
has happened). The autosave keeps (1) current at all times. But restoring a game
to an exact earlier moment requires both: if you reload (1) without (2), the model
has forgotten what happened and improvises from a resume prompt rather than
continuing naturally. `SaveSlot` (`domain/models.py`) bundles both halves
together so `load <name>` is a complete, faithful restore. This is the key
transfer lesson to TestOps AI: agent state = validated store + conversation
memory, and point-in-time restore requires both.

**Debug mode** surfaces what the agent does under the hood — which tools it calls,
what they returned, and how long each took. Off by default. Enable it two ways:

```bash
# Permanently via env var (add to .env):
DUNGEON_DEBUG=1

# Or toggle at runtime by typing `debug` at the You: prompt
```

Without the API key for your selected provider, the app prints a friendly
message and exits cleanly instead of crashing.

**First launch takes ~20 seconds** — this is normal. The OpenAI Agents SDK and
the LiteLLM adapter are heavy to import; the app shows a "Loading the game
engine…" spinner while they load. Subsequent launches in the same session are
instant.

## Tests

```bash
python -m pytest -m "not llm"     # deterministic tests only — no API key needed
python -m pytest -m "llm"         # LLM tests only — requires a live API key
python -m pytest                  # full suite (160 deterministic + 11 LLM)
```

`pytest` is included in the `[dev]` extra installed in the Setup step above —
no separate install needed.

- **Deterministic tests** (no `llm` marker): **160 tests** across eleven files,
  all passing without an API key:
  - `test_smoke.py` — 10 tests: imports, config, provider selection, agent contract, debug flag
  - `test_dice.py` — 18 tests: dice domain logic, seeded RNG, bounds, skill checks (M6)
  - `test_state.py` — 15 tests: validated persistence, tolerant loader, clear_state (M5); named checkpoints — save/load round-trip, name sanitization, incompatible slot, list (post-M6)
  - `test_models.py` — 21 tests: Pydantic model validation and cascade
  - `test_rules.py` — 38 tests: inventory, gold/HP, win/lose, `can_afford` (M6)
  - `test_rules_referee.py` — 7 tests: Rules Referee contract, skill-check + persistence (M6)
  - `test_lore_keeper.py` — 5 tests: Lore Keeper contract, GM delegation (M6)
  - `test_critic.py` — 6 tests: Critic contract, structured verdict, bounded retry (M6)
  - `test_end_of_game.py` — 5 tests: win/lose detection wired via `_check_end_of_game` (M6)
  - `test_guardrails.py` — 29 tests: `detect_injection` — 14 attack detections, 12 false-positive guards, 3 standalone (M7)
  - `test_injection_judge.py` — 3 deterministic contract tests: `INJECTION_JUDGE_INSTRUCTIONS` and verdict tokens (M7)
  - `test_character_judge.py` — 3 deterministic contract tests: `CHARACTER_JUDGE_INSTRUCTIONS` and verdict tokens (M7)
- **LLM tests** (`@pytest.mark.llm`): **11 tests** making real model calls.
  Skipped automatically when no API key is configured. Introduced in M7:
  - `test_injection_judge.py` — 5 LLM tests: 3 novel-injection cases the patterns miss must be blocked; 2 legitimate-play cases must be allowed
  - `test_character_judge.py` — 6 LLM tests: 3 character-leak cases must be flagged; 2 normal-narration cases must be allowed

## Project structure (M7)

```text
dungeon-agents/
  pyproject.toml
  .env.example           # includes DUNGEON_DEBUG (off by default)
  data/                  # git-ignored; holds game_state.json when saved
  src/dungeon_agents/
    config.py            # the ONLY place env vars are read; reads DUNGEON_DEBUG (M5)
    main.py              # console loop + I/O; meta-commands: stats, inventory,
                         # summary, new, debug, help, save <name>, load <name>,
                         # saves, exit; startup menu (continue/new); _confirm for
                         # destructive ops; _check_end_of_game / _print_end_of_game (M6);
                         # _review_character + Character Judge in _play_turn pipeline (M7)
    domain/              # pure Python, zero SDK — testable business logic
      models.py          # 6 Pydantic models: InventoryItem, Player, Quest, GameState
                         # (+ last_scene field M5), ActionResult, SaveSlot (post-M6)
      dice.py            # roll_dice(), resolve_check() (M6), InvalidDiceError,
                         # InvalidDifficultyError, DIFFICULTY_THRESHOLDS, MIN/MAX_SIDES
      state.py           # save_state / load_state (strict) / load_state_or_none
                         # (tolerant, M5) / clear_state (M5) + StateError
                         # (M2 free-form tools retired in M5; one validated format);
                         # save_checkpoint / load_checkpoint / list_checkpoints /
                         # _safe_slot_filename (post-M6 named checkpoints)
      rules.py           # pure rule functions: inventory, gold, HP, win/lose (M4);
                         # can_afford() (M6)
      guardrails.py      # detect_injection(), InjectionResult, _INJECTION_PATTERNS (M7)
                         # pure Python, zero SDK — domain layer of the security stack
    tools/               # thin @function_tool wrappers; one of two SDK-touching layers
      game_tools.py      # tools: roll_dice, get_inventory, add_item, remove_item,
                         # check_can_afford (M6, replaces validate_action),
                         # earn_gold, spend_gold, change_hp (M6), skill_check (M6),
                         # update_summary, set_location, set_quest
                         # (save_game / load_game were retired post-M6: autosave
                         # makes them no-ops; save/load is now a console command)
    agents/
      game_master.py     # Game Master agent + GAME_MASTER_INSTRUCTIONS constant
      rules_referee.py   # Rules Referee agent + RULES_REFEREE_INSTRUCTIONS (M6)
      lore_keeper.py     # Lore Keeper agent + LORE_KEEPER_INSTRUCTIONS (M6)
      critic.py          # Critic agent + CRITIC_INSTRUCTIONS, verdict tokens (M6)
      guardrails.py      # build_injection_guardrail() — two-layer @input_guardrail (M7)
      injection_judge.py # Injection Judge agent + INJECTION_JUDGE_INSTRUCTIONS,
                         # JUDGE_SAFE, JUDGE_INJECTION, build_injection_judge (M7)
      character_judge.py # Character Judge agent + CHARACTER_JUDGE_INSTRUCTIONS,
                         # CHARACTER_OK, CHARACTER_LEAK, build_character_judge (M7)
  tests/
    test_smoke.py        # 10 tests — imports, config, provider, agent contract, debug flag
    test_dice.py         # 18 tests — dice domain logic + resolve_check (M6)
    test_state.py        # 15 tests — validated persistence + tolerant loader + clear_state; named checkpoints (post-M6)
    test_models.py       # 21 tests — Pydantic model validation
    test_rules.py        # 38 tests — inventory, gold, HP, win/lose rules + can_afford (M6)
    test_rules_referee.py # 7 tests — Rules Referee contract (M6)
    test_lore_keeper.py  # 5 tests  — Lore Keeper contract (M6)
    test_critic.py       # 6 tests  — Critic contract, structured verdict, retry cap (M6)
    test_end_of_game.py  # 5 tests  — win/lose detection via _check_end_of_game (M6)
    test_guardrails.py   # 29 tests — detect_injection: 14 attacks, 12 false-positive guards,
                         #            3 standalone (case-insensitivity, known gap) (M7)
    test_injection_judge.py # 3 deterministic + 5 @pytest.mark.llm — Injection Judge (M7)
    test_character_judge.py # 3 deterministic + 6 @pytest.mark.llm — Character Judge (M7)
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
4. **Inventory & game rules** (pure rule functions, 4 new tools, win/lose conditions) ✅ done
5. **Session state & UX** (persistence unification, deterministic resume, stats/inventory/summary/new/debug commands, debug mode) ✅ done
6. **Multi-agent** (Game Master orchestrator + Rules Referee, Lore Keeper, Critic; agent-as-tool + review pipeline) ✅ done
7. **Guardrails & safety constraints** (2-layer input guardrail: patterns + Injection Judge; output guardrail: Character Judge; first `@pytest.mark.llm` tests) ✅ done
8. Evaluation & tests
9. Bridge to QA/TestOps AI (`docs/qa_migration_notes.md`)
