# Milestone 2 — Deterministic Tools

> **Status:** Done
> **Theme:** Exact, verifiable outcomes belong in tested Python — not in the model's imagination.

---

## 1. Goal

M1 gave us a working agent loop. The Game Master can hold a conversation, but
every "fact" it mentions — including the result of a dice roll — is invented by
the model. That is fine for flavour text, but it's wrong for anything that must
be exact or auditable: a roll of the die, or the contents of a saved game.

M2's goal is to establish the rule that will govern the whole project:

> **The model decides *when* to act; tested Python decides *what* the result is.**

We do this by introducing two new architectural layers — `domain/` (pure Python,
zero SDK) and `tools/` (thin SDK wrappers) — and wiring three callable tools to
the Game Master: `roll_dice`, `save_game_state`, and `load_game_state`.

M2 also introduces **tool-call observability** (SDK hooks that surface each tool
invocation on the console), **free-text input clarification** (the prompt and
banner make clear the player can type in plain English, not just numbered
choices), and a **`help` meta-command** with honest milestone-scoped guidance.
Each of these is a deliberate design decision, not polish — and each maps
directly to patterns that matter in TestOps AI.

After M2, the agent is still the only agent (multi-agent arrives in M5), but it
can now take deterministic, reproducible, tested actions on the world.

---

## 2. What was built — point by point

### 2.1 `domain/dice.py` — dice rolling as enforced business logic

**What:** a single function `roll_dice(sides, *, rng=None) -> int` with two
named constants (`MIN_SIDES = 2`, `MAX_SIDES = 100`) and a custom exception
(`InvalidDiceError`). No SDK imports anywhere in the file.

**Why the dice tool exists — and why it feels "empty" right now.**

The model decides *when* chance matters: it is creative intelligence. But the
*number it produces* must be real and verifiable. If the model invented a dice
result, it could unconsciously bias outcomes — always giving the player a good
roll during exciting moments, always failing them when the story calls for
tension. More importantly, no test could ever catch that. The tool exists so
that the number has a known, testable, reproducible source.

Right now the dice feel lightweight because the *rules that make the number
matter* — attribute-based checks, damage formulas, skill thresholds,
consequences — do not exist yet. Attributes arrive in M3; rule-backed
resolution arrives in M4. The tool is built and waiting; the mechanics it will
plug into are the next two milestones. This is intentional sequencing: establish
the pattern before the content that uses it.

**Named constants, not magic numbers.** The bounds 2 and 100 are written as
`MIN_SIDES` and `MAX_SIDES` at the top of the module. Tests import those names
directly: `test_out_of_range_sides_are_rejected` uses `MAX_SIDES + 1` as one of
its parametrize values. If you later change the bound, the test automatically
tests the new limit — and if the prompt said "100" in plain English it would
never update. Business rules belong where they can be enforced and tested.

**Fail loudly (`InvalidDiceError`).** When `sides` is out of range or the wrong
type, the function raises immediately with an informative message. It never
silently returns a clamped value or ignores the bad input. This is *safe failure*
at the domain level: an impossible roll cannot produce a bogus-but-plausible
result that makes it into the game without anyone noticing.

**The `bool` trap.** Python's `bool` is a subclass of `int`, which means
`roll_dice(True)` would pass `isinstance(sides, int)` and be treated as
`sides = 1` — below `MIN_SIDES`, but silently mis-typed. The guard is explicit:

```python
if isinstance(sides, bool) or not isinstance(sides, int):
    raise InvalidDiceError(...)
```

This is the kind of edge case that a tester's instinct spots: what inputs look
valid but aren't?

**Dependency injection for reproducibility.** The `rng` parameter accepts a
`random.Random` instance. In production the caller omits it and gets true
randomness (`random` module global). In tests, a seeded instance is injected:
`random.Random(42)` gives the same sequence every time. Same code path, same
validation, completely predictable output under test. This is the dependency
injection pattern applied to randomness — a foundational idea for reproducible
testing.

### 2.2 `domain/state.py` — bounded, validated state persistence

**What:** two functions, `save_game_state(state_json, *, data_dir=None) -> str`
and `load_game_state(*, data_dir=None) -> str`, plus `StateError`, `DEFAULT_DATA_DIR`,
and `STATE_FILENAME`. No SDK imports.

The module resolves the project root relative to its own file location
(`Path(__file__).resolve().parents[3]`) and places saves in `data/game_state.json`
by default.

**Why each decision matters:**

**Bounded writes.** The save path is always resolved *inside* `data_dir`. There
is no parameter for choosing the file name or location. The agent can ask the
tool to save state; it cannot ask it to write anywhere else. This is the first
appearance of the guardrails thinking that M6 formalises: constrain the surface
area over which an agent has effect. A tool with a `path=` argument is a
footgun; a tool with no path argument is safer by construction.

**Validated content, both directions.** `save_game_state` parses the incoming
string with `json.loads` before writing — if it is not valid JSON, `StateError`
is raised and nothing reaches disk. `load_game_state` validates the content on
read too: a corrupt file that cannot be parsed raises rather than handing garbage
to the agent.

**Normalization on save.** After parsing, the data is re-serialized with
`json.dumps(parsed, indent=2, sort_keys=True)`. This normalizes formatting and
key order. The practical benefit: two saves of logically identical state produce
identical bytes on disk. That makes diffs human-readable and makes the
`test_save_normalizes_formatting` test meaningful (it asserts `"a"` appears
before `"b"` after saving `{"b": 2, "a": 1}`).

**Safe default on missing file.** `load_game_state` returns `"{}"` when the
state file does not exist yet. Callers — including the agent — never have to
handle a `FileNotFoundError`. A fresh game silently starts from an empty state.

**M2 scope decision — free-form JSON, not Pydantic.** The state in M2 is
whatever JSON the agent sends. This is intentional: strict typed models
(`Player`, `GameState`, etc.) are the subject of M3. Introducing Pydantic here
would mix two lessons. The comment in `state.py`'s module docstring makes the
boundary explicit: *"In M2 the state is free-form JSON (strict Pydantic models
arrive in Milestone 3)."*

**Injectable `data_dir` for test isolation.** The same injection pattern as
`rng` in `dice.py`: tests pass `tmp_path` (pytest's per-test temporary
directory) so they never touch the real `data/` folder and never interfere with
each other.

### 2.3 `domain/__init__.py` — the layer contract as a docstring

**What:** a module-level docstring that states the rule: *"Everything here is
unit-testable without an API key or the OpenAI Agents SDK. This is the code that
migrates cleanly to TestOps AI. Only `tools/` and `agents/` are allowed to
import the SDK; `domain/` never does."*

**Why it matters:** architecture rules that live only in a README are easy to
forget. Writing them where a developer sees them when they open the package makes
the constraint self-documenting.

### 2.4 `tools/game_tools.py` — the SDK bridge (thin wrappers only)

**What:** three functions decorated with `@function_tool` from the OpenAI Agents
SDK: `roll_dice`, `save_game_state`, and `load_game_state`. Each is a thin
wrapper around its `domain/` counterpart.

```python
@function_tool
def roll_dice(sides: int) -> str:
    """Roll a single die and return the result.

    Use this whenever the outcome of an action depends on chance (attacks,
    skill checks, random events). Never invent a dice result yourself — always
    call this tool so the number is real and fair.
    ...
    """
    try:
        value = dice.roll_dice(sides)
    except dice.InvalidDiceError as exc:
        return f"Invalid dice roll: {exc}"
    return f"Rolled a {value} on a {sides}-sided die."
```

**Why this split exists and matters:**

The `@function_tool` decorator is the only SDK-specific thing here. Everything
else — the validation, the bounds, the randomness, the file I/O — lives in
`domain/`. The tools layer does exactly three things: (1) gives the function a
tool identity the SDK can register, (2) provides the docstring the SDK shows the
model (the model reads this to decide when and how to call the tool), and (3)
converts domain exceptions into strings the model can read and react to.

This means the domain logic is fully unit-testable without the SDK installed,
and the tool wrappers are so thin they barely need their own tests. Thick wrappers
with embedded logic would force you to either test with the SDK present or skip
testing the logic at all.

**Docstrings as agent-facing instructions.** The `@function_tool` decorator uses
the Python docstring as the tool description exposed to the model. The phrase
*"Never invent a dice result yourself"* is not just for human readers — it is the
instruction the model receives when it sees the tool definition. Docstrings in the
tools layer serve two audiences at once.

**Exception-to-string conversion.** A domain exception propagating up through the
SDK would produce an unhelpful stack trace in the model's tool result. Converting
it to a plain string (e.g. `"Invalid dice roll: sides must be between 2 and 100,
got 1"`) gives the model something it can reason about and potentially relay to
the player.

### 2.5 `agents/game_master.py` — wiring the tools into the agent

**What:** `build_game_master` now imports the three tool functions and passes
them in `tools=[roll_dice, save_game_state, load_game_state]` to the `Agent`
constructor. `GAME_MASTER_INSTRUCTIONS` gained two rules:

- *"When an action depends on chance, call the `roll_dice` tool and narrate the
  result it returns. Never make up a dice number yourself."*
- *"You may use `save_game_state` to persist progress and `load_game_state` to
  resume a saved adventure."*

**Why it matters:** the instructions and the tool list reinforce each other.
The tool list makes the tools *available*; the instructions tell the model *when*
to use them and *why* it must not invent alternatives. Neither alone is sufficient:
a tool the model doesn't know about won't get called; an instruction without a
real tool produces an invented number anyway.

The tool imports happen inside `build_game_master` (lazily), keeping the same
pattern established in M1: importing `game_master.py` to read
`GAME_MASTER_INSTRUCTIONS` in a smoke test does not pull in the SDK.

**Verified in a real run.** During M2 development, the Game Master was observed
calling `roll_dice` in a live session. The tool return value — produced by
`domain/dice.py` — appeared in the model's narration. The model did not invent a
number; the number came from Python.

### 2.6 `main.py` — tool-call observability via SDK hooks

**What:** a new private function `_build_tool_hooks()` returns a `RunHooks`
subclass (`ToolActivityHooks`) with two async methods:

- `on_tool_start(context, agent, tool)` — prints `[dim][tool] calling roll_dice...[/dim]`
- `on_tool_end(context, agent, tool, result)` — prints `[dim][tool] roll_dice -> Rolled a 8 on a 20-sided die.[/dim]`

The instance is created once during startup and passed to every turn via
`Runner.run_sync(game_master, conversation, hooks=tool_hooks)`.

**Why hooks, not print statements in the tool itself.** The observability is in
`main.py`, not in `tools/game_tools.py`. This is deliberate: console output
concerns live in the console layer. The tool logic stays pure. Hooks are the
SDK's official *observability seam* — the runtime calls them at defined points
without any changes to the agent, the tool, or the runner. The mechanic is
unchanged; only the window into it is added.

This is not a cosmetic feature. Observability — knowing *which* tool was called,
with *which* arguments, and *what it returned* — is what makes an agent system
auditable. Without it, you see only the narrated output; you cannot distinguish
"the model invented a number" from "the tool returned a number the model
narrated." Hooks eliminate that ambiguity.

**Why `_build_tool_hooks()` is a function, not a module-level object.** The
`RunHooks` class comes from the SDK (`from agents import RunHooks`). If that
import happened at module level, importing `main.py` in any test would drag in
the SDK. Building hooks lazily inside a function keeps the module importable
without the SDK — consistent with the pattern in `game_master.py`.

**ASCII-only output in hooks — a real portability bug.** The docstring inside
`_build_tool_hooks` mentions an emoji (`🎲`) that was considered for the hook
output. It was removed. The reason is documented in the source comment:

> *"Plain ASCII markers on purpose: Windows' default console encoding (cp1252)
> can't encode emoji, and a raised `UnicodeEncodeError` inside a hook aborts the
> whole tool call."*

The actual output uses `[tool]` in square brackets — ASCII, portable everywhere.
The same encoding constraint applies to the help panel (see §2.7). This came
up twice during M2 development, both times causing a visible runtime failure
until the non-ASCII character was removed. The lesson belongs here, not buried
in a commit message: on Windows the console encoding is `cp1252` by default, not
UTF-8. Rich's console output goes through Python's stdout encoding. Any character
outside `cp1252`'s range raises `UnicodeEncodeError`. The safe rule: keep all
programmatic console output to printable ASCII and let Rich markup handle styling.

### 2.7 `main.py` — free-text input clarification, onboarding, and `help` command

**What:** three coordinated additions that address a real UX problem found during
playtesting: players treated the numbered choices the Game Master listed as a
strict menu, not realising they could type anything.

**Banner.** The startup panel now reads:

```
Dungeon Agents  -  a free-text fantasy adventure
Type help for how to play, or exit to quit.
```

**Input prompt.** The `console.input(...)` call now displays:

```
You (an action or a choice #):
```

The `(an action or a choice #)` qualifier is intentional — it makes the free-text
nature of the game visible on every single turn.

**`HELP_WORDS` and `_print_help()`.** The set `HELP_WORDS = {"help", "?", "/help"}`
is checked after `EXIT_WORDS` in the input loop. When matched, `_print_help()` is
called and the loop `continue`s — no game turn is consumed. Help is a meta-command,
not a player action.

**`HELP_TEXT` content and why it is honest.** The help panel (`HELP_TEXT`) covers:
- Free-text play and numbered choices (both work).
- The four meta-commands: `help`, `save`, `load`, `exit`.
- The dice: explains that a `[tool] roll_dice -> ...` line means a real number
  was generated by tested code, not invented.
- A "note on the character sheet": any attributes shown (hp, gold, reputation...)
  are narrative flavour the storyteller improvises — not enforced by game rules.
  Real rule-backed attributes and inventory arrive in M3/M4.

The honesty note is intentional. Over-promising ("your stats matter") when the
mechanics do not yet exist erodes trust. A player who understands the current
scope can enjoy what is there. This is the documentation-as-expectation-setting
principle applied inside the running game.

**`HELP_TEXT` is ASCII-only — for the same reason as the hooks.** The text
originally included curly quotes, em dashes, and arrow characters. These caused
`UnicodeEncodeError` on Windows' `cp1252` console. All were replaced with ASCII
equivalents. The comment in the source makes this explicit:

> *"NOTE: ASCII only — Windows' default console encoding (cp1252) can't render
> curly quotes, em dashes, or arrows, and Rich raises on them. Keep it portable."*

**Help shows once at startup automatically.** After the banner, `_print_help()`
is called unconditionally. A new player never has to discover the `help` command
to understand how to play.

### 2.8 Tests — `test_dice.py` (12 cases) and `test_state.py` (6 cases)

**What:** two new test modules, both deterministic (no API key, no SDK, no
network). The full suite is now 26 tests: 8 smoke (M1) + 12 dice + 6 state.

**`test_dice.py` — what is covered and why:**

| Test | What it verifies | Why |
|------|-----------------|-----|
| `test_roll_is_within_bounds` | 1000 rolls on a d20 land in `[1, 20]` | Statistical confidence; one sample could get lucky |
| `test_roll_is_reproducible_with_seeded_rng` | Same seed -> same value | The injection pattern works; reproducibility is real |
| `test_min_and_max_sides_are_allowed` | `roll_dice(2)` and `roll_dice(100)` succeed | Boundary testing; off-by-one errors live at edges |
| `test_out_of_range_sides_are_rejected` | `1, 0, -5, 101, 1000` raise `InvalidDiceError` | Parametrized boundary + outside cases |
| `test_non_integer_sides_are_rejected` | `2.0, "20", None, True` raise `InvalidDiceError` | Type safety, including the `bool` trap |

The parametrize decorators on the last two functions expand to 5 + 4 = 9
additional test cases, giving 12 total from 5 function definitions.

**`test_state.py` — what is covered and why:**

| Test | What it verifies | Why |
|------|-----------------|-----|
| `test_save_then_load_roundtrips` | Save -> load returns same content | The core contract |
| `test_load_with_no_save_returns_empty_object` | Returns `"{}"` on first run | Safe default; no `FileNotFoundError` |
| `test_save_creates_the_file_in_the_data_dir` | File appears at `tmp_path/game_state.json` | Confirms the right path is used |
| `test_save_rejects_invalid_json` | Bad JSON raises `StateError`, no file written | Safe failure; nothing partial reaches disk |
| `test_load_rejects_corrupt_save` | Corrupt file raises `StateError` | Read-time validation works |
| `test_save_normalizes_formatting` | Keys are sorted on disk | Normalization is active |

Every test injects `tmp_path` as `data_dir`, so they never touch `data/` and
never depend on each other's side effects.

---

## 3. Concepts learned in M2

| Concept | Where it showed up | Why it transfers |
|---------|-------------------|-----------------|
| LLM orchestrates, Python executes | `roll_dice` in domain, called via tool | The model decides *when*; the code decides *what*. Core agentic pattern. |
| Layered architecture | `domain/` -> `tools/` -> `agents/` | Each layer has one job; only the right layers touch the SDK. |
| Dependency injection for reproducibility | `rng=` in `roll_dice`, `data_dir=` in state functions | Controllable inputs = reproducible tests. Applies to any side effect. |
| Bounded writes | `save_game_state` with no path parameter | Constrain what a tool *can* do, not just what it *should* do. |
| Validated content (in and out) | JSON parse on save and on load | Never let bad data reach the next layer silently. |
| Exception-to-string at the boundary | Tool wrappers catch domain exceptions | The SDK boundary is where you translate errors for non-Python consumers. |
| Docstrings as agent instructions | Tool docstrings shown to the model | One docstring, two audiences: developers and the model. |
| Named constants over magic numbers | `MIN_SIDES`, `MAX_SIDES` | Testable, refactorable, self-documenting. |
| SDK observability hooks | `RunHooks` subclass in `main.py` | Audit what the agent does without changing what it does. |
| Lazy SDK imports | `_build_tool_hooks()` is a function, not a module attribute | Keeps `main.py` importable without the SDK; consistent with `game_master.py`. |

---

## 4. QA mindset in M2

M2 deepens the QA themes introduced in M1:

**Reproducibility, for real.** M1 kept config immutable. M2 goes further:
randomness and file I/O are now injectable, so any test can control any source of
non-determinism. A test that cannot be run twice with the same result is not a
reliable test.

**Safe failure at every boundary.** Invalid dice sides -> `InvalidDiceError`.
Non-JSON state -> `StateError` before disk write. Corrupt save -> `StateError` on
read. At no point does bad input silently produce a plausible-looking wrong
result. This is the property that makes a system auditable: failures are loud and
early, not quiet and late.

**Testability through constraint.** The domain layer has zero SDK dependency by
design, not by accident. That choice is what allows `python -m pytest -m "not llm"`
to run 26 tests in a few seconds with no API key. Every architectural constraint
that isolates a layer makes that layer cheaper and faster to test.

**The boolean subclass trap as a tester's instinct.** The `isinstance(sides, bool)`
guard exists because a tester asks: *what inputs look valid but aren't?* `True`
is an `int` in Python. `roll_dice(True)` would pass type-checking and reach the
range check — where it would fail anyway (`1 < MIN_SIDES`), but for the wrong
reason and with a misleading error. Catching it explicitly at the type gate is
both more correct and more communicative.

**Boundary testing.** `test_min_and_max_sides_are_allowed` verifies that `2` and
`100` are accepted; `test_out_of_range_sides_are_rejected` verifies that `1` and
`101` are not. Testing the boundary on both sides is the standard practice for
any range-checked value.

**Observability as a QA property.** The SDK hooks in `main.py` are not
user-visible game features — they are a debugging and audit layer. In any
production system, knowing that a tool was called, with what input, and what it
returned is as important as the result itself. Hooks are the mechanism here;
structured logging, traces, and spans are the production equivalents.

**Windows encoding as a portability test case.** The `UnicodeEncodeError`
failures during M2 development are a recurring, real class of portability bug.
The lesson: any output path that might reach a Windows terminal with `cp1252`
encoding must be tested on that platform or defensively written to ASCII only.
The failure mode is silent during development on macOS/Linux (UTF-8 default) and
loud at runtime on Windows. This is exactly the kind of environment-specific
failure that a QA mindset anticipates: *does this work on the platforms our users
have, not just the platform I develop on?*

---

## 5. How to test / verify it yourself

```bash
# Inside an activated .venv with `pip install -e ".[dev]"` already run:

# Full deterministic suite (26 tests, no API key needed):
python -m pytest -m "not llm" -q
# Expected: 26 passed

# Run just the new M2 tests:
python -m pytest tests/test_dice.py tests/test_state.py -v

# See the seeded-RNG reproducibility yourself:
python -c "
import random
from dungeon_agents.domain.dice import roll_dice
a = roll_dice(20, rng=random.Random(42))
b = roll_dice(20, rng=random.Random(42))
print(a, b, a == b)   # same number twice, then True
"

# Confirm a bad input fails loudly:
python -c "
from dungeon_agents.domain.dice import roll_dice
roll_dice(True)   # should raise InvalidDiceError
"

# Full run (needs an API key) — observe the agent calling roll_dice:
dungeon-agents
# 1. Read the help panel that appears at startup.
# 2. Try typing a free-text action: "I search the room for a hidden door".
#    You are not limited to numbered choices.
# 3. Try an action that depends on chance: "I swing my sword at the goblin".
#    Watch for a dim [tool] calling roll_dice... / [tool] roll_dice -> ... line.
#    That number came from Python, not from the model's imagination.
# 4. Type 'help' at any time to re-read the help panel (no game turn consumed).
# 5. Type 'exit' to quit.
# Note: first launch takes ~20 seconds (SDK import). A spinner shows.
```

---

## 6. Risks & tradeoffs

**Free-form JSON state (deferred schema).** `state.py` validates that the agent's
output is parseable JSON, but it does not validate its *structure*. The agent
could save `{"anything": "goes"}`. This is intentional: Pydantic models with
explicit field definitions are M3's topic. Mixing them into M2 would conflate two
separate lessons. The risk is that M2's save files are structurally unconstrained;
the mitigation is that M3 immediately replaces this with typed models.

**No tool-call tests.** `tools/game_tools.py` is not directly unit-tested: doing
so would require the SDK, which breaks the "no API key" constraint. The domain
functions it wraps are thoroughly tested. The thin wrapper logic (exception
conversion, string formatting) is simple enough that the risk is low — but it is
a gap. Integration-level tests in M7 will cover the full tool-call round-trip.

**Single save slot.** `game_state.json` is one file. A second save overwrites the
first. For a learning demo this is fine; a real product would need namespaced
saves or a database. Noted here so future milestones don't design around the
assumption of one slot.

**Conversation still grows unbounded.** Inherited from M1. Game state is now
persistent, but the in-memory conversation history still accumulates indefinitely.
The Lore Keeper agent in M5 addresses this.

**Dice mechanics without rules.** The `roll_dice` tool works and the observability
hooks show it being called. But until M3 adds typed attributes and M4 adds
rule-based resolution, the number the tool returns has no mechanical effect —
the model narrates around it. This is not a defect; it is the intended sequencing.
It is worth stating here so the learning arc is clear: build the infrastructure
first, then build the rules that use it.

**Windows encoding portability.** Any console output that contains characters
outside ASCII must be tested on Windows (`cp1252`). The current code uses ASCII
only in all programmatic output (hooks, help text, banners). If a future
contributor adds styled text with curly quotes, em dashes, or emoji to any
`console.print(...)` call, they should verify it on Windows or replace the
characters with ASCII equivalents. The docstring in `_build_tool_hooks()` and
the `HELP_TEXT` comment both carry this warning.

---

## 7. Bridge to TestOps AI

The M2 pattern — *LLM orchestrates, Python executes* — is not a game-specific
design. It is the template for every tool-augmented agent, including those in a
QA/testing product. Each piece of M2 maps directly:

### The dice pattern: "AI decides when, code decides what"

In Dungeon Agents, the model decides that a goblin attack *warrants* a dice roll.
The `roll_dice` tool produces the number. The model narrates the consequence. The
model never invents the number; the code never decides whether the situation calls
for a roll.

In TestOps AI, the analogue is direct: a QA agent decides *what to test* (which
test cases, which coverage gaps, which risk areas — creative intelligence). But
the *result of each test* must come from the test runner, not from the model's
assessment. A QA agent must never hallucinate that a test passed. A hallucinated
pass ships broken software. The same structural rule — verifiable outcomes belong
in code — is the reason `roll_dice` exists in this form.

### Observability (hooks) maps to audit trails

The SDK hooks that print `[tool] roll_dice -> ...` in the game console are a
minimal form of what every production agent system needs: an audit trail. You
need to know which tool was called, with what, and what it returned — separate
from what the model said about it.

In TestOps AI, this is even more critical. If a QA agent tells you "all tests
passed," you need to verify that each test actually *ran* and that the result
came from the test runner. Hooks (or their production equivalents: structured
logs, traces, spans) are the mechanism. M2 introduces the concept at its
simplest; M7 formalises evaluation against real expected outputs.

### The full mapping

| Dungeon Agents (M2) | TestOps AI |
|---------------------|-----------|
| `roll_dice` — deterministic outcome the model must not invent | Test result evaluation — pass/fail must come from the runner, not the model |
| `save_game_state` / `load_game_state` — bounded, validated persistence | Test run storage — agent triggers a save; it cannot choose where or in what format |
| `domain/` layer — pure Python, no SDK | Core QA logic — assertions, comparators, result parsers — testable without an LLM |
| `tools/` layer — thin SDK wrappers | Tool adapters — expose QA primitives to the orchestrating agent |
| `InvalidDiceError` / `StateError` — loud, early failures | Assertion errors that surface immediately, not silently swallowed |
| SDK hooks in `main.py` | Audit log / trace of agent tool calls, independent of what the agent narrates |
| Help text with honest milestone scope | Documentation that sets accurate expectations, does not over-promise |

The dependency injection pattern (`rng=`, `data_dir=`) also transfers directly:
in TestOps AI you inject the test runner, the file system, and the clock wherever
a tool interacts with the external world, so any test can control any side effect.

The domain layer is the code that migrates cleanly. Because `domain/` has zero SDK
dependency, it can be extracted into a shared library used by both Dungeon Agents
and TestOps AI without carrying any agent framework along with it.

---

## 8. What's next — Milestone 3: domain models

M2's `save_game_state` accepts any valid JSON. That means the agent can save
`{"player": "alive"}` or `{"hp": "lots"}` or any other structurally arbitrary
blob — and the code will dutifully persist it. The `roll_dice` tool produces a
number, but there are no attributes to check it against and no rules that
translate it into a consequence.

M3 introduces **Pydantic models** in `domain/`: `Player`, `GameState`,
`InventoryItem`, `Quest`, `ActionResult`. These replace free-form JSON with
typed, validated structures that enforce what the state *must* contain, what types
each field must be, and what values are out of range. The lesson: a validated
schema is a machine-checkable specification. Not only does it prevent bad data
from entering the system — it also documents the data contract in a way that
tests can assert against.

After M3, `save_game_state` will serialize a `GameState` object, not a raw
string. The tool wrapper in `tools/` will change; the domain persistence logic in
`state.py` will get stricter; and the tests will be able to assert on field-level
correctness, not just JSON parseability. And crucially, the dice rolls that M2
introduced will have typed attributes to check against — turning the tool from a
working-but-inert mechanism into a real part of the game engine.
