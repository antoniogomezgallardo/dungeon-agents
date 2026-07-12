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
- **The domain layer (`domain/`, from M2) must have zero SDK dependency** — pure
  Python, unit-testable without an API key. Only `agents/` and `tools/` touch the
  OpenAI Agents SDK (import name: `agents`). From M3, `domain/models.py` holds the
  Pydantic data contract; Pydantic itself has no SDK dependency. From M4,
  `domain/rules.py` holds the deterministic game rules (pure functions:
  `GameState` → `ActionResult`); no SDK import.
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
  `state.py` (bounded writes, JSON validation, `tmp_path` injection; originally
  added free-form `save_game_state`/`load_game_state` functions — retired in M5
  when the project unified on the validated format). `tools/` layer: thin
  `@function_tool` wrappers. Game Master wired with `roll_dice` + save/load
  tools; instructions updated to call `roll_dice` for chance. `main.py`: SDK
  hooks (`RunHooks` subclass, now debug-mode-gated in M5); startup help panel +
  `help`/`?`/`/help` meta-command; all console output ASCII-only for Windows
  `cp1252` portability. 26 deterministic tests passing with no API key (8 smoke +
  12 dice + 6 state). Saved state lives in `data/` (git-ignored).
- **M3 — Domain models: DONE.** Five Pydantic models in `domain/models.py` (pure
  Python, zero SDK): `InventoryItem` (name non-empty, quantity ge=1), `Player`
  (name non-empty, hp 0..MAX_HP=100, max_hp ge=1, gold ge=0), `Quest` (title
  non-empty, description, completed bool — data only; rules deferred to M4),
  `GameState` (container: player + inventory + location + optional active_quest +
  session_summary; nested validation cascades so a bad item or out-of-range hp
  invalidates the whole state), `ActionResult` (success bool required/no default,
  message, optional new_state). Two new persistence functions in `state.py`:
  `save_state(GameState)` uses `model_dump_json`; `load_state()` uses
  `model_validate_json` and raises `StateError` on schema mismatch. (M2 raw-JSON
  functions coexisted at this point; both were retired in M5 when the project
  unified on the validated format.) 49 deterministic tests (8 smoke + 12 dice +
  9 state + 20 models), all passing without an API key.
- **M4 — Inventory & game rules: DONE.** Nine pure rule functions in
  `domain/rules.py` (zero SDK): `get_inventory`, `add_item`, `remove_item`
  (can't remove items you don't have), `spend_gold` (can't overspend), `earn_gold`,
  `change_hp` (HP clamped to [0, max_hp] via `max(0, min(v, cap))`),
  `complete_quest`, `is_game_won`, `is_game_over`. Each takes a `GameState` and
  returns an `ActionResult` (or bool for win/lose); never mutates input
  (`model_copy(deep=True)`). Four new `@function_tool` wrappers in
  `game_tools.py` → 7 tools total. Game Master instructions updated to enforce
  rules via tools. `HELP_TEXT` updated with inventory, gold, HP limits, win/lose
  conditions. 78 deterministic tests (8 smoke + 12 dice + 9 state + 20 models +
  29 rules), all passing without an API key.
- **M5 — Session state & UX: DONE.** Five blocks:
  (A) Persistence unification — retired the M2 free-form JSON save tools
  (`save_game_state` / `load_game_state`) entirely; unified on the single
  validated `GameState` schema. Added `load_state_or_none()` (tolerant: returns
  None for missing OR incompatible saves instead of raising `StateError`) and
  `clear_state()` (delete save for new game). New tools `save_game` / `load_game`
  replace the retired M2 tools.
  (B) Session management — `last_scene: str` field added to `GameState`; persisted
  after every GM turn; reprinted verbatim on resume (deterministic, not
  improvised). `Recap` panel shows name/location/HP/gold/quest + session_summary
  on startup. `RESUME_PROMPT` tells model to continue rather than restart. `new`
  command discards save and starts fresh.
  (C) State on demand — `stats`/`status` and `inventory`/`inv` and
  `summary`/`recap` console meta-commands read validated `GameState` directly
  (deterministic, never AI-narrated). After every meta-command (except `exit`),
  last scene is re-shown.
  (D) Debug mode — `DUNGEON_DEBUG` env var (truthy values: 1/true/yes/on) plus
  in-game `debug` toggle. `DebugState` mutable holder so already-built hooks see
  runtime toggles. Enriched `RunHooks`: `on_agent_start` (which agent is
  working), `on_tool_start` / `on_tool_end` (tool name, args, result, timing in
  ms). Off by default; clean play stays clean.
  (E) UX refinements — `_start_new_game()` seeds a fresh `GameState` at game
  start so stats work from turn 0. `update_summary` tool: GM writes story beats
  into `session_summary` (persisted, so `summary` command is deterministic).
  `set_location` and `set_quest` tools sync tracked state to the GM's improvised
  story.
  State-sync reliability lesson: with `claude-haiku-4-5`, the GM does not
  reliably call `set_location`/`set_quest` despite explicit instructions. The code
  is correct; the model is the variable. Response: show "not set yet" (honest
  gap) rather than a fabricated template value. KEY LESSON: a prompt pushes
  probabilities, not guarantees. What MUST happen goes in deterministic code. What
  depends on the model must fail honestly (visible gap), never deceptively
  (fabricated value). This is the most important agent lesson in the project and
  the strongest bridge to TestOps AI.
  Note on save_game/load_game: these were introduced as M5 tool wrappers but were
  retired post-M6 (see note below). At the end of M5, 10 tools existed including
  them; they no longer exist as tools.
  81 deterministic tests (10 smoke + 12 dice + 9 state + 21 models + 29 rules),
  all passing without an API key.
- **M6 — Multi-agent: DONE.** The single Game Master became an *orchestrator* of a
  team of four agents, demonstrating two coordination patterns. **Rules Referee**
  (specialist): arbitrates contested outcomes — dice, gold, HP — wired to the GM
  via `.as_tool()` (agent-as-tool: control returns to the GM). **Lore Keeper**
  (specialist): keeps location/quest/`session_summary` in sync with the story,
  also agent-as-tool; addresses M5's state-sync unreliability structurally by
  giving world-coherence its own narrow-scoped agent. **Critic** (verifier): a
  *review pipeline* (not agent-as-tool) orchestrated deterministically in
  `main.py` — after the GM writes a scene, the Critic checks it against the
  validated state, and on a contradiction the GM regenerates (self-repair loop
  bounded by `MAX_SCENE_RETRIES=1`, an anti-loop guard in code). Structured verdict
  (`OK` / `PROBLEM: ...`) so code decides. The Critic is the LLM-as-a-judge pattern
  and the seed of M8's evaluation. Design asymmetry worth remembering: the Lore
  Keeper is agent-as-tool (sync tolerates an honest "not set yet" gap) while the
  Critic is a guaranteed pipeline step (verification must never be skipped) — code
  guarantees what MUST always happen; agents handle what tolerates honest failure.
  Two M6 fixes from playtesting: (a) `earn_gold`/`spend_gold`/`change_hp` existed
  in `rules.py` since M4 but were never exposed as tools, so narrated gold/HP were
  lost on reload — now Referee tools persist them; (b) `validate_action` (a
  misleading name that delegated the decision back to the model) was replaced by
  `check_can_afford`, backed by the deterministic pure function `can_afford`, and
  bare dice were tied to consequence via `resolve_check` (roll vs a named
  difficulty, decided in code) exposed as the `skill_check` tool. End-of-game
  detection wired: `_check_end_of_game()` in `main.py` reads the validated state
  after every turn and returns "won" / "lost" / None — calling `is_game_won` /
  `is_game_over` from M4, which were never called until now. Defeat takes
  precedence over victory. Five new tests in `test_end_of_game.py`. 119
  deterministic tests (incl. new referee/lore-keeper/critic contract tests +
  can_afford + resolve_check + end-of-game), all passing without an API key.
  Reference doc:
  `docs/principios-y-patrones-de-agentes.md` (when to use agents, when not,
  non-negotiable principles, coordination patterns).
- **Post-M6 fixes (on branch fix/session-ux-and-save-load, 125 tests):**
  (1) Meta-command loop fix — after any meta-command (stats/inventory/help/saves/
  save/load) the model is NOT invoked; scene generation only happens on the opening
  scene, after `new`, and after a real player action. This eliminates spurious
  empty-scene calls and "Game Master is working" messages on meta-commands.
  (2) Startup menu — if a saved game exists, the game now presents a
  continue/new choice before loading the SDK. Choosing `new` at the startup
  prompt asks for confirmation before discarding. Without a save, starts directly.
  (3) Named checkpoints (SaveSlot) — `save <name>` / `load <name>` / `saves`
  console commands. `SaveSlot` model in `domain/models.py` bundles validated
  `GameState` + conversation history (both halves of agent state). `save_checkpoint`
  / `load_checkpoint` / `list_checkpoints` / `_safe_slot_filename` in `state.py`
  (bounded write: name sanitized to safe filename, no path traversal). Checkpoints
  live in `data/saves/`. 6 new tests in `test_state.py` (now 15 total).
  (4) Retirement of save_game / load_game tools — these agent tools were no-ops
  (autosave makes them redundant; load only narrated a summary without restoring
  anything). Removed from `game_tools.py` and `game_master.py`. Save/load is now
  a deterministic console command, not something the model manages. A comment in
  `game_tools.py` explains the removal.
  KEY LESSON (checkpoints): agent state = validated store + conversation memory.
  Point-in-time restore requires both. `SaveSlot` captures both; restoring only
  the `GameState` would give the model its old facts but no memory of how it got
  there. This is the strongest transfer to TestOps AI in the project so far.
- M7 — Guardrails & safety constraints: not started.
- M8 — Evaluation & tests: not started.
- M9 — Bridge to QA/TestOps AI (`docs/qa_migration_notes.md`): not started.
