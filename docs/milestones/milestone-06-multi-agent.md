# Milestone 6 — Multi-Agent Architecture

> **Status:** In progress — Blocks 1 and 2 complete (Game Master + Rules Referee,
> persistence fix, and skill-check mechanic). Blocks for Inventory Keeper, Lore
> Keeper, and Critic remain.
>
> **Theme:** Specialization + coordination produce reliability that a single
> agent with a longer prompt never can. The model orchestrates; the code verifies.

---

## 1. Goal

M5 solved a painful single-agent problem: a Game Master asked to narrate, track
inventory, sync location, roll dice, validate spending, update summaries, and
manage saves in one turn made each job worse. Its context filled with competing
instructions; its reliability with any single job was proportional to how much
attention was left over for it.

The insight is structural, not a matter of prompting harder. A single agent that
does seven things at once is like a developer who is simultaneously the architect,
the reviewer, the DBA, and the on-call responder. The answer is not a longer job
description; it is dividing the work.

M6 replaces the do-everything Game Master with a **team of specialist agents**:

| Agent | Responsibility |
|-------|---------------|
| **Game Master** | Narrates the story and orchestrates the others |
| **Rules Referee** | Arbitrates: is this action allowed? What is its outcome? |
| Inventory Keeper | Tracks and reports what the player carries (future block) |
| Lore Keeper | Maintains session summaries and scene history (future block) |
| Critic | Reviews GM output for consistency and tone (future block) |

This document covers **Blocks 1 and 2**. Block 1 introduced the Rules Referee
and the agent-as-tool coordination pattern. Block 2 — driven by the user playing
the game and noticing concrete failures — fixed two mechanical gaps: gold and HP
changes were never persisted to disk, and a bare dice roll had no mechanical
weight because the model decided what the number meant. The remaining agents will
be documented as they are built.

The `domain/` layer — rules, models, state, dice — is unchanged. Every function
built in M1–M5 is the stable tested foundation that the multi-agent layer runs on
top of. That is the payoff for the M2–M4 discipline of keeping deterministic logic
out of agents.

---

## 2. What was built — Block 1

### 2.1 The Rules Referee — a second agent with a narrow job

`agents/rules_referee.py` introduces the project's first specialist agent. Its
contract is written at the top of the file:

> "Where the Game Master narrates the story, the Rules Referee does one narrow
> job: it judges whether a proposed action is allowed by the game's rules and
> what its outcome is, rolling dice when chance is involved. It does NOT tell
> the story."

`RULES_REFEREE_INSTRUCTIONS` (the module-level constant,
`agents/rules_referee.py:30`) defines the Referee's behavioral contract. Like
`GAME_MASTER_INSTRUCTIONS`, it lives as a constant so contract tests can assert
on it without touching the SDK or an API key. The Referee knows:

- When an outcome depends on chance, call `roll_dice` — never invent a number.
- When an action spends gold or consumes items, call `check_can_afford` first.
- State the ruling plainly: allowed or disallowed, dice rolled and their values,
  a one-line reason.
- Hard limit: do not narrate. That is the Game Master's job.

The `build_rules_referee()` factory (`agents/rules_referee.py:71`) constructs the
agent with only the arbitration tools — initially `roll_dice` and
`check_can_afford` (Block 1), expanded to six tools in Block 2 (section 2.5). It
deliberately receives none of the narration or story-state tools. The capability
surface matches the job surface.

**Why this matters.** Giving an agent only the tools its job needs is not just
tidiness — it is a testability decision. A Referee that cannot call `add_item` or
`set_location` can never accidentally mutate state while arbitrating. Its outputs
are rulings: structured text, not side effects. That makes testing its behavior
tractable without a live model call (section 5).

### 2.2 The Game Master becomes an orchestrator

`build_game_master()` (`agents/game_master.py:82`) now has a clear two-part
structure:

1. Build the Rules Referee.
2. Expose the Referee to the Game Master as a tool via `.as_tool(...)`.

The wiring is at `agents/game_master.py:126–134`:

```python
referee = build_rules_referee(settings)
rules_referee_tool = referee.as_tool(
    tool_name="rules_referee",
    tool_description=(
        "Consult the Rules Referee to resolve the outcome of a risky or "
        "resource-spending action. Describe the action; it returns a ruling "
        "(allowed/disallowed, any dice rolled, a one-line reason)."
    ),
)
```

`rules_referee_tool` then appears as the first entry in the Game Master's tool
list (`agents/game_master.py:141`), alongside the narration and state-sync tools.
From the Game Master's perspective, the Referee is just another tool — a callable
that takes a description of an action and returns a structured ruling.

The Game Master's instructions (`GAME_MASTER_INSTRUCTIONS`, `agents/game_master.py:16`)
reflect the new division of labor:

> "To resolve the OUTCOME of an action that is risky or depends on chance
> (an attack, a climb, a skill check), or that spends gold or uses items, consult
> the `rules_referee` tool. Describe the action to it; it returns a ruling
> (allowed or disallowed, any dice rolled, a one-line reason). Narrate the story
> around whatever it rules — the Referee decides the outcome, you tell the tale."

Two tools that the Game Master held before M6 — `roll_dice` and `validate_action`
— are no longer in its tool list. The Game Master no longer rolls dice itself; it
asks the Referee, which does it. The Referee's `check_can_afford` replaces
`validate_action` entirely (section 2.4).

### 2.3 Tool count after Block 2

| Agent | Tools |
|-------|-------|
| Game Master | `rules_referee` (the Referee as tool), `save_game`, `load_game`, `get_inventory`, `add_item`, `remove_item`, `update_summary`, `set_location`, `set_quest` (9 total) |
| Rules Referee | `skill_check`, `roll_dice`, `check_can_afford`, `earn_gold`, `spend_gold`, `change_hp` (6 total) |

The total tool count visible to the system is 15, but the GM sees 9 and the
Referee sees 6. Specialization means narrowing, not growing. The Referee grew
from 2 to 6 tools in Block 2 because arbitrating an outcome now includes
persisting its consequences — those four tools are not narration tools, they are
the completion of the Referee's single job.

### 2.4 Design decision: `validate_action` retired, `check_can_afford` introduced

`validate_action` existed in M4–M5. Its name implied deterministic validation but
its implementation delegated the decision to the model: it returned a prompt
fragment instructing the model to "judge whether this is possible." The code did
not decide; it handed the question back to the caller wearing a deterministic name.

This was a double problem:

1. **A misleading name.** A function named `validate_action` should validate; it
   should not ask the model to judge. The name encouraged callers to trust it like
   deterministic code, when it was actually probabilistic. This is the cousin of
   the silent false positive: a plausible-looking veneer over a non-guarantee.

2. **A violation of the project's central principle.** The decision of whether an
   action is affordable belongs in Python, not in a model prompt. The model
   translates "the adventurer wants to buy a rope for 5 gold" into structured
   numbers; the code decides whether 5 gold is available.

The user noticed that the name was misleading — a good QA instinct. The fix was
to write the function that should have existed in the first place.

`can_afford` in `domain/rules.py:46` is a **read-only, deterministic pre-check**.
It takes `gold_cost`, `item_name`, and `item_quantity` as integers, loads the
current `GameState`, and decides without mutating anything:

```python
def can_afford(
    state: GameState,
    gold_cost: int = 0,
    item_name: str = "",
    item_quantity: int = 1,
) -> ActionResult:
```

It reports every shortfall in a single `ActionResult` — both gold and item gaps
are listed if both are missing (`domain/rules.py:91–94`). The message is exact:
`"Cannot afford: needs 5 gold but only has 3; needs 1x Rope but has 0."` The
model receives that message verbatim to relay to the player.

`check_can_afford` in `tools/game_tools.py:151` is the thin `@function_tool`
wrapper given to the Rules Referee. It converts the model's description (three
typed parameters: `gold_cost: int`, `item_name: str`, `item_quantity: int`) into a
call to `can_afford` and returns its `.message`. The model now **translates story
to numbers**; the code **decides affordability**.

This is the same "AI orchestrates, code verifies" pattern applied one level deeper:
now the code inside the Referee's tools — not just the GM's tools — does the
deciding.

### 2.5 Block 2 — Bug fix: gold and HP changes were never persisted

This fix, like the `validate_action` retirement, was identified because the user
played the game. The symptom: after earning a reward or taking damage in combat,
the `stats` command showed the original values, and reloading the game reset
everything to zero. The model was narrating changes that never touched the
validated state on disk.

The root cause was a gap in tool exposure. `earn_gold`, `spend_gold`, and
`change_hp` existed as pure domain functions in `domain/rules.py` since Milestone
4. They were correct and tested. But they were never wrapped as `@function_tool`
and never given to any agent. The agent had no mechanism to call them.

The consequence was the same failure mode that M5 established as the cardinal
error: the model's narration was the only record of the gold and HP changes.
Narration is not state. When the session ended, the changes vanished.

The fix is in `tools/game_tools.py:177–216`. Three new `@function_tool` wrappers
were added, each following the established load-modify-save pattern:

```python
@function_tool
def earn_gold(amount: int) -> str:
    return _apply(rules.earn_gold(_load_or_new_state(), amount))

@function_tool
def spend_gold(amount: int) -> str:
    return _apply(rules.spend_gold(_load_or_new_state(), amount))

@function_tool
def change_hp(delta: int) -> str:
    return _apply(rules.change_hp(_load_or_new_state(), delta))
```

`_apply` (`tools/game_tools.py:46`) calls `state.save_state(result.new_state)` on
success. The domain function enforces the rule (HP clamped to `[0, max_hp]` by
`max(0, min(v, cap))`; gold cannot go below 0); the wrapper persists the result.

All six tools are now given to the Rules Referee in `build_rules_referee()`
(`agents/rules_referee.py:97–104`). The Referee's instructions were updated to
explain when to call each one and why:

> "Once an action's outcome is decided, PERSIST its consequences by calling the
> matching tool so the tracked state stays accurate: `earn_gold` / `spend_gold`
> when the player gains or loses gold. `change_hp` when the player takes damage
> (negative) or heals (positive). These write the change to the game state;
> without them the change exists only in the story and is lost on reload. Only
> persist consequences you actually ruled."
> (`agents/rules_referee.py:51–56`)

The instruction makes the reason explicit — "lost on reload" — so the model
knows not just what to call but why the call matters. This is the pedagogic
pattern established in `tools/game_tools.py` docstrings since M2: the docstring
is the agent's instruction, and the instruction must explain the consequence of
not following it.

**Why the Referee, not the Game Master?** Persistence of a consequence is part of
completing a ruling. If the Referee decides "the player takes 6 damage," it
should call `change_hp(-6)` before returning its verdict — the ruling is not
complete until its effect is on disk. Giving these tools to the GM would split
the judgment (Referee) from the write (GM), which is a coordination hazard: the
GM might narrate a different number than the Referee ruled, or forget to call
the tool entirely. Keeping consequence persistence inside the Referee closes the
loop atomically within the arbitration step.

### 2.6 Block 2 — Mechanic fix: dice tied to a deterministic consequence

The second fix was also found by the user playing the game. The symptom was
subtle: dice were being rolled, but they had no mechanical effect. A roll of 14
and a roll of 3 on the same task produced the same story outcome — whatever the
model decided to narrate. The die was theater, not a game mechanic.

The root cause was that `roll_dice` returned a raw integer. The model received
"Rolled a 9 on a 20-sided die" as a tool result and was then free to interpret
that 9 as success or failure based on its next prediction. The code produced a
number; the model produced the consequence. That is the wrong division of labor.

The fix is `resolve_check` in `domain/dice.py:102–130` and its `skill_check`
wrapper in `tools/game_tools.py:219–241`.

`resolve_check` rolls `1d20` and **compares the result against a named difficulty
threshold in Python**, returning a `CheckResult` with an unambiguous `success:
bool` field. The model cannot interpret the verdict — it reads "SUCCESS" or
"FAILURE" from the tool result string produced by `skill_check`:

```python
verdict = "SUCCESS" if result.success else "FAILURE"
return (
    f"{verdict}: rolled {result.roll} on 1d20 vs {result.difficulty} "
    f"(needs {result.threshold}+)."
)
```

(`tools/game_tools.py:237–241`)

The five named difficulty levels (`domain/dice.py:67–73`) and their thresholds
are:

| Level | Minimum d20 roll needed |
|-------|------------------------|
| `trivial` | 3 |
| `easy` | 5 |
| `moderate` | 10 |
| `hard` | 15 |
| `very_hard` | 18 |

**Design decision: named levels, not free integers.**

Three alternatives were considered:

1. **Named difficulty levels (chosen).** The Referee passes a word ("moderate");
   the code maps it to a threshold and compares. The model judges *how hard* the
   action is (a subjective, context-sensitive question — exactly what a language
   model is well-suited to answer). The code decides *whether it succeeds*
   (a deterministic comparison — exactly what Python does reliably). The set of
   valid difficulty names is closed; an unknown name raises
   `InvalidDifficultyError` immediately (`domain/dice.py:118–123`), so the model
   cannot invent a level.

2. **Free integer threshold (rejected).** Passing a raw integer threshold (e.g.
   `threshold=12`) would give the model unconstrained influence over the
   difficulty, making the mechanic effectively probabilistic again — the model
   could always set `threshold=1` for a guaranteed success. Named levels bound
   the model's authority to the vocabulary the designers chose.

3. **Fixed single difficulty (rejected).** A single global threshold loses all
   mechanical texture: a "trivial" task and a "very hard" task feel identical.
   Named levels let the Referee make a meaningful judgment about the fiction
   without controlling the arithmetic.

The principle is the same as for `check_can_afford`: the model's role is
translation and judgment (what is this action, how hard is it?); the code's role
is the binary decision (did it succeed?). The model cannot override a failed
roll by claiming it would have succeeded. The roll is the record; `success:
bool` is the verdict; narration follows from both.

`resolve_check` is fully testable with a seeded `rng` parameter
(`domain/dice.py:103`), following the same injection pattern as `roll_dice`.
Given the same seed and difficulty, the outcome is always identical —
reproducibility under test, real randomness in play.

---

## 3. Concepts learned — multi-agent coordination patterns

This is the conceptual center of M6. Three coordination patterns are available;
understanding all three — and why Block 1 chose one over the others — is the core
lesson.

### 3.1 Pattern 1 — Agent-as-tool / orchestrator (the M6 choice)

One agent calls another **as if it were a tool**. The SDK's `.as_tool(...)` method
wraps a full Agent into a callable: when the orchestrator "calls" it, the inner
agent runs to completion (potentially calling its own tools in its own internal
loop), then returns its final text output as the tool result. Control **returns to
the orchestrator** after every call.

In M6: the Game Master is the orchestrator. The Rules Referee is called via
`rules_referee_tool`. When the GM calls `rules_referee("the player tries to climb
the wall")`, the Referee runs its internal loop — possibly rolling dice, possibly
checking affordability — and returns a ruling. The GM receives that ruling as a
tool result and narrates around it. The GM never gave up control.

The critical property: **a single, auditable thread of decisions**. From the
outside, one agent drove the turn. Inside that turn, a specialist was consulted.
The trace in debug mode shows a single conversation thread with a nested
sub-invocation.

### 3.2 Pattern 2 — Handoff (transfer of control)

The SDK also supports `handoff(target_agent)`. When an agent hands off, it
transfers control to another agent and **does not regain it**. The receiving agent
runs to completion and its output is the final output of the turn. There is no
return.

Handoffs are appropriate when the entire remaining work can be handled by the
receiving agent, and the originating agent has nothing more to do. Example: a
triage agent that reads a support ticket and hands it to a billing specialist,
then the billing specialist's response is the final answer.

In the game context, a handoff would mean: the GM receives the player's action,
hands off to the Referee, and the Referee's ruling becomes the player's output —
no narration, no story. That is wrong for this use case. The GM must always
narrate. Hence handoffs were not used here.

Handoffs will likely appear in M6 future blocks if the Lore Keeper or Critic
should produce a complete response independently. For now they remain unused.

### 3.3 Pattern 3 — Pipeline / review chain

Agents are chained in a **fixed sequence defined by code**, not by model
decision. Output of agent A becomes input of agent B, regardless of content.
Example: GM narrates a scene → Critic reviews it → if Critic approves, the
scene is shown; if not, the GM revises.

A pipeline is a **workflow** (see the vocabulary in
[`docs/teoria-de-agentes-y-qa.md`](../teoria-de-agentes-y-qa.md), section 7):
the code controls the sequence, not the model. It is more predictable than
agent-as-tool (the sequence never changes) but less flexible (the Critic always
runs, even on trivial turns).

The future Critic agent will likely use this pattern: every GM response passes
through a Critic review step before reaching the player. That step is
unconditional and code-controlled — a pipeline, not a dynamic tool call.

### 3.4 Why agent-as-tool was chosen for Block 1 — the four reasons

This was an explicit design decision with alternatives considered:

**Reason 1 — Testability and auditability.**
The agent-as-tool pattern preserves a single thread of decisions. There is one
agent driving the turn; one place to set a breakpoint, one conversation trace to
read. A handoff splits the trace into two independent conversations; reconstructing
what happened requires joining them. For a project whose first obligation is
testability, a single auditable thread is the right tradeoff.

**Reason 2 — Reversible control.**
The orchestrator always remains in charge. If the Referee's ruling is wrong,
the GM can (and the prompt tells it to) narrate around the problem rather than
blindly accepting it. With a handoff, the originating agent is gone; there is no
fallback. Keeping the GM as the persistent authority over the player's experience
is a design choice about responsibility, not just architecture.

**Reason 3 — Incremental adoption.**
From the Game Master's perspective, adding the Rules Referee was adding one more
tool entry. No restructuring of the game loop, no new `Runner` invocations, no
routing logic in `main.py`. The existing architecture absorbs the new agent
without a rewrite. That property — each specialist is "just a tool" — makes the
remaining M6 blocks straightforward to add.

**Reason 4 — Anthropic's guidance on autonomous agents.**
[`docs/teoria-de-agentes-y-qa.md`](../teoria-de-agentes-y-qa.md) (section 7)
records Anthropic's observation: most production systems need a controlled
workflow, not another autonomous agent. Agent-as-tool is the minimal step up from
a single agent — a controlled consult, not a transfer of authority. Adding agents
incrementally, with the orchestrator retaining control, is the path that preserves
predictability as the system grows.

---

## 4. Principles for working with multiple agents

These principles run through the entire M6 design. They are not abstract rules;
each connects to something in the code built in Block 1.

### 4.1 The result of an action must be decided by code, not by the model

This is the foundational principle, stated in M5 and deepened in M6. `can_afford`
is its clearest expression yet: the model translates a story action into three
integers; the function in `domain/rules.py` decides whether those integers are
satisfiable against the current `GameState`. The model's job stops at translation.

A prompt pushes probabilities, not guarantees. What MUST always happen — "you
cannot spend gold you do not have" — goes in deterministic Python that the model
cannot override. What the model controls — which tool to call, how to translate
the player's words into parameters — can be probabilistic, because the cost of
getting it wrong is bounded: the model describes the action incorrectly, the
function rejects it, and the model is told why. The code is the last line of
correctness.

In a QA context (see
[`docs/teoria-de-agentes-y-qa.md`](../teoria-de-agentes-y-qa.md), section 12):
a QA agent instructed to record test results will sometimes forget to call the
recording tool. The worst outcome is not that the result is missing — it is that
the system invents a "passed" status. The result must be decided by deterministic
code reading from validated state; the agent's job is to trigger that code, not to
be the source of truth itself.

### 4.2 Honest failure, never deceptive failure

Introduced in M5, this principle sharpens in M6 because `check_can_afford` makes
it concrete. When the player cannot afford something, the Referee receives:

```
Cannot afford: needs 5 gold but only has 3.
```

That exact string — produced by `can_afford` in `domain/rules.py:91–94` — is
relayed to the player. It names what is short. It cannot be softened or fudged by
the model because the model receives it as a tool result, not as something it
generates.

The `validate_action` predecessor did the opposite: it asked the model to decide
affordability, which meant the model could decide "yes" even when the player had
zero gold, because the decision was probabilistic. The new design makes the honest
gap a code output, not a model judgment.

Visible gaps are acceptable. Silent false positives are the cardinal error. In
QA: "no result recorded" is acceptable; "PASSED" when no check ran is
catastrophic.

### 4.3 Specialization plus coordination produces reliability

A single agent given ten jobs does each one with roughly one-tenth of its
attention. More precisely: each instruction competes for attention with every
other instruction, and a model that is simultaneously trying to narrate vividly,
remember to call `set_location`, check affordability, and update the summary will
periodically fail at one of them.

Giving each job to an agent with a narrow prompt and only the tools that job needs
is not about distributing load — the model capacity per agent call is the same. It
is about reducing competition for attention within each call. The Referee, asked
only to arbitrate and given only `roll_dice` and `check_can_afford`, has no
competing instructions. It cannot accidentally narrate (the instructions
explicitly forbid it), and it cannot accidentally mutate state (it has no mutation
tools).

This is why "a larger model" is not the answer to reliability problems in a
multi-tool agent. The answer is narrow scope.

### 4.4 Structured contracts between agents reduce ambiguity

The interface between the Game Master and the Rules Referee is:
- Input: a natural-language description of the player's action.
- Output: a ruling — a structured English sentence naming the decision, any dice
  rolled, and a one-line reason.

The interface between the Rules Referee and `check_can_afford` is:
- Input: three typed integers (`gold_cost: int`, `item_name: str`,
  `item_quantity: int`).
- Output: `"Affordable."` or `"Cannot afford: ..."`.

Both interfaces are narrow and typed. The GM–Referee interface uses structured
natural language (not free prose). The Referee–tool interface uses Python types
validated by the SDK's schema conversion.

Passing structured, typed values between agents reduces the ambiguity that causes
coordination failures. The Referee cannot be confused about what `gold_cost=5`
means. It can be confused about what "the player wants to buy a rope" means — but
that ambiguity lives at the natural-language boundary (GM to Referee), not at the
code boundary (Referee to tools). The goal is to push the boundary of ambiguity
as close to the model's input as possible, and make everything downstream
deterministic.

This maps directly to integration testing: the contract between two components
should be explicit and typed. A component that accepts `dict[str, Any]` is harder
to test and reason about than one that accepts a Pydantic model.

### 4.5 A tool call is the boundary between narration and persistent fact

The Block 2 persistence bug made this boundary visible in the most direct way
possible: the user played the game, earned gold in the story, and found zero gold
when they checked the `stats` command. The gold existed in the model's narration
— a string in the conversation history. It did not exist in `GameState` on disk.

The lesson is a sharper statement of the principle from section 4.1: it is not
enough for the model to narrate a consequence. The consequence becomes a
persistent fact only when a tool call writes it to validated state. Until that
call happens, the event is fictional — accurate in the story, absent from the
system.

This is easy to miss during development because the consequence looks correct in
the conversation output. The bug only becomes visible when the state is read back
from disk: on reload, on a `stats` command, on a `can_afford` check. The test
for "did this actually persist?" is always: close the session, reload, and check
the state. In QA terms: does the assertion hold after the session boundary?

The corollary for agent design is: whenever the system description says "the
player gains/loses X," there must be a tool call that writes X to validated
state. If the tool call is missing, the event did not happen from the system's
point of view — regardless of what the model narrated. Audit the tool calls, not
the narrative.

---

## 5. QA mindset in M6

**Contract tests over integration tests.**

The most important test property in M6 is that `test_rules_referee.py` runs
without an API key and without calling a real model. All seven tests in that file
(`tests/test_rules_referee.py`) assert on the module-level constants
`RULES_REFEREE_INSTRUCTIONS` and `GAME_MASTER_INSTRUCTIONS` — the behavioral
contracts. They verify:

- The Referee's instructions exist and are non-trivial.
- The Referee's instructions forbid narration ("do not narrate" appears in the
  text).
- The Referee's instructions require `skill_check` for uncertain outcomes, and
  assert "cannot overrule" the result.
- The Referee's instructions require `check_can_afford` for resource actions.
- The Referee's instructions name `earn_gold`, `spend_gold`, and `change_hp` as
  consequence-persistence tools, and explain why ("lost on reload").
- The Referee's instructions contain an honest-failure clause ("cannot rule
  without X").
- The Game Master's instructions delegate contested outcomes to `rules_referee`.

These are **behavioral contract tests**: they prove that the agents' instructions
encode the right commitments without requiring a live model to test those
commitments at runtime. The same principle applies to `GAME_MASTER_INSTRUCTIONS`
in `tests/test_smoke.py`: the contract is a string constant, and strings are
testable without an API key.

**Tool isolation enables unit testing of each agent's logic.**

Because `build_rules_referee()` and `build_game_master()` both import the SDK
lazily (inside the factory function, not at module top), importing
`RULES_REFEREE_INSTRUCTIONS` and `GAME_MASTER_INSTRUCTIONS` never requires the
SDK or an API key. The behavioral contract is always available to tests. Only the
factory function — which constructs the live `Agent` object — touches the SDK.
This is the M1 pattern extended to two agents.

**`can_afford` tests are the gold standard.**

`tests/test_rules.py:251–308` adds nine tests for `can_afford`. Each is a
pure-function test: build a `GameState`, call `can_afford`, assert on
`ActionResult.success` and the message text. No model, no SDK, no network. The
cases cover:

- No cost: trivially affordable.
- Enough gold: affordable.
- Not enough gold: fails with exact numbers in the message.
- Negative cost: rejected as invalid.
- Has item: affordable.
- Missing item: fails with item name in message.
- Not enough of the item: fails.
- Both gold and item missing: both shortfalls named in one message.
- Read-only: state is not mutated after a check.

The last case (`test_can_afford_does_not_mutate_state`) is the most important: it
confirms that `can_afford` is a genuine dry-run. An affordability check that
accidentally spent resources would be a serious bug that no type system catches
automatically.

**`resolve_check` tests prove the boundary between model judgment and code decision.**

`tests/test_dice.py` gained six tests for `resolve_check` (now 18 dice tests
total). Each uses a seeded `rng` to make the roll exact and deterministic. The
test cases cover:

- Success when the roll meets or exceeds the threshold (seed 5 → roll 20 → beats
  every level).
- Failure when the roll is below the threshold (seed 2 → roll 2 → fails "easy").
- The `>=` boundary: a roll exactly equal to the threshold counts as success.
- Reproducibility: same seed and difficulty always produce the same `CheckResult`.
- Rejection of an unknown difficulty name (`InvalidDifficultyError`).
- Case normalization: `"MODERATE"` is treated as `"moderate"`.

These tests are the specification for the mechanic. If `resolve_check` ever drifts
— if, say, someone changes `>=` to `>` and breaks the boundary case — the seeded
tests catch it immediately without running the game.

**`on_agent_start` debug output now names two agents.**

The `ToolActivityHooks` in `main.py` already printed `[debug] agent X is
working...` in M5 (when there was only one agent). In M6, debug mode shows which
agent is active per sub-invocation: the Game Master's `on_agent_start` fires, then
the Referee's fires when the GM calls the `rules_referee` tool. The observability
seam built in M5 now earns its value.

---

## 6. How to test / verify it yourself

```bash
# Inside an activated .venv with `pip install -e ".[dev]"` already run:

# Full deterministic suite (103 tests, no API key):
python -m pytest -m "not llm" -q
# Expected: 103 passed

# Contract tests for the Rules Referee (7 tests, includes Block 2 persistence checks):
python -m pytest tests/test_rules_referee.py -v
# Expected: all 7 tests pass

# Tests for can_afford (9 tests in test_rules.py):
python -m pytest tests/test_rules.py -v -k "can_afford"
# Expected: 9 tests pass

# Tests for resolve_check (6 tests in test_dice.py):
python -m pytest tests/test_dice.py -v -k "check"
# Expected: 6 tests pass

# Full per-file breakdown:
python -m pytest tests/test_smoke.py         -q    # 10 tests
python -m pytest tests/test_dice.py          -q    # 18 tests (12 original + 6 resolve_check)
python -m pytest tests/test_state.py         -q    # 9 tests
python -m pytest tests/test_models.py        -q    # 21 tests
python -m pytest tests/test_rules.py         -q    # 38 tests (29 original + 9 can_afford)
python -m pytest tests/test_rules_referee.py -q    # 7 tests
```

**Verify the contract directly (no API key):**

```python
# Read the Referee's instructions constant without touching the SDK:
from dungeon_agents.agents.rules_referee import RULES_REFEREE_INSTRUCTIONS
print(RULES_REFEREE_INSTRUCTIONS)
# Expected: the full instruction block; contains "roll_dice", "check_can_afford",
# "do not narrate", and an honest-failure clause.

# Read the GM's updated instructions:
from dungeon_agents.agents.game_master import GAME_MASTER_INSTRUCTIONS
print("rules_referee" in GAME_MASTER_INSTRUCTIONS)  # True
print("roll_dice" in GAME_MASTER_INSTRUCTIONS)       # False (GM no longer rolls dice)
```

**Verify `can_afford` at the REPL (no API key):**

```python
from dungeon_agents.domain.models import GameState, InventoryItem, Player
from dungeon_agents.domain.rules import can_afford

state = GameState(player=Player(name="Aria", gold=3))

# 1. Affordable — has enough gold
r = can_afford(state, gold_cost=3)
print(r.success, r.message)  # True "Affordable."

# 2. Not affordable — not enough gold
r = can_afford(state, gold_cost=5)
print(r.success, r.message)  # False "Cannot afford: needs 5 gold but only has 3."

# 3. Both gold and item missing in one check
r = can_afford(state, gold_cost=5, item_name="Rope")
print(r.success)   # False
print(r.message)   # "Cannot afford: needs 5 gold but only has 3; needs 1x Rope but has 0."

# 4. Read-only: state is untouched after any check
can_afford(state, gold_cost=3)
print(state.player.gold)  # 3 (unchanged)
```

**Verify `resolve_check` at the REPL (no API key):**

```python
import random
from dungeon_agents.domain.dice import resolve_check, DIFFICULTY_THRESHOLDS

# 1. Inspect the thresholds — they are testable constants, not magic numbers
print(DIFFICULTY_THRESHOLDS)
# {'trivial': 3, 'easy': 5, 'moderate': 10, 'hard': 15, 'very_hard': 18}

# 2. Reproduce an exact roll with a seeded RNG
result = resolve_check("hard", rng=random.Random(5))
print(result.roll, result.threshold, result.success)
# 20 15 True  (seed 5 produces a 20 on 1d20; 20 >= 15 -> success)

# 3. Confirm failure is also exact and reproducible
result = resolve_check("easy", rng=random.Random(2))
print(result.roll, result.threshold, result.success)
# 2 5 False  (seed 2 produces a 2; 2 < 5 -> failure)

# 4. Unknown difficulty fails loudly rather than guessing
from dungeon_agents.domain.dice import InvalidDifficultyError
try:
    resolve_check("impossible")
except InvalidDifficultyError as e:
    print(e)  # unknown difficulty 'impossible'; expected one of: easy, hard, ...
```

**Verify persistence tools at the REPL (no API key, requires a writable data/
directory):**

```python
from dungeon_agents.domain import state
from dungeon_agents.domain.models import GameState, Player

# Seed a fresh state with known gold and HP
fresh = GameState(player=Player(name="Aria", hp=80, gold=10))
state.save_state(fresh)

# Apply earn_gold and confirm it persists
from dungeon_agents.domain import rules
result = rules.earn_gold(state.load_state_or_none(), 5)
if result.success:
    state.save_state(result.new_state)

reloaded = state.load_state_or_none()
print(reloaded.player.gold)   # 15

# Apply change_hp (damage) and confirm clamp behavior
result = rules.change_hp(reloaded, -90)  # more damage than current HP
if result.success:
    state.save_state(result.new_state)

reloaded2 = state.load_state_or_none()
print(reloaded2.player.hp)    # 0  (clamped, not negative)
```

**Live game verification (requires an API key):**

```bash
dungeon-agents
# With DUNGEON_DEBUG=1 (or typing `debug` at the prompt), observe the agent handoff:
#
#   You: I try to buy a rope from the merchant for 5 gold
#
#   [debug] agent Game Master is working...
#   [debug] Game Master -> tool rules_referee...
#   [debug] agent Rules Referee is working...
#   [debug] Rules Referee -> tool check_can_afford...
#   [debug]   check_can_afford -> Cannot afford: needs 5 gold but only has 0. (NN ms)
#   [debug]   rules_referee -> DISALLOWED: the player has 0 gold, cannot spend 5. (NN ms)
#
# The GM then narrates the refusal in-character, around the Referee's ruling.
#
#   You: I try to climb the castle wall
#
#   [debug] agent Game Master is working...
#   [debug] Game Master -> tool rules_referee...
#   [debug] agent Rules Referee is working...
#   [debug] Rules Referee -> tool skill_check(difficulty='hard')...
#   [debug]   skill_check -> FAILURE: rolled 7 on 1d20 vs hard (needs 15+). (NN ms)
#   [debug]   Rules Referee -> tool change_hp(delta=-4)...
#   [debug]   change_hp -> HP changed by -4. Aria now has 76/100 HP. (NN ms)
#   [debug]   rules_referee -> DISALLOWED: rolled 7 vs hard (needs 15+); fall deals 4 damage. (NN ms)
#
# The GM narrates the fall in-character. The HP change is already on disk.
```

---

## 7. Risks & tradeoffs

**The Referee's ruling quality depends on the model.**

The Referee's ruling is natural-language text — "ALLOWED. Rolled 14 on 1d20 vs a
moderate climb (needs 10+): success." The Game Master receives this as a tool
result string and narrates around it. The GM cannot verify the ruling's internal
consistency; it trusts the Referee. If the Referee produces a malformed or
ambiguous ruling (e.g. gives a number without context), the GM may narrate
incorrectly. This is the model-reliability problem re-expressed at the
inter-agent boundary. The mitigation is the Referee's narrow scope and explicit
instructions: less surface area means fewer modes of failure.

**Two model calls per turn (when the Referee is consulted).**

Before M6, a turn with a contested action required one GM call, which might roll
dice internally. In M6, a contested action triggers: one GM call → one Referee
call (which may roll dice) → result back to GM → GM narrates. That is at minimum
two model calls per contested action. Latency increases. On a fast model like
`claude-haiku-4-5`, this is usually acceptable (a few extra seconds), but users on
a slow connection or a rate-limited key will notice. Future blocks should measure
whether the additional specialization justifies the latency cost.

**The Game Master still holds mutation tools.**

The GM can call `add_item`, `remove_item`, `get_inventory`, `set_location`,
`set_quest`, and `update_summary` directly, without consulting the Referee. The
architectural separation between narration (GM) and arbitration (Referee) is only
enforced by the GM's instructions, not by hard tool boundaries. If the GM
incorrectly decides to add an item without checking whether the player won it
fairly, nothing in the code prevents it. Future blocks (Inventory Keeper) will
address this by moving mutation tools from the GM to a dedicated keeper agent.

**`validate_action` is retired with no migration path.**

Any prompt or tool calling `validate_action` by name after this change will
receive an error. The function is gone. If a test or an external script relied on
it, it will break. In this project that is fine — no external callers existed —
but in a production system, retiring a tool name without a deprecation period
would require careful coordination with all callers.

**The honest-gap principle is still probabilistic at the GM–Referee boundary.**

`can_afford` is deterministic. But the GM's decision of **when** to call
`rules_referee` (and therefore when the Referee calls `check_can_afford`) is a
model probability. If the GM narrates a purchase without consulting the Referee,
the affordability check never runs. The design mitigation is the GM's instructions
("for actions that spend gold or use items, consult the `rules_referee` tool") and
the observable debug output. The code is correct; the model is the variable. The
correct response to model non-compliance is an honest gap, not a fabricated
validation.

**Named difficulty levels constrain the model's authority, but not its accuracy.**

`skill_check` bounds the Referee to five named levels. That prevents the model
from choosing `threshold=1` to guarantee success. It does not prevent the Referee
from choosing "trivial" for what the story would call "very hard" — the judgment
call of which level to assign is still a model probability. The mitigation is the
same as for `check_can_afford`: the Referee's instructions establish a vocabulary
for matching level to action, and debug output makes the choice visible. A future
improvement could add a Critic step that reviews the Referee's difficulty
assignment for consistency with the fiction.

**Persistence of consequences depends on the Referee calling the right tools.**

`change_hp` and `earn_gold` / `spend_gold` are only called if the Referee's model
decides to call them. An incomplete ruling — one that decides "the player takes 4
damage" but does not call `change_hp(-4)` — leaves the consequence un-persisted.
The instructions explain the consequence of not calling ("lost on reload"), which
increases the probability of compliance. The observable debug output makes
omissions visible. As with all instruction-driven behaviors in this project: the
code is the specification; the model is the variable; the correct response to
omission is a visible gap and a logged event, not a fabricated state.

---

## 8. Bridge to TestOps AI

The multi-agent patterns introduced in M6 are the direct precursor to a
distributed QA system where specialist agents handle different phases of test
evaluation.

| Dungeon Agents (M6) | TestOps AI equivalent |
|---------------------|----------------------|
| Rules Referee: one narrow job, narrow tool set | A "Result Validator" agent: one job (decide pass/fail), access only to the assertion library, no side effects |
| `check_can_afford`: code decides, model translates | A test assertion: code evaluates the condition; the agent triggers the assertion with the correct parameters |
| `validate_action` retired for a misleading name | Any QA tool named `validate_*` that defers the decision to a model is misnamed and misdesigned — rename and rewrite |
| GM instructs Referee; Referee may not be consulted | QA orchestrator instructs result-recording agent; agent may skip steps — design for partial compliance, not assumed compliance |
| Agent-as-tool: one auditable thread | Orchestrator-pattern evaluation pipeline: one trace to audit, one place to set breakpoints, one conversation log |
| Handoff: control does not return | Pass-off to a human reviewer or an async verification step — appropriate when the orchestrator has nothing more to contribute |
| Pipeline: code-controlled sequence | Fixed evaluation pipeline: test execution → result extraction → validation → reporting, each step unconditional and code-ordered |
| Referee's ruling is structured English | An evaluator agent's verdict should be structured and typed (JSON with `success: bool` and `reason: str`), not free prose |
| `on_agent_start` names which agent is working | Audit log entry: which evaluation agent ran which assertion, and at what timestamp |
| Referee cannot mutate narration state | A validation agent should be read-only: it asserts, does not modify. Mutation lives in a separate dedicated agent |
| `earn_gold` / `change_hp`: consequence persisted by the Referee's tool call | Test result written by the recorder agent's tool call — narrating "test passed" without calling the record tool is the same bug |
| `skill_check`: model judges difficulty; code decides outcome | Evaluation metric: model interprets test output and classifies severity; code (threshold rule) decides pass/fail — never ask the model to hold the verdict |
| Seeded `rng` makes dice deterministic under test | Seeded or mocked randomness in evaluation logic makes QA pipelines reproducible — flaky evaluators are worse than flaky tests |
| User played the game and found the persistence bug | Real users find the gaps that tests miss — build observability (debug mode, stats command) so gaps surface quickly during QA of the QA system |

**The deepest transfer: specialization is the path to a trustworthy QA verdict.**

A single QA agent asked to execute a test, evaluate the result, record the
finding, update the test run, and file a bug report if it fails is a single agent
with seven competing jobs. Each job is done with reduced attention. The most
dangerous failure mode is a fabricated "passed" issued because the agent was
attending to narration — excuse, reporting — and did not actually run the
evaluation.

Separating "execute" from "evaluate" from "record" into agents with narrow
instructions and only the tools their job requires is the same structural answer
M6 applies to the game. In TestOps AI, this separation also creates a natural
audit trail: each agent's contribution is a distinct step in a traceable pipeline,
not a buried step inside one large agent's context.

The lesson from `validate_action → check_can_afford` is directly applicable: any
tool in a QA system named `validate_*` or `check_*` that does not perform
deterministic validation in code is misnamed. The name makes callers trust it as a
decision; if the decision is actually probabilistic, that trust is misplaced.
Honest naming and honest implementation are the same discipline.

**The Block 2 lesson: a tool call is the boundary between narration and record.**

The persistence bug found in Block 2 is structurally identical to the most
dangerous failure mode in a QA recording system: an agent that narrates "the test
passed" without calling the tool that writes the result to the database. The test
run looks complete in the conversation; the database shows no result. The next
report either omits the test (a silent gap) or, worse, inherits the previous run's
result (a silent false positive).

The mitigation in both systems is the same: (1) the tool call is the write;
narration without a tool call is not a write; (2) build a state-reading command
(`stats`, or a test-results query) that reads from the validated store and makes
the gap immediately visible; (3) use debug-mode observability to audit whether the
tool was actually called. The session boundary — close, reload, check — is the
test for persistence. In TestOps AI, the equivalent test is: close the agent
session, query the database, and verify the result is there.

---

## 9. What's next — remaining M6 blocks

**Inventory Keeper (next block).**
The `add_item`, `remove_item`, and `get_inventory` tools currently live with the
Game Master. Moving them to a dedicated Inventory Keeper agent narrows the GM
further and creates a single agent responsible for inventory truth. The GM would
call the Inventory Keeper as a tool for any inventory read or mutation, the same
pattern used for the Referee.

**Lore Keeper (future block).**
`update_summary`, `set_location`, `set_quest`, and `last_scene` management are
natural candidates for a Lore Keeper that owns the narrative record. The GM
consults the Lore Keeper to update or retrieve story context, rather than holding
those tools itself.

**Critic (future block).**
A Critic agent that reviews the GM's draft response before it reaches the player.
This is likely a pipeline step (unconditional code-controlled review), not an
agent-as-tool call — the Critic always runs, and if it objects, the GM revises.
This introduces the concept of a review chain, the third coordination pattern.

**Handoff exploration (future block).**
Once all specialists exist, there will be scenarios where a full handoff is
appropriate — for example, when the player's action is purely about inventory
management and the Inventory Keeper can resolve the entire turn without GM
narration. Block 1 deliberately chose not to use handoffs to preserve narration
control; future blocks will explore the cases where handoffs are correct.

**Wiring win/lose detection (carryover from M5).**
`is_game_won` and `is_game_over` from M4 are still not called after each turn in
`main.py`. Wiring this is a small step, deferred again in M6 because the agent
architecture was the priority.

**Inter-agent testing patterns.**
A Rules Referee that returns correct rulings in isolation may behave differently
when invoked by a Game Master with a partial or contradictory context. M6's future
blocks will develop test patterns for agent interactions — not just contract tests
on constants, but behavioral tests on the coordination itself. This is the deepest
QA challenge the project has not yet addressed.
