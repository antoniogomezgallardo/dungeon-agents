# Milestone 3 — Domain Models

> **Status:** Done
> **Theme:** A validated schema is a machine-checkable specification — invalid state cannot be built, saved, or loaded silently.

---

## 1. Goal

M2 left a gap. The `save_game_state` tool accepts any JSON the agent sends — it
could be `{"hp": "lots"}` or `{"player": "alive"}` and the code would dutifully
write it to disk. The `roll_dice` tool produces a real number, but there are no
typed attributes to check it against and no consequence attached to the result.
The game has infrastructure without a data contract.

M3 closes that gap by introducing **Pydantic domain models** in `domain/models.py`:
five pure-Python classes that define, in code, exactly what the game state must
look like — which fields exist, their types, and their bounds. Once those models
exist, the persistence layer can validate against them: a save that violates the
schema is rejected, and a load that produces invalid data raises immediately.

The milestone has one acceptance criterion that drives every decision:

> **Invalid state cannot be built, saved, or loaded silently.**

The word "silently" is load-bearing. The system was already rejecting some bad
input (non-JSON blobs at M2). M3 demands deeper validation: a save file that is
syntactically valid JSON but has `"hp": -50` must also fail — loudly — rather than
being accepted as plausible game state.

This document explains what was built, why each choice was made the way it was,
and how the whole design connects to the TestOps AI patterns these milestones exist
to teach.

---

## 2. What was built — point by point

### 2.1 `domain/models.py` — five models, one data contract

**What:** a new file, `src/dungeon_agents/domain/models.py`, containing five
Pydantic models and one named constant.

```
MAX_HP = 100

InventoryItem   (name, quantity)
Player          (name, hp, max_hp, gold)
Quest           (title, description, completed)
GameState       (player, inventory, location, active_quest, session_summary)
ActionResult    (success, message, new_state)
```

**Why Pydantic — and not something simpler.**

A Pydantic model is a Python class that declares its fields using type annotations
and `Field(...)` constraints, and validates every new instance automatically. You
never call a `validate()` method yourself; validation happens the moment you write
`Player(name="Aria", hp=-10)` — Pydantic raises a `ValidationError` before the
object is constructed.

The alternative would be writing guard statements in every function that touches
the state: `if hp < 0: raise ...`, `if len(name) == 0: raise ...`. That approach
works at small scale but spreads the validation logic across the codebase. Every
new path that constructs a player must remember to re-check every invariant.
Pydantic centralizes the contract on the class itself: the rules are where the
data is defined, not scattered at each call site.

**Why `MAX_HP` is a named constant, not the literal `100`.**

```python
# domain/models.py:24
MAX_HP = 100
```

The hp bounds appear twice in `Player`:

```python
hp: int = Field(default=MAX_HP, ge=0, le=MAX_HP, ...)
max_hp: int = Field(default=MAX_HP, ge=1, le=MAX_HP, ...)
```

If `MAX_HP` were written as `100` in both places, changing the cap would require
finding every occurrence. More importantly, tests would have to hard-code `100`
too — coupling them to a value rather than an intent. With `MAX_HP` as a named
constant, tests `import MAX_HP` and write `Player(name="X", hp=MAX_HP + 1)` — the
test automatically covers the new boundary if the cap changes. This is the same
pattern as `MIN_SIDES`/`MAX_SIDES` in M2's `dice.py`: business bounds belong as
testable names, not magic numbers.

### 2.2 `InventoryItem` — the simplest constraint is still a constraint

```python
class InventoryItem(BaseModel):
    name: str = Field(min_length=1, ...)
    quantity: int = Field(ge=1, ...)
```

**Why `quantity >= 1` and not `>= 0`.** An item with a quantity of zero is not in
the inventory at all — it has been used up or sold. Representing it as an
`InventoryItem(name="Torch", quantity=0)` would be a bug: it implies a slot is
occupied by something that does not exist. The model refuses to build it. If the
quantity drops to zero, the item should be removed from the inventory list; an
`InventoryItem` with `quantity=0` is a meaningless state, and the schema prevents
it from existing in the first place.

**Why `name` has `min_length=1` and not a `name is not None` check.** Pydantic
requires type annotations, and `str` already excludes `None`. The `min_length=1`
constraint adds the additional rule that an empty string is not a valid item name.
An item with no name is a data error — likely a bug in whatever code constructed
it — and the earlier it is caught, the cleaner the failure.

### 2.3 `Player` — encoding gameplay invariants as field constraints

```python
class Player(BaseModel):
    name: str = Field(min_length=1, ...)
    hp: int = Field(default=MAX_HP, ge=0, le=MAX_HP, ...)
    max_hp: int = Field(default=MAX_HP, ge=1, le=MAX_HP, ...)
    gold: int = Field(default=0, ge=0, ...)
```

**hp is clamped to `[0, MAX_HP]`.** A character at 0 hp is dead; a character at
negative hp is a fiction that the data layer has no business representing. A
character at `hp > MAX_HP` is equally impossible — you cannot be "more than fully
healed." Both ends of the range are wrong for different reasons, and the `ge=0,
le=MAX_HP` constraint expresses both at once.

**gold cannot go negative.** The constraint `ge=0` encodes the rule that you
cannot owe gold — the state can never represent a debt. Whether the player can
*afford* a purchase (and what happens when they can't) is a game rule for M4.
That is a behavioral question. What M3 encodes is the invariant: the gold field is
a non-negative count of coins. A spending check that would put gold below zero
should be rejected by M4's rule layer *before* attempting to construct a Player
with negative gold.

**`max_hp` has `ge=1` not `ge=0`.** A max_hp of 0 would mean the player can never
have any hp at all, which is not a meaningful character state. The lower bound of 1
reflects the rule that a character always has at least some maximum health, even if
their current hp is 0.

**Defaults are not optional.** `hp` defaults to `MAX_HP` (fully healed), `gold`
defaults to `0` (penniless), and `max_hp` defaults to `MAX_HP`. A new character
starts alive and broke — which is the right game assumption. These defaults also
mean that `Player(name="Aria")` is a valid call with exactly one argument; tests
and in-game code do not need to specify every field every time.

### 2.4 `Quest` — data now, rules in M4

```python
class Quest(BaseModel):
    title: str = Field(min_length=1, ...)
    description: str = Field(default="", ...)
    completed: bool = Field(default=False, ...)
```

**Why `Quest` is data-only in M3.** A quest has a title, an optional description,
and a flag that marks it done. That is all. The *rules* that decide when a quest
is fulfilled — what event sets `completed = True`, what happens to the player when
it does, what constitutes a win condition — are deliberately absent.

This is milestone sequencing working as intended. M3's job is to establish the
validated data shape that M4's rules will attach to. If M3 tried to encode quest
completion logic, it would be working outside its scope and would likely produce
rules that conflict with whatever M4 designs. By defining the shape and deferring
the behavior, M3 gives M4 a stable, validated structure to reason about.

The analogy in QA terms: defining a `Quest` is like writing the schema for a user
story. The story has a title and a description. Whether the acceptance criteria are
met is a question the CI pipeline answers at run time, not a question the data type
can answer by itself.

### 2.5 `GameState` — the container and validation cascade

```python
class GameState(BaseModel):
    player: Player
    inventory: list[InventoryItem] = Field(default_factory=list, ...)
    location: str = Field(default="unknown", ...)
    active_quest: Quest | None = Field(default=None, ...)
    session_summary: str = Field(default="", ...)
```

`GameState` is the "outer" model that nests the others. Understanding what this
nesting does is central to M3.

**Validation cascades through nested models.** When you write:

```python
GameState(player={"name": "X", "hp": -99})
```

you are passing a raw dict, not a pre-built `Player`. Pydantic coerces the dict
into a `Player` and, in doing so, applies `Player`'s constraints. The negative hp
fails validation. The `GameState` is never constructed — one bad field in a nested
model invalidates the whole tree.

The same cascade applies to `inventory`:

```python
GameState(
    player=Player(name="Aria"),
    inventory=[{"name": "Torch", "quantity": 0}]
)
```

Pydantic coerces each dict in the list to an `InventoryItem`. `quantity=0` fails
the `ge=1` constraint. The entire `GameState` construction fails, not just the
item. There is no partial-valid state where the player is fine but the inventory
is corrupt. This is the M3 acceptance criterion expressed mechanically.

**Why `active_quest` is `Quest | None` with a `None` default.** A fresh game may
have no quest yet — the player just arrived at the tavern, nothing has been
assigned. `None` is the correct representation of "no quest," and `Optional[Quest]`
is more honest than an empty-quest placeholder. Checking `state.active_quest is
None` is unambiguous; checking whether a "placeholder" quest has an empty title is
fragile. Optional fields in Pydantic default to `None` when `default=None` is set,
so `GameState(player=...)` with no quest argument constructs cleanly.

**`session_summary` is carried by state.** The Lore Keeper agent (M5) will
maintain a concise running recap of the session. For now, `session_summary` is
just a string the state carries — no agent reads it yet. It is defined here so M5
has a validated field to write to rather than inventing its own key in a free-form
dict.

### 2.6 `ActionResult` — the return type for game rules

```python
class ActionResult(BaseModel):
    success: bool = Field(description="Did the action succeed?")
    message: str = Field(default="", ...)
    new_state: GameState | None = Field(default=None, ...)
```

`ActionResult` is the future return type for M4's rule functions. It is defined
in M3 because the shape of a rule's output is a design decision, and getting it
wrong makes M4 harder to write.

**`success` has no default.** Every other field has a default. `success` does not.
This is deliberate: a result object where you forgot to specify whether the action
succeeded is a bug, and it should fail at construction time. If `success` had a
default of `False`, a test that accidentally omitted it would silently look like a
failure rather than an error.

This is a small but instructive principle: **the absence of a default is itself
an assertion** — you are saying "this field is required and there is no safe
fallback." The test `test_action_result_requires_success_flag` asserts exactly
this: `ActionResult(message="no flag given")` raises `ValidationError`.

**Why carry `new_state` instead of mutating in place.** A rule function in M4
that takes a `GameState` and returns an `ActionResult` is a pure function: given
the same state and the same action, it returns the same result. It does not modify
the state it received. The new state (if any) lives in `result.new_state`.

This makes rules easy to test: no setup, no teardown, no shared mutable state.
You pass in a state, you get back a result, you assert on the result. If you want
to verify that buying a torch reduces gold by 5, you call the rule with a player
who has 10 gold and check that `result.new_state.player.gold == 5`. The original
state is unchanged and can be inspected independently. This pattern — functions
that return new state rather than mutating existing state — is a foundational idea
in both functional programming and in testing.

### 2.7 `state.py` — Pydantic-validated persistence alongside M2 raw-JSON functions

**What:** `src/dungeon_agents/domain/state.py` gained two new functions at the
bottom of the file:

- `save_state(state: GameState, *, data_dir=None) -> str`
- `load_state(*, data_dir=None) -> GameState | None`

The M2 functions (`save_game_state`, `load_game_state`) were left unchanged.

**Why the M2 functions were kept.**

`save_game_state` and `load_game_state` are registered as tools in
`tools/game_tools.py` and wired into the Game Master in `agents/game_master.py`.
Those tools work with raw JSON strings, which is what the SDK passes back and
forth at M2. Replacing the underlying functions would change their signatures,
break the tools, and force a rewrite of code that M3 does not touch.

Instead, M3 adds alongside without removing. The two new functions share the same
file, the same bounded-path logic, and the same safe data directory — but they
work with validated `GameState` objects:

- `save_state` receives a `GameState` that is already valid by construction
  (Pydantic would have refused to build an invalid one) and serializes it with
  `model_dump_json(indent=2)`.
- `load_state` reads the file, calls `GameState.model_validate_json(raw)`, and
  raises `StateError` if the JSON does not match the schema.

This "add without breaking" pattern is a recurring engineering discipline: when
introducing a new abstraction, keep the existing one working until all callers are
migrated. M4 will migrate the agent tools to use the typed functions; M3 defines
them.

**Why `load_state` returns `GameState | None` instead of raising on missing file.**

`load_game_state` (M2) returns `"{}"` for a missing file — a safe default string
that means "fresh game." `load_state` returns `None` for the same case, because
`None` is the idiomatic Python way to signal "nothing here yet" when the return
type is an object, not a string. An empty GameState would require inventing a
player name; `None` makes the "no save" case unambiguous without fabricating data.
The calling code checks `if state is None: # start fresh game`.

**The `StateError` distinction: schema mismatch vs. JSON corruption.**

The M2 `load_game_state` raises `StateError` on corrupt JSON. The M3 `load_state`
raises `StateError` on two distinct problems:

1. The file is corrupt JSON (Pydantic raises `json.JSONDecodeError` internally).
2. The file is valid JSON but violates the `GameState` schema (Pydantic raises
   `ValidationError`).

Both are surfaced as `StateError`. The string inside the exception carries the
Pydantic validation details — the field path, the value, and the constraint that
failed — so the developer can diagnose what went wrong. From the caller's point of
view, the rule is the same in both cases: a save file that cannot be loaded as a
valid `GameState` fails loudly.

### 2.8 Tests — `test_models.py` (20 cases) and `test_state.py` (3 new cases)

**What:** a new file `tests/test_models.py` (20 deterministic tests) and three
new test functions at the bottom of `tests/test_state.py`. The total suite is
now **49 tests** (8 smoke + 12 dice + 9 state + 20 models), all passing without
an API key.

**`test_models.py` coverage:**

| Group | Key tests | What they verify |
|-------|-----------|-----------------|
| `InventoryItem` | valid construction, `quantity < 1`, empty name | Happy path + two bad-value rejections |
| `Player` | defaults, custom values, `@pytest.mark.parametrize` with 4 invalid kwargs, wrong types | Each invalid axis (hp, gold, name, type) has its own case |
| `Quest` | defaults, empty title | Minimal model, one constraint |
| `GameState` | minimal (only player), full nested tree, invalid nested player, invalid nested item | Container validation and cascade |
| `ActionResult` | success minimal, failure with message, carries new_state, missing success flag | All meaningful states + required-field enforcement |

The `@pytest.mark.parametrize` on `test_player_rejects_invalid_state` is worth
examining. It specifies four invalid kwargs dicts:

```python
@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "X", "hp": -1},         # hp below 0
        {"name": "X", "hp": MAX_HP + 1}, # hp above max
        {"name": "X", "gold": -5},       # negative gold
        {"name": ""},                     # empty name
    ],
)
def test_player_rejects_invalid_state(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        Player(**kwargs)
```

This produces four separate test cases — `kwargs0` through `kwargs3` — in pytest's
output. Each covers a different invalid axis. Parametrize is the right tool here
because all four cases have identical logic (construct → expect `ValidationError`)
but different data. Writing four separate `def test_` functions would work, but
parametrize makes the pattern explicit and makes adding a fifth case a one-line
change.

**Note on `model_construct()` — a real gotcha the tests caught.**

During M3 development, `model_construct()` — Pydantic's bypass method that builds
a model without running validators — appeared in a test that was then fixed. It is
worth understanding why it exists and why using it in tests usually defeats the
purpose.

`model_construct()` is Pydantic's escape hatch for performance-sensitive cases
where you know the data is already valid (e.g. data coming directly from a
trusted database). It skips all field validators, including `ge`, `le`, and
`min_length`. A call like `Player.model_construct(name="X", hp=-99)` will succeed
and return a `Player` with an invalid hp, because the constraint was never checked.

In a test that is supposed to verify that `Player(name="X", hp=-99)` raises
`ValidationError`, using `model_construct()` would produce a false pass — the test
would construct the object successfully and then never see the error it was
supposed to verify. The fix is to always use the normal constructor in tests that
are verifying validation behavior.

The lesson is general: always know whether you are testing the validated or the
unvalidated path, and use the constructor that corresponds to what you intend.

**`test_state.py` new tests (M3 section):**

| Test | What it verifies |
|------|-----------------|
| `test_save_state_then_load_state_roundtrips` | A `GameState` saved and reloaded comes back value-equal (`==` on Pydantic models compares fields) |
| `test_load_state_with_no_save_returns_none` | No file → `None`, not a crash |
| `test_load_state_rejects_schema_mismatch` | Valid JSON with `"hp": -50` → `StateError` (the M3 acceptance criterion) |

The roundtrip test uses Pydantic's value equality — two `GameState` instances with
identical field values are equal even if they are different Python objects. This is
the same semantics as value types in other languages: equality is about content,
not identity.

---

## 3. Concepts learned in M3

| Concept | Where it showed up | Why it transfers |
|---------|------------------|-----------------|
| Data contract as code | `Field(ge=..., le=..., min_length=...)` on each model | Constraints that are testable, diffable, and executable — not just prose in a README |
| Validation cascade | Nested model in `GameState` invalidates the whole tree | One bad field anywhere in the state graph fails the whole state — no partial-valid objects |
| Named constants for bounds | `MAX_HP` imported in tests | Testable names over magic numbers; tests stay correct when bounds change |
| No-default as a required signal | `success: bool = Field(...)` with no `default=` | Absence of a default is itself an assertion: this field is required |
| Add without breaking | `save_state` / `load_state` alongside M2 functions | Introduces new abstraction without changing existing callers |
| `model_construct()` vs normal construction | Gotcha in tests | `model_construct` bypasses validators; only use it when you explicitly want unvalidated data |
| Value equality on models | `loaded == original` in roundtrip test | Pydantic models compare by field values, not object identity |
| Optional nesting vs. placeholder | `active_quest: Quest \| None` | `None` is unambiguous for "no quest yet"; a placeholder requires fragile empty-check conventions |
| Functional result objects | `ActionResult.new_state` instead of mutation | Pure functions that return new state are easier to test than mutating methods |

---

## 4. QA mindset in M3

**Schema validation is executable specification.** In M2 the game state's
structure was implicit — implied by the agent's behavior and the help text's
"honesty note." A developer reading the codebase had to infer that `hp` was a
number and that it shouldn't go negative. In M3, those rules are in code, checked
automatically, and reported on violation with the field name and the failed
constraint. The schema is the specification, and Pydantic enforces it on every
object construction.

**The acceptance criterion is a test.** "Invalid state cannot be loaded silently"
is not just a goal in the milestone brief — it is `test_load_state_rejects_schema_mismatch`.
The test writes a file with `"hp": -50`, calls `load_state`, and asserts
`StateError` is raised. If the code stopped rejecting invalid state, the test would
fail. This is traceability working in the M3 direction: requirement → schema
constraint → test that verifies the constraint is enforced on load.

**Validation at every boundary: in and out.** M2 validated that the content being
saved was parseable JSON. M3 extends this: the content must also match the
`GameState` schema. Both directions are covered — `save_state` receives a
`GameState` already validated by Pydantic, and `load_state` validates the schema
when reading. Nothing invalid can enter the system from either direction.

**Cascade as defense in depth.** Each model validates itself. `GameState`
validates its nested models. A caller who constructs a `GameState` from raw dicts
(which is the pattern in tests that verify rejection) triggers validation at every
level of the tree in a single call. There is no way to slip a bad `InventoryItem`
into a `GameState` that otherwise looks valid.

**Required fields as preconditions.** `success: bool` with no default in
`ActionResult` is a precondition enforcement: no rule function can return an
`ActionResult` without explicitly stating whether the action succeeded. Forgetting
to set it is not a silent bug — it is an immediate construction error. The earlier
a mistake is caught, the smaller its blast radius.

---

## 5. How to test / verify it yourself

```bash
# Inside an activated .venv with `pip install -e ".[dev]"` already run:

# Full deterministic suite (49 tests, no API key needed):
python -m pytest -m "not llm" -q
# Expected: 49 passed

# Run just the new M3 tests:
python -m pytest tests/test_models.py tests/test_state.py -v

# See validation in action at the Python REPL:
python -c "
from dungeon_agents.domain.models import Player, MAX_HP
from pydantic import ValidationError

# Valid construction:
hero = Player(name='Aria')
print(hero.hp, hero.gold)   # 100 0

# Out-of-range hp raises immediately:
try:
    Player(name='X', hp=-10)
except ValidationError as e:
    print('Caught:', e.errors()[0]['msg'])

# hp above MAX_HP also fails:
try:
    Player(name='X', hp=MAX_HP + 1)
except ValidationError as e:
    print('Caught:', e.errors()[0]['msg'])
"

# See cascade validation:
python -c "
from dungeon_agents.domain.models import GameState, Player
from pydantic import ValidationError

try:
    GameState(player={'name': 'X', 'hp': -99})
except ValidationError as e:
    # Shows the field path through the nested model
    print(e.errors()[0]['loc'], e.errors()[0]['msg'])
"

# See validated persistence:
python -c "
import tempfile, pathlib
from dungeon_agents.domain.models import GameState, Player
from dungeon_agents.domain.state import save_state, load_state, StateError

with tempfile.TemporaryDirectory() as d:
    data_dir = pathlib.Path(d)
    original = GameState(player=Player(name='Aria', hp=30, gold=7), location='tavern')
    save_state(original, data_dir=data_dir)
    loaded = load_state(data_dir=data_dir)
    print('Equal:', loaded == original)   # True

    # Write an invalid file and try to load it:
    (data_dir / 'game_state.json').write_text('{\"player\": {\"name\": \"X\", \"hp\": -50}}')
    try:
        load_state(data_dir=data_dir)
    except StateError as e:
        print('Rejected:', str(e)[:60])
"
```

**Expected results:**

- `49 passed` from the full deterministic suite.
- The REPL examples raise `ValidationError` on bad input and print `True` for the
  roundtrip equality check.
- The invalid-load example prints `Rejected:` followed by the schema mismatch
  detail from Pydantic.

---

## 6. Risks & tradeoffs

**`save_state` / `load_state` are not yet wired to the agent tools.**
The M2 tools (`save_game_state`, `load_game_state`) are still active in
`tools/game_tools.py`. They work with raw JSON strings. The validated functions
exist in `domain/state.py` but no tool calls them yet. The agent can still save
structurally arbitrary JSON through the M2 path. M4 will migrate the tools to the
validated path; M3 establishes the target abstraction without completing the
migration.

**Quest is data only — win condition is undefined.**
A `Quest` with `completed = True` is just a flag in the data. Nothing happens when
it flips. The rule that triggers completion, the check that evaluates whether the
player's actions fulfill the quest, and the win condition are all M4 work. M3
defines the validated shape so M4 has somewhere to attach the logic.

**Dice still "don't matter" in a rules sense.**
The `roll_dice` tool produces a real number and the agent narrates around it, but
no rule takes that number as input and produces a consequence. `Player.hp` is now a
validated field with bounds, but no function subtracts from it based on a combat
roll. That connection — typed attributes + deterministic rules — is the M4 payoff.
M3 built the attributes; M4 builds the rules.

**`model_construct()` bypasses validation.**
Pydantic's `model_construct()` method exists for performance-critical paths where
data is known to be valid. It skips all validators. If future code uses it to build
domain objects — especially in tests — it can produce invalid-but-constructed
objects that look fine until they hit a real validator downstream. The discipline is
to use normal constructors except in explicitly documented performance contexts.

**Single file for all models.**
All five models live in `domain/models.py`. At M3's scale this is fine. If the
domain grows significantly — more model types, nested validation logic, custom
validators — splitting into one file per model (or a models package) may be
warranted. Nothing in the current structure prevents that refactoring.

---

## 7. Bridge to TestOps AI

The Pydantic models in M3 map directly onto the validated data layer of a QA
product. The table below makes the mapping explicit:

| Dungeon Agents (M3) | TestOps AI equivalent |
|---------------------|----------------------|
| `Player` — validated character state, typed fields, bounded hp and gold | `TestCase` — validated test definition, required fields (title, steps, expected result), bounded attributes (priority, severity levels) |
| `Quest` — data-only objective with a completion flag | `UserStory` / acceptance criterion — title, description, `passed: bool`; the *rules* that evaluate passing are separate from the data shape |
| `GameState` — container; nested validation cascades through the whole tree | `TestPlan` / `TestRun` — container of test cases and suites; a plan with a malformed test case fails validation of the whole plan |
| `ActionResult` — explicit success/fail + message + optional new state | `TestResult` — `passed: bool` (required, no default), `message` (the failure detail), `evidence` (the new state / artifacts produced) |
| `GameState.model_validate_json(raw)` → `StateError` on schema mismatch | Loading a test plan from JSON or YAML → validation error if a required field is missing or a value is out of range |
| `save_state` / `load_state` alongside M2 raw-JSON functions | Versioned persistence with backward compatibility — new schema coexists with old one until all callers are migrated |

**The validation cascade in QA terms.** When a `GameState` fails because one
`InventoryItem` has `quantity=0`, the whole state fails — there is no partial-valid
game state. In a TestOps AI test plan, a missing required field in one test case
should invalidate the whole plan before any tests run, not silently produce a
partial execution. Cascade validation is the mechanism that enforces this.

**`ActionResult.success` has no default — same discipline for `TestResult.passed`.**
An action with no `success` flag is a construction error, not a silent `False`. A
test result with no `passed` value should similarly be an error, not a default.
Defaulting a required field to `False` would cause unreported results to look like
failures; defaulting to `True` would cause them to look like passes. Neither is
correct. No default is the right constraint.

**The schema is documentation you can run.** In TestOps AI, the question "what
does a valid test case look like?" is not answered by a wiki page — it is answered
by the Pydantic model definition. The field names, types, and constraints are the
authoritative spec. New developers who read the model know exactly what the system
accepts and rejects. And the tests that assert on invalid construction are
runnable examples of the spec being enforced.

---

## 8. What's next — Milestone 4: inventory and game rules

M3 defined the validated shape of the game state. M4 adds the rules that operate
on it.

Concretely, M4 will:

- Wire `save_state` / `load_state` into the agent tools, replacing the M2 raw-JSON
  path. After M4, the agent can only persist and load state that passes Pydantic
  validation.
- Add deterministic rule functions in `domain/rules.py` that take a `GameState`
  and return an `ActionResult`: pick up an item, spend gold, take damage from a
  combat roll. These functions will be pure Python — no SDK, fully testable without
  an API key.
- Use `Player.hp` and `Player.gold` in real calculations. The `roll_dice` tool,
  which has been present since M2, will finally have typed attributes to check
  against and rules that turn its output into a consequence.
- Define the win condition: what combination of `Quest.completed` and player state
  constitutes finishing the game.

After M4, the agent stops being a creative writing assistant that narrates around
dice rolls and starts being a genuine game engine with enforced rules. The M3
models are the foundation that M4 builds on.
