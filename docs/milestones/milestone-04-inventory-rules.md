# Milestone 4 — Inventory & Game Rules

> **Status:** Done
> **Theme:** The agent decides what the story is; deterministic Python decides whether it's allowed.

---

## 1. Goal

M3 left us with a fully validated data shape. A `Player` has typed, bounded `hp`
and `gold` fields; a `GameState` nests all the models and rejects anything invalid.
But those validated fields had no rules attached to them. The agent could narrate
"you spend 50 gold on a sword" even when the player had 3 gold, because nothing
in the code prevented it. The models enforced the *form* of state; nobody enforced
the *transitions*.

M4 closes that gap. It introduces **deterministic game rules** in a new file,
`domain/rules.py`, and wires them into four new agent tools. After M4:

- Picking up an item, losing an item, spending gold, taking damage, and recovering
  HP are all handled by pure Python functions that check preconditions and return
  an explicit result.
- The agent is told to use these tools and to relay rule failures to the player in
  an in-character way — it cannot "decide" that a rule doesn't apply.
- The game has a **win condition** (complete the active quest) and a **lose
  condition** (HP reaches 0) for the first time. It is no longer an infinite
  conversation; it can end.

This milestone is where the design principle that has been building since M2 fully
arrives:

> **The agent decides *when* to act and *how to narrate it*; tested Python decides
> whether the action is allowed and what the new state is.**

---

## 2. What was built — point by point

### 2.1 `domain/rules.py` — nine pure rule functions

**What:** a new file, `src/dungeon_agents/domain/rules.py`, containing one private
helper and nine public functions:

```
_find_item(state, name) -> InventoryItem | None   [private helper]

get_inventory(state)             -> str
add_item(state, name, quantity)  -> ActionResult
remove_item(state, name, qty)    -> ActionResult
spend_gold(state, amount)        -> ActionResult
earn_gold(state, amount)         -> ActionResult
change_hp(state, delta)          -> ActionResult
complete_quest(state)            -> ActionResult
is_game_won(state)               -> bool
is_game_over(state)              -> bool
```

Every function is **pure Python** — no SDK import, no file I/O, no randomness.
The file is fully unit-testable without an API key, which is exactly the rule for
the `domain/` layer established in M2.

**Why nine separate functions instead of a single dispatch function.**

Each rule covers exactly one precondition set and one resource. A combined
`apply_action(state, action_type, **kwargs)` function would save lines of code but
make testing harder: you would always have to spell out the action type, and a
single failing case would be harder to attribute to a specific rule. Separate
functions mean separate tests, separate failure messages, and a clear name in every
call site. When a TestOps AI equivalent runs a "spend budget" rule on a test
execution, you want to read `spend_budget(run, amount)` in the trace, not
`apply_resource_rule(run, "spend", amount=100)`.

### 2.2 Pure functions and the `model_copy(deep=True)` pattern

Every mutating rule follows the same three-step structure:

```python
def add_item(state: GameState, name: str, quantity: int = 1) -> ActionResult:
    # 1. check preconditions — fail early, don't touch the state
    if quantity < 1:
        return ActionResult(success=False, message="...")

    # 2. deep-copy the input state — never mutate the argument
    new_state = state.model_copy(deep=True)

    # 3. modify the copy and return it in the result
    new_state.inventory.append(InventoryItem(name=name, quantity=quantity))
    return ActionResult(success=True, message="...", new_state=new_state)
```

**Why `model_copy(deep=True)` instead of `copy.deepcopy()`.**

Pydantic models are validated objects. `model_copy` is Pydantic's own deep-copy
method — it respects the model's internal state correctly, including nested models.
`copy.deepcopy` also works on Pydantic models, but `model_copy(deep=True)` is the
idiomatic choice: it signals intent ("I want a full copy of this domain object")
and stays within the Pydantic API.

**Why this makes rules trivially testable.**

A rule that mutates its input requires test setup: you construct a state, apply the
rule, then wonder whether `state` or `result.new_state` holds the change. A pure
function does not: you hand in a state, you get back a result, and you assert on
the result. The original state is unchanged and can be inspected. The tests for
this — `test_add_item_does_not_mutate_input_state`, and the equivalent for every
other mutating rule — verify this guarantee explicitly: call the rule, then assert
that the original state object is unchanged.

### 2.3 Inventory rules: `get_inventory`, `add_item`, `remove_item`

**`get_inventory`** is the only read-only rule. It takes a `GameState` and returns
a human-readable string summarising the inventory:

```
"The inventory is empty."

or

"Inventory:
- Torch x2
- Health Potion x1"
```

The name matching in `_find_item` is case-insensitive (`item.name.lower() ==
name.strip().lower()`). This means the agent can say "torch" or "Torch" and get
the same result — important because the model's casing of item names may drift
across turns.

**`add_item`** enforces two preconditions: the name must be non-empty after
stripping whitespace, and the quantity must be at least 1. On success, if the item
already exists in the inventory its quantity grows (stacking); otherwise a new
`InventoryItem` is appended. Both paths return `ActionResult(success=True, ...)`.
A violation returns `ActionResult(success=False, message="...")` with `new_state`
left as `None` — nothing was changed.

**`remove_item`** enforces three preconditions: positive quantity, item exists,
and the existing stack covers the requested quantity. The error messages are specific
(`"You only have 2x Arrow, can't remove 5."`) so the agent can relay them
in-character without improvisation. When a stack drops to zero, the item is removed
from the list entirely — a zero-quantity `InventoryItem` is invalid per M3's
`InventoryItem(quantity: int = Field(ge=1))` constraint, so the rule ensures the
state stays valid.

### 2.4 Resource rules: `spend_gold`, `earn_gold`, `change_hp`

**`spend_gold`** and **`earn_gold`** are symmetric. `spend_gold` checks that the
amount is positive and that `amount <= state.player.gold`, then subtracts. `earn_gold`
checks that the amount is positive, then adds.

**Why the check, when `Player.gold` already has `ge=0`?**

This is a subtle but important design point. `Player.gold` carries the invariant
"gold is never negative." That invariant lives on the *model* — it describes a
valid `Player` at rest. The `spend_gold` rule is not a model constraint; it is a
*transition guard*. Without it, the code would attempt to build a `Player` with
negative gold and get a `ValidationError` from Pydantic — a correct but
unfriendly failure. The rule catches the violation one step earlier, returns a
friendly message (`"You only have 3 gold, can't spend 10."`), and never attempts
the invalid construction. The model's constraint is a backstop; the rule is the
intended gate.

**`change_hp`** handles damage and healing in one function. The `delta` parameter
is signed: negative for damage, positive for healing. HP is clamped:

```python
player.hp = max(0, min(player.hp + delta, player.max_hp))
```

**Why clamp instead of validate?**

HP arithmetic in a game is full of edge cases: a goblin hits you for 999 damage
when you have 10 HP; a potion heals you for 50 when you are already at 95/100.
If the rule raised an error on overflow, the caller would need to pre-compute the
clamped value before calling — shifting the burden upstream and spreading the
clamping logic across every combat/healing call site. Clamping inside the rule
means the caller says "this hit does delta damage" and trusts the rule to produce
a valid HP value. The formula is correct and the result is always in `[0, max_hp]`,
so the Pydantic model never sees an out-of-range value.

This is a general principle: **when a transition to an invalid state is expected
and has a natural resolution (clamp, cap, floor), the rule applies it; when the
transition is conceptually wrong and there is no natural resolution (spending gold
you do not have), the rule rejects it with a friendly message.**

The `change_hp` function also emits a meaningful message depending on the outcome:
`"Aria has fallen! (HP reached 0)"` when the player dies, `"Aria takes 20 damage
(HP now 30)."` for ordinary damage, and a healing message for positive delta.

### 2.5 Win and lose conditions: `complete_quest`, `is_game_won`, `is_game_over`

For the first time, the game has **a way to end**.

**`complete_quest`** marks the active quest done. It checks that an active quest
exists and that it is not already completed, then sets `new_state.active_quest.completed = True`.
The returned message confirms the win. Two error cases:
- No active quest: `ActionResult(success=False, message="There is no active quest to complete.")`
- Already completed: `ActionResult(success=False, message="That quest is already completed.")`

**`is_game_won`** is a pure boolean check:

```python
def is_game_won(state: GameState) -> bool:
    return state.active_quest is not None and state.active_quest.completed
```

**`is_game_over`** is similarly direct:

```python
def is_game_over(state: GameState) -> bool:
    return state.player.hp == 0
```

**Why these are separate functions and not properties on `GameState`.**

A Pydantic model property could express these checks, but it would place
*behavioral* logic inside a *data* class. The domain layer separates data shapes
(`models.py`) from the rules that operate on them (`rules.py`). `GameState` knows
what it carries; `rules.py` knows what it means. This separation keeps `models.py`
a clean, SDK-free data contract and keeps `rules.py` the authoritative source of
truth for game logic.

### 2.6 `tools/game_tools.py` — four new tools, two shared helpers

**What:** four `@function_tool` functions added to the existing file, plus two
private helpers shared by all four:

```python
def _load_or_new_state() -> GameState
def _apply(result) -> str

@function_tool  get_inventory() -> str
@function_tool  add_item(item_name, quantity=1) -> str
@function_tool  remove_item(item_name, quantity=1) -> str
@function_tool  validate_action(action) -> str
```

**`_load_or_new_state`** implements the "load or seed" pattern. It calls
`state.load_state()` (the M3 validated persistence function). If no save exists
(`None`), it returns a fresh `GameState` with a default `Player(name="Adventurer")`
and an opening `Quest(title="Clear the cellar", ...)`. This means the inventory
tools always have a valid, typed state to operate on — there is no code path where
they receive `None`.

**`_apply`** is the persistence bridge between a rule result and the file system:

```python
def _apply(result) -> str:
    if result.success and result.new_state is not None:
        state.save_state(result.new_state)
    return result.message
```

On success it saves the produced `new_state` to `data/game_state.json` (validated,
per M3's `save_state`). On failure nothing is saved. Either way it returns the
human-readable message, which the agent receives and narrates. This is the
**load-modify-save pattern**: load current state → apply rule → save result if
successful → return message.

**`get_inventory`** and **`add_item` / `remove_item`** are thin wrappers that
compose `_load_or_new_state()` and `_apply()`:

```python
@function_tool
def add_item(item_name: str, quantity: int = 1) -> str:
    return _apply(rules.add_item(_load_or_new_state(), item_name, quantity))
```

Three lines is correct. All business logic is in `domain/rules.py`; all
persistence is in `_apply`. The tool wrapper has exactly one responsibility:
translate the agent's tool call into a domain call and a persistence call.

**`validate_action`** is different in character. Rather than applying a specific
rule, it assembles a snapshot of the player's current state and returns it to the
agent as context, along with the action string:

```python
@function_tool
def validate_action(action: str) -> str:
    game = _load_or_new_state()
    summary = rules.get_inventory(game)
    return (
        f"Player has {game.player.gold} gold and {game.player.hp} HP. {summary}\n"
        f"Judge whether this action is possible with those resources: {action}"
    )
```

It does not make the decision — the model does, with accurate resource information
in front of it. This is deliberate: for actions that do not map cleanly to a single
rule (e.g. "I try to bribe the guard with whatever I can afford"), providing
context and letting the agent reason is more flexible than trying to enumerate every
possible action type as a rule.

### 2.7 `agents/game_master.py` — all 7 tools registered, instructions updated

**What:** `build_game_master` now imports and registers all seven tools:

```python
tools=[
    roll_dice,
    save_game_state,
    load_game_state,
    get_inventory,
    add_item,
    remove_item,
    validate_action,
]
```

The `GAME_MASTER_INSTRUCTIONS` constant was updated with an explicit rules section:

```
- The game's rules are enforced by tools, not by you. Use them and narrate what
  they return; never let the player do something the rules forbid:
  - `get_inventory` to see what the player carries.
  - `add_item` / `remove_item` when the player gains or loses items.
  - `validate_action` before resolving an action that spends gold or uses items.
- When a rule tool reports a failure, explain it to the player in a friendly,
  in-character way rather than ignoring it.
```

**Why keep `save_game_state` and `load_game_state` alongside the new tools.**

The M2 raw-JSON tools remain for two reasons. First, the agent's existing behavior
of calling `save_game_state` / `load_game_state` for session persistence still
works and is not broken by M4. Second, removing them would mean the agent loses the
ability to save and resume mid-session progress until a full migration is done. M4
adds alongside without removing — the same discipline as M3 adding `save_state`
alongside `save_game_state`.

### 2.8 `main.py` `HELP_TEXT` — honest milestone-scoped description

The player-facing help text was updated to accurately describe the M4 game state:
inventory, gold, HP limits, the quest objective, and win/lose conditions. The key
sentences:

> "Win by completing your quest (e.g. 'I finish the quest' once you've done what
> it asks). Lose if your HP reaches 0 and your character falls."

**Why update the help text as part of the milestone.**

The help text is the user contract — what the player is promised the game does.
Documenting rules that the code does not enforce would be misleading; leaving the
help text at M3's "coming in later milestones" wording would be equally wrong.
After M4, the rules are real; the help text says they are real.

### 2.9 `tests/test_rules.py` — 29 new tests

**What:** a new file, `tests/test_rules.py`, with 29 deterministic test cases.
The total deterministic suite is now **78 tests** (8 smoke + 12 dice + 9 state +
20 models + 29 rules), all passing without an API key.

The test file uses a `_fresh_state(**player_kwargs)` helper that constructs a
minimal valid `GameState` with a single `Player(name="Aria")`. This keeps test
cases short and focused on the rule being tested, not on state setup.

**Test groups and what each verifies:**

| Group | Tests | Key cases |
|-------|-------|-----------|
| `get_inventory` | 2 | empty state; state with items |
| `add_item` | 6 | add to empty; stack existing (case-insensitive); no mutation; non-positive qty (parametrized × 2); empty name |
| `remove_item` | 6 | success; stack drops to zero; item not present; quantity exceeds stack; no mutation; qty message content |
| `spend_gold` / `earn_gold` | 5 | spend success; can't overspend; non-positive amount (parametrized × 2); no mutation; earn success |
| `change_hp` | 5 | damage; healing; clamp at 0 + fallen message; clamp at max_hp; no mutation |
| `win / lose` | 5 | complete_quest sets won; no active quest; already completed; is_game_won false without quest; is_game_over at hp=0 and hp=1 |

The parametrize patterns (`@pytest.mark.parametrize("bad_qty", [0, -3])` and
`@pytest.mark.parametrize("bad_amount", [0, -5])`) follow the same style
established in `test_models.py` for `Player` validation — same data, different
inputs, one assertion pattern.

---

## 3. Concepts learned in M4

| Concept | Where it showed up | Why it transfers |
|---------|------------------|-----------------|
| AI orchestrates, code verifies | Agent calls tools; rules decide | The model is not the authority on whether an action is legal — tested Python is |
| Pure functions (state in, result out, no mutation) | Every rule in `rules.py` | Trivially testable: hand in a state, assert on the result; the original is untouched |
| `model_copy(deep=True)` | Every mutating rule | Pydantic's idiomatic deep copy; keeps rules pure even over nested models |
| Precondition as early return | `if quantity < 1: return ActionResult(success=False, ...)` | Check, fail fast, never touch state — same discipline as guard clauses |
| Clamp vs. reject | `change_hp` clamps; `spend_gold` rejects | When a natural resolution exists, apply it; when there is none, fail clearly |
| Rule as the transition guard, model as the backstop | `spend_gold` checks before building; `Player.gold ge=0` catches any escape | Two defensive layers: the rule for expected cases, the model for programming errors |
| Load-modify-save pattern | `_load_or_new_state()` + rule + `_apply()` | One consistent persistence contract for all state-changing tools |
| Friendly rule failure messages | Every `ActionResult(success=False, message=...)` | Errors are user-facing; "can't spend 10, you have 3 gold" is more useful than `ValidationError` |
| Win/lose as deterministic checks | `is_game_won`, `is_game_over` as pure booleans | The narrative can be improvised; whether the game is over is not |
| Separation of data and behavior | `models.py` vs. `rules.py` | Pydantic models define shape; rule functions define transitions — each has one job |

---

## 4. QA mindset in M4

**Rules are acceptance criteria validators.**

Every `domain/rules.py` function is the direct analogue of a test assertion. It
receives a state, checks a condition, and returns a typed result with a `success`
flag and a message. The pattern is identical to what a QA acceptance-criteria
validator does: given a system state, does this action meet the preconditions? If
yes, apply it and return the new state. If no, return a failure with a clear
explanation.

The key shift from M3 is that M4's rules are not passive schema constraints —
they are *active checks* that run at the moment of each action. A Pydantic model
says "a Player with negative gold cannot exist." A `spend_gold` rule says "a
Player cannot spend gold they do not have, right now, as this action is being
applied."

**`validate_action` is a precondition check.**

Before the agent narrates the outcome of a resource-spending action, it calls
`validate_action(action)` to confirm the player has the resources to do it. This
is exactly the pattern of a pre-condition check in a test: verify the system is in
a valid state before executing the operation. In a QA system, this is the
difference between testing a feature with valid preconditions and testing it with
setup that guarantees the expected starting state.

**`ActionResult` is a validation result.**

`ActionResult(success: bool, message: str, new_state: GameState | None)` maps
cleanly to a test result:
- `success` — did the assertion pass?
- `message` — what does the failure (or success) say?
- `new_state` — the new system state after the operation (the evidence, the
  artifact produced by the test run).

`success` has no default (established in M3) — a result with no verdict is a bug.

**The agent cannot "cheat."**

Before M4, the agent could hallucinate a dice result or narrate "you spend gold"
without the state changing. After M4, the agent is told to use rule tools and
narrate what they return. It cannot decide that a rule doesn't apply, because the
tools are wired and the instructions are explicit. This is the QA analogy: a test
runner does not let the test script decide that a step should be skipped — it runs
the step, checks the result, and records what actually happened.

**Pure functions mean reproducible tests.**

Every rule test is deterministic. There is no randomness, no time dependency, no
shared state. Given `_fresh_state(gold=3)` and `spend_gold(state, 10)`, the
result is always the same `ActionResult(success=False, message="You only have 3
gold, can't spend 10.", new_state=None)`. You can run the test suite a thousand
times with no API key and get the same 78 passes. That reproducibility is the
foundation of a trustworthy test suite — in Dungeon Agents and in TestOps AI alike.

**Win and lose conditions are tested assertions.**

`is_game_won` and `is_game_over` are pure boolean functions over the state. They
are tested in `test_rules.py`. The test `test_complete_quest_wins_the_game` is not
just a unit test for `complete_quest` — it is a specification: "a game in which
the active quest is completed is a won game." In TestOps AI, the equivalent is a
"done check" function: given a test execution result, is the feature considered
complete?

---

## 5. How to test / verify it yourself

```bash
# Inside an activated .venv with `pip install -e ".[dev]"` already run:

# Full deterministic suite (78 tests, no API key needed):
python -m pytest -m "not llm" -q
# Expected: 78 passed

# Run just the new M4 rules tests:
python -m pytest tests/test_rules.py -v

# See the rules work at the Python REPL — no SDK, no API key:
python -c "
from dungeon_agents.domain.models import GameState, Player, Quest, InventoryItem
from dungeon_agents.domain import rules

state = GameState(
    player=Player(name='Aria', gold=10, hp=50),
    inventory=[InventoryItem(name='Torch', quantity=2)],
    active_quest=Quest(title='Clear the cellar'),
)

# Inventory
print(rules.get_inventory(state))            # Inventory:\n- Torch x2

# Add an item
r = rules.add_item(state, 'Health Potion', 1)
print(r.success, r.message)                  # True  Added 1x Health Potion.
print(len(state.inventory))                  # 2  -- original unchanged

# Try to remove something you don't have
r = rules.remove_item(state, 'Sword', 1)
print(r.success, r.message)                  # False  You don't have any Sword to remove.

# Spend gold you have
r = rules.spend_gold(state, 4)
print(r.success, r.new_state.player.gold)    # True  6

# Try to overspend
r = rules.spend_gold(state, 99)
print(r.success, r.message)                  # False  You only have 10 gold, can't spend 99.

# HP clamping: take 999 damage
r = rules.change_hp(state, -999)
print(r.new_state.player.hp, 'fallen' in r.message.lower())  # 0  True

# Win the game
r = rules.complete_quest(state)
print(r.success, rules.is_game_won(r.new_state))  # True  True

# Lose condition
dead_state = GameState(player=Player(name='Aria', hp=0))
print(rules.is_game_over(dead_state))        # True
"
```

**Expected results:**

- `78 passed` from the full deterministic suite.
- The REPL examples print the values shown in the comments — every rule behaves
  as described, the original state is never mutated, and the impossible actions
  fail with friendly messages.

---

## 6. Risks & tradeoffs

**`validate_action` delegates the decision to the model.**

`validate_action` provides resource context but leaves the "is this allowed"
judgment to the agent. A determined or confused model could still narrate an action
its judgment found "allowed" even when a specific rule would reject it. The
`add_item` / `remove_item` tools do enforce their rules; `validate_action` is a
softer guard for open-ended actions. A future milestone could replace it with
stricter structured action types.

**No spend-gold or earn-gold tool yet.**

`domain/rules.py` has `spend_gold` and `earn_gold` functions. There are no
corresponding `@function_tool` wrappers in `game_tools.py`. The agent uses
`validate_action` to check affordability and `add_item` / `remove_item` for
inventory, but gold changes are not directly tool-callable. Adding tool wrappers
for gold is a small step (follow the `add_item` pattern) and is deferred to keep
M4 focused.

**`save_game_state` / `load_game_state` are still wired.**

The M2 raw-JSON tools remain active alongside the M4 tools. The agent could still
call `save_game_state` with arbitrary JSON and bypass the validated persistence
path. Removing the M2 tools would be a clean break but could disrupt session
saves the agent makes via those tools. The migration is deferred.

**Win/lose detection is not wired to the game loop.**

`is_game_won` and `is_game_over` are deterministic functions that can read the
current state. Nothing in `main.py` calls them after each turn and acts on the
result (showing a win screen, stopping the loop). Wiring them into the game loop
is a natural next step; for M4, the functions exist and are tested, but the loop
does not yet terminate based on them.

**Load-modify-save is not atomic.**

Each inventory tool loads state, applies a rule, and saves the result as three
separate file operations. A crash between the rule and the save would leave the
state on disk behind the in-memory result. At single-user console scale this is
acceptable. A production system would want a transaction.

---

## 7. Bridge to TestOps AI

The rule layer built in M4 is the closest the project has come, so far, to the
core of what TestOps AI needs to do. The table below maps each piece directly:

| Dungeon Agents (M4) | TestOps AI equivalent |
|---------------------|----------------------|
| `rules.py` pure functions | Acceptance-criteria validators — each checks one precondition set and returns a typed result |
| `ActionResult(success, message, new_state)` | `TestResult(passed, message, evidence)` — the explicit return type from any automated check |
| `validate_action(action)` | Precondition checker — does the system satisfy the prerequisites for this test step? |
| `is_game_won(state)` | Done/complete check — given an execution result, is the feature considered passing? |
| `is_game_over(state)` | Hard-fail detector — given a system state, has an unrecoverable failure occurred? |
| Rules live outside the agent's control | The agent cannot "declare" a test passed — the rule function is the authority |
| Load-modify-save in tools | Test-runner step: load execution context, apply check, persist result |
| `change_hp` clamps within valid bounds | Resource accounting in a test budget: clamp cost to budget ceiling rather than crashing |
| Case-insensitive `_find_item` | Normalise identifiers before comparison in a test registry — avoid false "not found" on casing differences |

**The most important transfer: rules outside the agent's control.**

In M4, the agent is told what tools to use and what to narrate — but it cannot
decide to skip the `remove_item` rule when the player lacks the item, or to grant
a gold spend that exceeds the player's balance. The rule runs and the result is
what it is.

In TestOps AI, this is the property that makes automated QA trustworthy: the agent
can decide which tests to run and how to report them, but whether a test passed is
determined by a deterministic assertion function, not by the model's judgment. The
model should never be the one deciding that a test "kind of passed." Tested Python
makes that call.

**`ActionResult` is a validation result object.**

Every QA system needs a standard result type — something that carries `passed`,
a `message`, and the evidence (artifacts, diffs, new state). `ActionResult` is
the game's version. Designing it in M3 with `success` having no default (you must
always state whether the action succeeded) carries over directly: a test result
with no explicit verdict is a bug, not a default.

**Pure functions mean auditable test history.**

Because every rule is pure, you can replay any sequence of actions from a saved
state and get exactly the same results. That is the property a QA audit trail
needs: the execution history is reproducible, not dependent on timing or side
effects. Dungeon Agents demonstrates this at small scale; TestOps AI needs it at
production scale.

---

## 8. What's next — Milestone 5: session state & UX (then M6: multi-agent)

> **Roadmap note (updated):** a new M5 — Session state & UX — was inserted after
> M4 shipped. The multi-agent work described below is now **M6**. The M5 scope
> covers save-format unification, new-game vs. load choice, resume recap, and
> deterministic stats/inventory commands.

M4 gave the game its rules. M6 introduces its first specialist agents alongside
the Game Master.

The M1–M4 design has been a single Game Master agent that does everything:
narrates, enforces rules (via tools), manages inventory, and tracks the quest. At
small scale this works. As the game grows more complex — more rule types, richer
lore, combat mechanics, inventory management across many item types — a single
agent becomes a bottleneck: its context gets crowded, its responsibilities blur,
and its instructions become a wall of text.

M5 will introduce a **multi-agent architecture**, splitting the Game Master into
a team of specialist agents:

- **Game Master** — narration and player interaction (existing, slimmed down)
- **Rules Referee** — applies game rules and validates actions
- **Inventory Keeper** — tracks and reports what the player carries
- **Lore Keeper** — maintains and queries the session narrative summary
- **Critic** — reviews the GM's output for consistency and tone

Each agent will have a narrow responsibility and a short instruction set. The
OpenAI Agents SDK's agent-handoff mechanism routes requests between them. This
introduces a new design challenge: when something goes wrong, which agent is
responsible? How do you test the interactions between agents, not just each agent
in isolation?

The `domain/` layer's rules and models are not changing in M5 — they are the
stable foundation that the multi-agent layer builds on. Everything you learned in
M1–M4 about separating deterministic logic from the agent layer pays off in M5:
the rules are testable without any agent; the agents are interchangeable without
touching the rules.
