# Milestone 5 — Session State & UX

> **Status:** Done
> **Theme:** What MUST happen goes in code; what the model controls must fail honestly, never deceptively.

---

## 1. Goal

M4 gave the game enforced rules and a win condition. But two problems lurked
underneath: a persistence bug that could crash a tool on startup, and a UX that
made the game feel stateless and confusing.

The **persistence bug** was concrete: two save systems coexisted. M2 had introduced
a free-form JSON save (`save_game_state` / `load_game_state`) that wrote whatever
the model happened to say — fields like `player_name`, `health`, `current_scene`.
M3 later added a validated save (`save_state` / `load_state`) that expected the
full `GameState` schema — fields like `player`, `inventory`, `active_quest`. If
the agent had called the M2 saver at some point, the file on disk had the M2 shape.
When the M3 loader ran on the next launch, Pydantic raised a `ValidationError` —
the exact crash the user hit — because the file passed JSON parsing but failed
schema validation.

The **UX problems** were equally real: the game had no way to start fresh without
manually deleting a file; resuming a session improvised a new opening scene instead
of continuing where you left off; `stats` and `inventory` at the console showed
"No character yet" until the model happened to call a save tool; and there was no
way to see what the agent was doing under the hood when debugging a session.

M5 is five blocks plus a state-sync fix. Together they address all of this:

- **Block A** — persistence unification: retire the M2 format, unify on one validated
  schema, add a tolerant loader that discards incompatible saves gracefully.
- **Block B** — session management: deterministic resume (a Recap panel + exact last
  scene reprinted verbatim); `new` command to start fresh; model told to *continue*
  rather than restart when loading.
- **Block C** — state on demand: `stats`, `inventory`, and `summary` console commands
  that read the validated `GameState` directly and print exact values — not
  AI-narrated estimates.
- **Block D** — optional debug mode: `DUNGEON_DEBUG` env var plus in-game `debug`
  toggle to surface tool calls, timing, and agent identity; off by default so
  normal play stays clean.
- **Block E** — UX refinements from playtesting: seed a starter state at game start
  so stats always have something to show from turn 0; `update_summary` tool so the
  GM records story beats into persisted state; `summary`/`recap` command to view
  it on demand.
- **State-sync fix** — the most important lesson: `new_game_state()` now starts
  neutral (no hard-coded template location or quest); two new tools (`set_location`,
  `set_quest`) let the GM sync tracked state to its own improvised story; the
  deeper discovery is that a small model does not reliably call those tools —
  which turns into the central lesson of M5.

After M5, stats are always exact, resuming is always deterministic, incompatible
saves are discarded gracefully, and the code is honest about what it knows.

---

## 2. What was built — point by point

### Block A — Persistence unification

#### 2.1 The root problem: two formats doing the same job

The M2 save functions wrote arbitrary JSON shaped by whatever the model passed.
The M3 validated functions wrote the `GameState` Pydantic schema. If the agent
ever called the M2 tool (which it did, because those tools were still registered),
the file on disk had the M2 shape. The M3 `load_state` tried to
`GameState.model_validate_json` that file. The `player` key was missing; `health`
and `player_name` were present but unknown. Pydantic raised a `ValidationError`.
The tool handler did not catch `ValidationError`; it propagated as an unhandled
exception and crashed the game.

This is the canonical **two-format incompatibility bug**: two systems doing the
same job, writing different shapes to the same file, each expecting its own shape
back. One format wins, the other fails at read time.

#### 2.2 The fix: retire M2, unify on one validated format

`domain/state.py` now exposes only three public functions:

```
save_state(state: GameState) -> str
load_state() -> GameState | None       # strict — raises StateError on schema mismatch
load_state_or_none() -> GameState | None  # tolerant — returns None for any failure
clear_state() -> None
```

The M2 functions (`save_game_state`, `load_game_state`) and their corresponding
`@function_tool` wrappers were removed. The `import json` that backed them was
also removed. `state.py` now imports only Pydantic — it is fully validated all
the way down.

The agent's save/load tools are now `save_game` and `load_game` (see section 2.3),
both built on `save_state` / `load_state_or_none`. There is one format on disk
and one code path that reads it.

**Why keep two loader variants rather than one?**

The same operation can have two correct behaviors depending on context:

- `load_state()` is the **strict** loader used in tests and internal persistence.
  When a save exists but fails the schema, that is a bug worth surfacing loudly as
  `StateError`. Tests assert on this explicitly
  (`test_load_state_rejects_schema_mismatch`).
- `load_state_or_none()` is the **tolerant** loader used by the game loop and all
  tools. When a save exists but fails the schema, the game treats it as "no valid
  save" and starts fresh with a friendly message. Crashing on startup because the
  user has an old save file is a bad UX. Discarding it and starting clean is
  correct behavior.

The loader you choose should match what failure *means* in that context. In tests,
an incompatible save is a bug in the test data — loud failure is right. In the game
loop, an incompatible save is a version mismatch from a previous build — silent
discard and start fresh is right.

#### 2.3 `save_game` and `load_game` tools

Two new `@function_tool` wrappers replace the retired M2 tools:

```python
@function_tool
def save_game() -> str:
    current = state.load_state_or_none() or new_game_state()
    return state.save_state(current)

@function_tool
def load_game() -> str:
    saved = state.load_state_or_none()
    if saved is None:
        return "No saved game found (or it was incompatible). Starting a new adventure."
    p = saved.player
    quest = saved.active_quest.title if saved.active_quest else "none"
    return (
        f"Resumed. {p.name} is at {saved.location} with {p.hp}/{p.max_hp} HP "
        f"and {p.gold} gold. Active quest: {quest}."
    )
```

Both delegate to `load_state_or_none` — they are immune to the crash that existed
when the M3 strict loader ran on an M2-format file.

#### 2.4 `clear_state()` — the new-game primitive

```python
def clear_state(*, data_dir: Path | None = None) -> None:
    """Delete the saved state file if it exists."""
    path = _state_path(data_dir or DEFAULT_DATA_DIR)
    path.unlink(missing_ok=True)
```

`missing_ok=True` makes this a safe no-op when there is nothing to delete. The
`new` console command calls this via `_start_new_game()` in `main.py`, which then
seeds a fresh `GameState` immediately.

---

### Block B — Session management

#### 2.5 `last_scene: str` field in `GameState`

A new field was added to `GameState` in `domain/models.py`:

```python
last_scene: str = Field(
    default="",
    description="The Game Master's most recent scene text, for exact resume.",
)
```

After every Game Master response, `main.py` calls `_remember_last_scene(scene)`,
which loads the current saved state, sets `last_scene = scene`, and saves again.
On the next launch, `_resume_banner()` reprints this field verbatim — the player
sees the exact scene they left on, not an improvised re-opening.

This is the **deterministic resume** property: the resume experience is independent
of the model's memory or mood. The model's output from a prior session is stored in
validated state and replayed exactly. If you closed the game mid-dungeon, you
return to mid-dungeon.

#### 2.6 The Recap panel on resume

When `main.py` starts and finds a valid save, it shows a structured `Recap` panel
before the last scene:

```python
def _resume_banner(state) -> None:
    p = state.player
    quest = state.active_quest.title if state.active_quest else "none"
    recap_lines = [
        f"Resuming your adventure as {p.name}.",
        f"Location: {state.location}  |  HP: {p.hp}/{p.max_hp}  |  Gold: {p.gold}",
        f"Quest: {quest}",
    ]
    if state.session_summary:
        recap_lines.append(f"\nSo far: {state.session_summary}")
    console.print(Panel("\n".join(recap_lines), title="Recap", border_style="cyan"))
    if state.last_scene:
        _print_scene(state.last_scene)
```

The panel is assembled from validated `GameState` fields — no model call, no
chance of improvised incorrect values. After the recap, the model receives
`RESUME_PROMPT` ("The player is resuming a saved game. Continue the adventure
naturally from the scene just shown") rather than `OPENING_PROMPT` ("Begin the
adventure"). The model's job is to continue, not restart.

#### 2.7 The `new` console command

`NEW_WORDS = {"new", "/new"}` triggers `_start_new_game()`:

```python
def _start_new_game() -> None:
    from dungeon_agents.tools.game_tools import new_game_state
    game_state.save_state(new_game_state())
```

This calls `clear_state()` implicitly by overwriting the file (via `save_state`,
which always writes), then resets the in-memory conversation to `OPENING_PROMPT`.
The prior adventure is gone; a fresh `GameState` is on disk immediately so
stats/inventory work from turn 0.

#### 2.8 Re-show last scene after meta-commands

Every meta-command (`help`, `stats`, `inventory`, `summary`) ends by reprinting
`_last_scene` if it is non-empty. This means the player never loses their place.
The `exit` command is the only one that does not re-show — the player is leaving.

---

### Block C — State on demand

#### 2.9 `stats` / `status` command

`STATS_WORDS = {"stats", "status", "/stats"}` triggers `_print_status()`:

```python
def _print_status(*, inventory_only: bool = False) -> None:
    from dungeon_agents.domain import rules
    state = game_state.load_state_or_none()
    if state is None:
        console.print("[dim]No character yet - take an action to begin.[/dim]")
        return

    if not inventory_only:
        p = state.player
        quest = state.active_quest.title if state.active_quest else "not set yet"
        done = " (completed)" if state.active_quest and state.active_quest.completed else ""
        where = state.location if state.location != "unknown" else "not set yet"
        lines = [
            f"{p.name}",
            f"HP:    {p.hp}/{p.max_hp}",
            f"Gold:  {p.gold}",
            f"Where: {where}",
            f"Quest: {quest}{done}",
        ]
        console.print(Panel("\n".join(lines), title="Stats", border_style="blue"))

    console.print(Panel(rules.get_inventory(state), title="Inventory", border_style="blue"))
```

This reads the validated `GameState` directly and prints exact, code-computed
values. The model never touches this output. HP is whatever `Player.hp` holds;
gold is whatever `Player.gold` holds. Neither can be wrong by design — Pydantic
enforces the bounds at write time.

**Why "not set yet" instead of a default?**

If location is `"unknown"` (the field's default, set by `new_game_state()`), the
stats screen shows `"not set yet"`. This is an honest gap — the GM has not yet
called `set_location`, so the tracked state genuinely does not know where the
player is. The alternative — showing a hard-coded template like `"Broken Wall Inn"`
from the starter state — would show a value that contradicts the model's improvised
story. An honest gap is always better than a confident wrong answer. This principle
becomes section 6's biggest lesson.

#### 2.10 `inventory` / `inv` command

`INVENTORY_WORDS = {"inventory", "inv", "/inventory"}` calls
`_print_status(inventory_only=True)`, which skips the HP/gold/location panel and
shows only the inventory. The inventory text comes from `rules.get_inventory(state)`,
the same deterministic M4 function used by the `get_inventory` agent tool. One
source of truth for inventory formatting.

#### 2.11 `summary` / `recap` command

`SUMMARY_WORDS = {"summary", "recap", "/summary"}` triggers `_print_summary()`:

```python
def _print_summary() -> None:
    state = game_state.load_state_or_none()
    if state is None:
        console.print("[dim]No adventure yet - take an action to begin.[/dim]")
        return
    text = state.session_summary or "Nothing notable has happened yet."
    console.print(Panel(text, title="Story so far", border_style="cyan"))
```

`session_summary` is written by the GM via the `update_summary` tool (Block E).
The console command reads it verbatim from saved state — again, deterministic,
not re-generated. Early in a session before anything story-significant has
happened, it shows "Nothing notable has happened yet."

---

### Block D — Optional debug mode

#### 2.12 `DUNGEON_DEBUG` env var and `Settings.debug`

`config.py` was updated to read `DUNGEON_DEBUG`:

```python
_TRUTHY = {"1", "true", "yes", "on"}

debug = os.getenv("DUNGEON_DEBUG", "").strip().lower() in _TRUTHY
```

`Settings` gains a `debug: bool` field. Two smoke tests verify this directly:
`test_debug_flag_off_by_default` and `test_debug_flag_reads_truthy_env`.

Setting `DUNGEON_DEBUG=1` in `.env` (or the shell) starts the game in debug mode
from the first turn. The in-game `debug` command toggles it at runtime without
rebuilding the agent.

#### 2.13 `DebugState` — a mutable holder

```python
class DebugState:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
```

A boolean would be copied by value into the closures that the `RunHooks` subclass
captures. A mutable object gives the hooks a reference they can observe at call
time — when the `debug` command sets `debug.enabled = not debug.enabled`, the
already-built hook sees the change immediately. No agent rebuild needed.

#### 2.14 Enriched `RunHooks` — only when debug is on

```python
class ToolActivityHooks(RunHooks):
    def __init__(self) -> None:
        self._started: dict[int, float] = {}

    async def on_agent_start(self, context, agent) -> None:
        if debug.enabled:
            console.print(f"[dim][debug] agent {agent.name} is working...[/dim]")

    async def on_tool_start(self, context, agent, tool) -> None:
        if debug.enabled:
            self._started[id(tool)] = perf_counter()
            console.print(f"[dim][debug] {agent.name} -> tool {tool.name}...[/dim]")

    async def on_tool_end(self, context, agent, tool, result) -> None:
        if debug.enabled:
            started = self._started.pop(id(tool), None)
            took = f" ({(perf_counter() - started) * 1000:.0f} ms)" if started else ""
            console.print(f"[dim][debug]   {tool.name} -> {result}{took}[/dim]")
```

Three hook methods:
- `on_agent_start` — which agent is working. Useful now; essential in M6 when
  multiple agents collaborate and you want to trace who did what.
- `on_tool_start` — tool name and agent, plus start time stored by `id(tool)`.
- `on_tool_end` — result and elapsed milliseconds.

This replaced the M2/M4 always-on `[tool]` print lines that every player saw on
every turn. Debug mode is now explicitly opt-in.

---

### Block E — UX refinements

#### 2.15 Seed a starter state at game start (`_start_new_game`)

`_start_new_game()` writes a fresh `GameState` to disk before the first model
call. `new_game_state()` (defined in `tools/game_tools.py`) returns:

```python
def new_game_state() -> GameState:
    return GameState(player=Player(name="Adventurer"))
```

Location defaults to `"unknown"`; `active_quest` defaults to `None`. This seeding
means that the moment the game starts, `load_state_or_none()` returns a valid
object. The `stats` command shows the character immediately. No "no character yet"
on a fresh game.

**Why define `new_game_state()` in `game_tools.py` rather than `domain/`?**

It constructs a `GameState` with deliberate defaults and is imported by both
`main.py` and the tool functions. Placing it in `game_tools.py` keeps it near its
primary consumers without adding a layer. The `domain/` layer has no concept of
"starter defaults" — that is an application-level concern.

#### 2.16 `update_summary` tool

```python
@function_tool
def update_summary(summary: str) -> str:
    """Record a concise running summary of the adventure so far."""
    game = _load_or_new_state()
    game.session_summary = summary.strip()
    return _apply(ActionResult(success=True, message="Summary updated.", new_state=game))
```

The GM is instructed to call this after story-significant moments (accepting a
quest, reaching a new place, a major win or loss). The summary is written by the
model — but because it is persisted in validated state, displaying it later via the
`summary` console command is entirely deterministic. The model writes it once; the
code reads it back exactly as written.

This is the **write once, read deterministically** pattern: the model's output
becomes a persisted fact. Once stored, the stored value — not a fresh model call
— is the source of truth for display.

#### 2.17 `set_location` and `set_quest` tools (state-sync fix)

These two tools close the gap between the model's improvised story and the
tracked `GameState`:

```python
@function_tool
def set_location(location: str) -> str:
    """Set the player's current location to match your narration."""
    location = location.strip()
    if not location:
        return "A location needs a name."
    game = _load_or_new_state()
    game.location = location
    return _apply(ActionResult(success=True, message=f"Location set to {location}.", new_state=game))

@function_tool
def set_quest(title: str, description: str = "") -> str:
    """Set (or replace) the player's active quest to match your narration."""
    title = title.strip()
    if not title:
        return "A quest needs a title."
    game = _load_or_new_state()
    game.active_quest = Quest(title=title, description=description.strip())
    return _apply(ActionResult(success=True, message=f"Quest set: {title}.", new_state=game))
```

Without these tools, the earlier M4 `_load_or_new_state()` seeded a hard-coded
starter quest (`"Clear the cellar"`, location `"Broken Wheel Inn"`). When the GM
improvised a completely different opening — a forest temple, a seaside village —
the stats screen showed the template values. The contradiction was visible to
anyone who typed `stats` in the first few turns.

The fix: `new_game_state()` seeds a truly neutral state (location `"unknown"`,
quest `None`). `set_location` and `set_quest` give the GM the tools to sync its
story to the tracked state. The GM instructions explicitly tell it to call both
on the first scene and whenever the player travels or takes on a new objective.

**The reliability lesson — the most important discovery of M5.**

With the default model (`claude-haiku-4-5`), the GM does *not* reliably call
`set_location` and `set_quest` on every new game, despite the explicit prompt
instructions. Sometimes it calls one, sometimes neither, sometimes both. The code
is correct. The model is the variable.

The design response is critical: when `location` is `"unknown"` and `active_quest`
is `None`, the `stats` screen shows `"not set yet"`. It never shows a fabricated
value. The worst case is a visible gap, not a wrong answer.

**This is the central lesson of M5:**

> A prompt pushes probabilities; it does not guarantee behavior. What MUST happen
> goes in deterministic code. What depends on the model must be designed to fail
> honestly — a visible gap — never deceptively — a fabricated value accepted as truth.

This principle governs every design decision from here forward. If the agent
forgets to set the location, the stats screen says so plainly. If the agent
forgets to update the summary, the summary screen says "nothing notable yet."
Honest gaps, not confident lies.

#### 2.18 Total tool count: 10

`build_game_master` registers 10 tools:

```python
tools=[
    roll_dice,       # dice roll — deterministic, never invented
    save_game,       # persist validated state
    load_game,       # read + summarize saved state
    get_inventory,   # read inventory (M4)
    add_item,        # add item (M4)
    remove_item,     # remove item (M4)
    validate_action, # resource context for open-ended actions (M4)
    update_summary,  # persist story beats (M5)
    set_location,    # sync location to narration (M5)
    set_quest,       # sync quest to narration (M5)
]
```

---

## 3. Concepts learned in M5

| Concept | Where it showed up | Why it transfers |
|---------|-------------------|-----------------|
| Two formats, one file = a bug class | M2 and M3 save systems coexisting; crash on load | Any time two systems write to the same resource with different schemas, version mismatches are certain — unify early |
| Two error policies for the same operation | `load_state` raises; `load_state_or_none` returns None | Pick the error policy that is *correct for the context*, not the most convenient one globally |
| Deterministic resume | `last_scene` stored in validated state; reprinted verbatim | The user experience of "resuming exactly where I was" must not depend on the model's memory — store the facts in code |
| Honest gaps over fabricated values | `"not set yet"` when location/quest are unset | A visible gap is always better than a confident wrong answer, especially when the source of data is a model |
| A prompt pushes probabilities, not guarantees | GM does not reliably call `set_location` / `set_quest` | The model is a probability distribution, not an if-statement. Design for partial compliance |
| Write once, read deterministically | `update_summary` writes once; `summary` command reads it back | Once a model output is persisted as validated state, subsequent reads are deterministic even though the original write was probabilistic |
| Mutable holder for shared runtime state | `DebugState` — a reference, not a value | When a closure or hook needs to see a future mutation, pass a mutable object, not a copied boolean |
| Hook seam for observability | `RunHooks.on_agent_start` / `on_tool_start` / `on_tool_end` | The SDK's official observability surface — not a hack. In M6, `on_agent_start` will show which of several agents is acting |
| Seed state early, not lazily | `_start_new_game()` writes to disk before the first turn | If dependent systems (stats, inventory) need valid state, create it at game start, not on first tool call — no "nothing yet" surprises |
| Meta-commands re-show context | Every meta-command reprints `_last_scene` | A user who checks stats should return to exactly where they were — interrupting the narrative to query it should be seamless |

---

## 4. QA mindset in M5

**Two save formats = a class of bugs, not an instance.**

The crash the user hit was not a one-off. Any time two systems write to the same
file with different schemas, every future schema change creates a new incompatibility.
The fix is architectural: enforce one format and one write path. In QA/testing
systems, this maps to test-result schema discipline — if two sub-systems write
test results in different shapes, the aggregator breaks whenever one shape changes.
Unify on a schema early.

**Error policy belongs to the caller, not the function.**

`load_state` and `load_state_or_none` share the same underlying logic but differ
in what they do with a `StateError`. The test suite uses `load_state` because a
bad file in a test is a bug — loud failure helps the developer. The game loop uses
`load_state_or_none` because a bad file at runtime is a version mismatch — silent
discard and restart is correct UX. The function does not choose; the caller does.
This is testability discipline: the same operation is testable as a strict
assertion in one context and as a safe fallback in another.

**Deterministic display means testable display.**

Because `stats`, `inventory`, and `summary` read from validated `GameState` fields,
their output is fully predictable given the state. You can write a test that seeds
a specific `GameState`, calls `load_state_or_none`, feeds it to `_print_status`,
and asserts on what was printed — no model call, no randomness, no network. That
is the QA property: observable behavior that is reproducible without the AI.

**"Not set yet" is a test result, not a placeholder.**

When a stat shows "not set yet", that is an accurate reading of the state. The
value is genuinely absent. In QA terms, this is equivalent to a test step that
produces no result data because the agent that was supposed to record it failed to
do so. The right response is "no data", not "invent a result". A QA system that
shows "passed" when no result was actually recorded is worse than one that shows
"result missing" — the former hides failures; the latter surfaces them.

**Observability is opt-in, not opt-out.**

Before M5, the `[tool]` print lines were always on. Every player saw the mechanics.
Debug mode flips this: clean by default, observable on demand. In a QA context,
the equivalent is verbose logging — on in CI pipelines, off in user-facing output.
Observability that cannot be silenced is noise; observability that cannot be
enabled is darkness. The `DUNGEON_DEBUG` env var + in-game `debug` toggle gives
both.

**`on_agent_start` prepares for M6.**

The hook prints which agent is working. In M5 there is only one agent, so it is
not very informative. But the hook is wired and tested, and in M6 — where the Game
Master, Rules Referee, Inventory Keeper, Lore Keeper, and Critic all collaborate —
`on_agent_start` becomes the primary way to trace who did what in a turn. Building
the observability seam before you need it is cheaper than retrofitting it later.

---

## 5. How to test / verify it yourself

```bash
# Inside an activated .venv with `pip install -e ".[dev]"` already run:

# Full deterministic suite (81 tests, no API key):
python -m pytest -m "not llm" -q
# Expected: 81 passed

# Per-file breakdown:
python -m pytest tests/test_smoke.py  -q    # 10 tests (includes 2 new debug-flag tests)
python -m pytest tests/test_dice.py   -q    # 12 tests (unchanged)
python -m pytest tests/test_state.py  -q    # 9 tests (5 original + 4 new M5 tests)
python -m pytest tests/test_models.py -q    # 21 tests
python -m pytest tests/test_rules.py  -q    # 29 tests (unchanged)

# Verify the M5 persistence behavior at the Python REPL — no SDK, no API key:
python -c "
import tempfile, pathlib
from dungeon_agents.domain.models import GameState, Player
from dungeon_agents.domain.state import (
    save_state, load_state, load_state_or_none, clear_state, STATE_FILENAME
)

with tempfile.TemporaryDirectory() as d:
    tmp = pathlib.Path(d)

    # 1. Tolerant loader returns None when no file exists
    print(load_state_or_none(data_dir=tmp))   # None

    # 2. Save and round-trip a validated state
    original = GameState(player=Player(name='Aria', hp=60, gold=15), location='tavern')
    save_state(original, data_dir=tmp)
    loaded = load_state(data_dir=tmp)
    print(loaded == original)                  # True
    print(loaded.player.name, loaded.location) # Aria tavern

    # 3. Tolerant loader discards an old-format (M2-style) file
    (tmp / STATE_FILENAME).write_text(
        '{\"player_name\": \"Hero\", \"health\": 25, \"current_scene\": \"somewhere\"}',
        encoding='utf-8'
    )
    print(load_state_or_none(data_dir=tmp))    # None  (discarded, no crash)

    # 4. clear_state removes the file
    save_state(original, data_dir=tmp)
    clear_state(data_dir=tmp)
    print(load_state(data_dir=tmp))            # None

    # 5. clear_state on a missing file is a no-op
    clear_state(data_dir=tmp)                  # no exception
    print('all ok')
"
```

**Live game verification (requires an API key):**

```bash
# Start with a clean state
dungeon-agents

# At the prompt, try these in order:
#   stats       -> shows "not set yet" for location/quest (before GM calls set_location/set_quest)
#   inventory   -> shows empty inventory
#   help        -> shows help, then reprints the current scene
#   debug       -> enables debug mode; next turn shows tool calls and timing
#   summary     -> shows "Nothing notable has happened yet" early in the game
#   new         -> discards the save and starts a fresh adventure
#   exit        -> quit; on next launch, game resumes with Recap panel + last scene
```

**Check debug output:**

```bash
# Via env var (debug on from turn 0):
DUNGEON_DEBUG=1 dungeon-agents
# Or via in-game command: type `debug` at the You: prompt
# Expected: [debug] agent Game Master is working...
#           [debug] Game Master -> tool set_location...
#           [debug]   set_location -> Location set to ... (NN ms)
```

---

## 6. Risks & tradeoffs

**Model reliability with `set_location` and `set_quest`.**

The GM is instructed to call these tools on the first scene and when the player
travels or takes a new objective. With the default `claude-haiku-4-5` model it
does not do so reliably. The instruction raises the probability but does not
guarantee the behavior. This is by design — the stats screen shows "not set yet"
rather than a fabricated value. Accepting an honest gap is the correct tradeoff.
Using a larger, more instruction-following model (e.g. `claude-sonnet-4-6` via
`DUNGEON_MODEL`) improves but does not guarantee compliance either.

**Win/lose detection still not wired to the game loop.**

`is_game_won` and `is_game_over` from M4 are deterministic functions that read
the current state. `main.py` does not call them after each turn and terminate the
loop accordingly. The functions exist and are tested; wiring them is a small step,
deferred because session management was the priority in M5.

**`last_scene` and `session_summary` are model-authored content stored as facts.**

The scene text and summary stored in `GameState` are whatever the model wrote.
They are treated as persisted facts for resume and recap purposes. If the model
writes an inconsistent summary, that inconsistency is persisted. The alternative
— re-generating the summary on demand — loses determinism. The tradeoff is accepted:
the stored value is exact, even if the content is sometimes imperfect.

**`_remember_last_scene` is best-effort.**

If there is no valid save when `_remember_last_scene` runs (e.g. the very first
turn before any tool has written state), it skips silently. The next successful
tool call creates a save, and subsequent scenes are persisted from that point on.
This means the very first scene of a brand-new game is not persisted until a tool
call happens. Practically this is rare because `_start_new_game()` writes state
before the first turn.

**Debug timing uses wall-clock `perf_counter`.**

Tool timing in debug mode is wall-clock elapsed time, which includes API
round-trip latency. It is not a measurement of the tool's own execution time.
For a `roll_dice` call (pure Python, microseconds), a 200ms timing means the
model took 200ms to finish its turn — the tool itself was instant. This is
informative but not a profiler.

**`load_state_or_none` silently discards any schema-incompatible save.**

A corrupted or manually edited save file is indistinguishable from an old-format
file — both return `None`. The user gets a fresh game with no explanation beyond
the GM saying "Starting a new adventure." A more informative message (e.g. detecting
JSON parse failure vs. schema mismatch) would require exposing more detail from the
loader. Deferred as complexity not yet needed.

---

## 7. Bridge to TestOps AI

M5's most important lesson — that a prompt is a probability, not a guarantee —
is the single most important lesson for a QA-adjacent AI agent.

| Dungeon Agents (M5) | TestOps AI equivalent |
|---------------------|----------------------|
| Two save formats in one file = crash | Two result formats in one store = aggregation breaks. Enforce a schema from day one |
| `load_state` (strict) vs. `load_state_or_none` (tolerant) | Test-result reader: strict in CI (fail the build on malformed results), tolerant in a dashboard (show "result missing" rather than crashing the view) |
| `last_scene` persisted verbatim for deterministic resume | Test-execution artifact stored at run time; replay/review is from the stored artifact, not re-generated |
| `"not set yet"` when model forgets `set_location` | `"no result"` when agent forgets to record a test outcome — visible gap, not invented pass |
| Prompt instructs GM to sync state; GM sometimes does not | QA agent instructed to log results; agent sometimes misses steps. Design the logging as a separate persisted action, not just a side effect |
| Debug hooks: `on_agent_start`, `on_tool_start`, `on_tool_end` with timing | Audit log for a QA agent: which agent evaluated which test, which assertion ran, how long each step took |
| `DUNGEON_DEBUG` env var + in-game toggle | CI-level verbose logging via env var; dashboard toggle for user-facing detail. Same pattern, same two activation paths |
| `DebugState` mutable holder — hooks see runtime changes | Any shared flag that agents must observe at call time (pause, abort, verbosity) should be a shared mutable reference, not a value copied at build time |
| `update_summary` writes once; `summary` command reads deterministically | A QA agent records a finding once; the finding viewer reads it from the store. The viewer is never the generator |

**The central transfer: prompt pushes probability, code enforces guarantees.**

The clearest statement of M5's lesson in QA terms:

> An AI QA agent can be instructed to record every test result. Sometimes it will.
> The worst failure mode is not that it records nothing — it's that it records a
> fabricated "passed" when no real check was made.
>
> Design for partial compliance: make the honest case (recording nothing, or showing
> "no result") the default when the agent skips a step. Never design a system where
> the agent's silence produces a passing status.

In Dungeon Agents this is implemented as: if `set_quest` was not called, `active_quest`
is `None`, and stats show "not set yet". The game never invents a quest title from
the old template. The code is correct; the model is the variable; the visible gap
is the designed response to model failure.

In TestOps AI, the equivalent is: if the evaluation agent does not explicitly
record a `TestResult(success=True, ...)`, the run has no result. The run viewer
shows "no result recorded" — not "passed by default". A false positive that ships
as truth is the worst outcome in QA. A visible gap triggers investigation; a
fabricated pass ships a broken build.

---

## 8. What's next — Milestone 6: multi-agent

M5 stabilized the single-agent game and made its session experience solid.
M6 takes the architecture in a different direction: replacing the single Game Master
with a team of specialist agents.

The M1-M5 design has one agent doing everything: narrating, calling inventory
tools, tracking quests, updating the summary, setting location. For a simple
console game this works. As the game complexity grows — richer lore, combat
mechanics, multiple simultaneous quests, critic feedback on narrative quality —
a single agent becomes a bottleneck. Its context fills up, its instructions grow
into a wall of text, and its behavior becomes harder to reason about.

M6 introduces a **multi-agent architecture**:

- **Game Master** — narration and player interaction (existing, slimmed down)
- **Rules Referee** — applies game rules and validates actions
- **Inventory Keeper** — tracks and reports what the player carries
- **Lore Keeper** — maintains and queries `session_summary` and `last_scene`
- **Critic** — reviews the GM's output for consistency and tone

Each agent has a narrow responsibility and a short instruction set. The OpenAI
Agents SDK's agent-handoff mechanism routes work between them. `on_agent_start`
in the debug hooks (already wired in M5) will show which agent is acting on each
turn — the observability seam is already in place.

The `domain/` layer is unchanged in M6. Every rule, model, and persistence
function built in M1-M5 is the stable foundation the multi-agent layer runs on
top of. This is the payoff for the architectural discipline of keeping
deterministic logic in `domain/` and agent-touching code in `agents/` and `tools/`.

The new challenge in M6 is **inter-agent testing**: a Rules Referee that always
returns correct results in isolation may behave differently when handed off to by
a Game Master with a partial context. How do you test agent interactions, not just
each agent alone? That is the central design question M6 is meant to answer.
