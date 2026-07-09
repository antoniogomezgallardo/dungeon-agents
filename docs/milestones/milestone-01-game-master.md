# Milestone 1 — Single Game Master Agent

> **Status:** ✅ Done
> **Theme:** Get one agent talking to a human through a clean, testable console loop.

> **Update (2026-07-09) — provider is now selectable.** After M1 shipped, the
> project was adapted to run on **Anthropic (Claude) by default**, or OpenAI,
> chosen via `DUNGEON_PROVIDER`. Where this document below says `OPENAI_API_KEY`
> or `gpt-4o-mini`, read it as *"the selected provider's key / default model."*
> Concretely: `config.Settings` now carries `provider`, `api_key`, and `model`
> (not a hard-coded `openai_api_key`); the default is `anthropic` +
> `claude-haiku-4-5` ($1/$5 per 1M tokens); and Anthropic is reached through the
> OpenAI Agents SDK's **LiteLLM adapter**. The *design lessons in this doc are
> unchanged* — this is exactly the "isolate the vendor behind config" payoff the
> doc argues for, demonstrated in practice. See §2.4 (note below the heading) and the README
> for the current shape.

---

## 1. Goal

Build the smallest thing that is *actually an agent application*: a terminal
program where you type an action and a single AI **Game Master** replies with a
short fantasy scene, always ending with 2–3 choices. No tools, no persistence,
no multiple agents — those are later milestones.

The point of starting this small is not laziness. It's that **you can't learn
tool calling, guardrails, or multi-agent handoffs until you have a working
single-agent loop to hang them on.** M1 is the skeleton every later milestone
bolts onto. If the skeleton is clean and testable, everything after it is
easier. If it's messy, every later milestone inherits the mess.

---

## 2. What was built — point by point

### 2.1 `pyproject.toml` — the project definition

**What:** declares the package, its dependencies, a console-script entry point
(`dungeon-agents`), and a pytest marker (`llm`).

**Why it matters:**
- Using `pyproject.toml` (the modern standard) instead of loose scripts means
  the project is **installable** (`pip install -e .`). Installability is what
  lets `import dungeon_agents` work from anywhere and lets tests find the code
  the same way a user would. It removes "works on my machine, in my folder"
  fragility.
- The `[project.scripts]` line `dungeon-agents = "dungeon_agents.main:main"`
  turns a Python function into a real terminal command. This is a small taste
  of **packaging as a product** — the same mechanism you'd use to ship a CLI.
- The `markers` section registers `llm` so pytest knows about it and doesn't
  warn. We defined the marker *before* writing any LLM test, because we already
  know M7 will need to separate expensive, non-deterministic tests from cheap,
  deterministic ones. Declaring intent early keeps the test suite honest.

> **QA lens:** the `requires-python = ">=3.11"` line is an *acceptance
> criterion encoded in config* — install fails loudly on an unsupported
> interpreter instead of breaking mysteriously later.

### 2.2 `.env.example` and `.gitignore` — secrets and hygiene

**What:** `.env.example` is a committed template listing the variables the app
reads (`OPENAI_API_KEY`, `DUNGEON_MODEL` at M1; updated after M1 to
`DUNGEON_PROVIDER`, `ANTHROPIC_API_KEY`, and `DUNGEON_MODEL` — see addendum at
the top of this document). `.gitignore` ensures the real `.env` (with your
actual key) is never committed, along with build artifacts and the future
`data/` directory.

**Why it matters:**
- **Never commit secrets.** The `.example` convention is the standard way to
  document *what* configuration exists without leaking the *values*. A new
  developer copies it to `.env` and fills in their own key.
- Git-ignoring `data/` now (before it exists) means M2's saved game state won't
  accidentally get committed. Anticipating this costs one line today.

### 2.3 `config.py` — the single source of configuration truth

**What:** one module that reads environment variables and returns an immutable
`Settings` object. Nothing else in the codebase calls `os.getenv`.

```python
@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    model: str

    @property
    def has_api_key(self) -> bool:
        return bool(self.openai_api_key)
```

**Why it matters — this is one of the most important decisions in M1:**
- **One place to read env vars.** When configuration lives in twelve different
  files, changing how the app is configured means hunting through all twelve.
  Here, there's exactly one place. This is the *Single Responsibility
  Principle* applied to configuration.
- **`frozen=True` makes it immutable.** Config can't be accidentally mutated
  mid-run, so behavior can't silently drift. What you load is what you get.
- **Testability.** Because config is a plain function returning a plain object,
  tests can call `load_settings()` under a controlled environment
  (`monkeypatch.setenv(...)`) and assert on the result — no mocking of the
  whole OpenAI client needed.
- **`has_api_key` is a named intent, not a scattered `if os.getenv(...)`.** The
  console loop asks `settings.has_api_key` — readable, and testable in isolation
  (see `test_has_api_key_flag`).

> **QA lens:** centralized config is *observability + reproducibility*. To
> reproduce a run, you only need to know the contents of `Settings`. To observe
> what a run will do, you read one object.

### 2.4 `agents/game_master.py` — the agent, and its contract as data

> **Update (2026-07-09):** after the provider change, `build_game_master` no
> longer passes `settings.model` directly. A private `_resolve_model(settings)`
> helper now sits between them: for `anthropic` it returns a
> `LitellmModel(model="anthropic/<id>", api_key=settings.api_key)` object; for
> `openai` it returns the bare model string. The factory signature and the
> instructions constant are unchanged; only the model-wiring gained one level of
> indirection.

**What:** the Game Master's behavior instructions live in a module-level
constant `GAME_MASTER_INSTRUCTIONS`; a `build_game_master(settings)` factory
constructs the actual SDK `Agent` from them.

```python
GAME_MASTER_INSTRUCTIONS = """..."""   # the behavioral contract, as plain text

def build_game_master(settings: Settings):
    from agents import Agent          # imported lazily
    return Agent(name="Game Master",
                 instructions=GAME_MASTER_INSTRUCTIONS,
                 model=settings.model)
```

**Why it matters:**
- **The prompt is a testable artifact.** By keeping the instructions as a
  module constant instead of an inline string buried in the SDK call, a test
  can `import` it and assert the behavioral contract is present — e.g. that it
  says "2 or 3" choices and "concise" — *without spending a cent on an API
  call*. See `test_game_master_contract_mentions_choices`. This is a
  lightweight, deterministic proxy for behavior you'll verify for real in M7.
- **The factory pattern separates *definition* from *construction*.** The
  constant describes *what the agent should do*; the factory *builds it* using
  runtime settings (like the model). You can reason about, diff, and review the
  behavior without running anything.
- **Lazy import (`from agents import Agent` inside the function).** The SDK is
  only imported when we actually build the agent. This means the smoke test can
  `import GAME_MASTER_INSTRUCTIONS` even if the SDK isn't installed — a
  deliberate choice that keeps the deterministic test suite dependency-light.

> **QA lens:** this is *traceability*. The behavioral requirement ("end with
> 2–3 choices") maps to a line in the instructions, which maps to an assertion
> in a test. Requirement → implementation → verification, all visible.

### 2.5 `main.py` — the console loop

**What:** all input/output and the turn loop. Loads settings, bails politely if
there's no key, builds the agent, then loops: run the agent → print the scene →
read the player's input → append it → repeat, until the player exits.

**Why it matters, decision by decision:**

- **I/O is separated from the agent.** `main.py` does console work; the agent
  lives elsewhere. This is the classic separation between *interface* and
  *logic*. It means we could later swap the console for a web UI or a test
  harness without touching the agent, and we can test the agent without a
  console.

- **Graceful no-key path.** If there's no API key, the app prints a friendly
  instruction and returns — it does **not** crash with a stack trace, and it
  never even imports the SDK. The message names the specific env var the
  selected provider needs (via `settings.api_key_env_name`) and shows which
  provider is active. Compare the two experiences: a new user running the app
  with no key gets a sentence telling them exactly what to do, versus a wall of
  red traceback. *Failing safely and legibly is a feature.*

- **Conversation continuity (lines 59–65).** We keep a `conversation` list and,
  after each turn, replace it with `result.to_input_list()` — the SDK's
  accumulated history (the user turns *and* the assistant's replies). Feeding
  that back in next turn is **how the Game Master remembers what happened**.
  Without this, every turn would start from a blank slate and the story would
  have amnesia. This is your first encounter with **conversation state**, and
  it foreshadows the bigger *external state* problem in M2–M3.

- **Multiple clean exits (lines 67–75).** `exit`/`quit` typed by the player, and
  `Ctrl+C`/end-of-input (`KeyboardInterrupt`/`EOFError`) are all caught and turn
  into a tidy farewell. A program that only handles the happy path isn't done.

- **`Runner.run_sync` (line 62).** The SDK's synchronous runner drives the whole
  agent turn — sending the conversation to the model and returning a result
  with `.final_output` (the text) and `.to_input_list()` (the new history). In
  M1 the agent has no tools, so a "turn" is just one model reply. In M2, when we
  add tools, the *same* `run_sync` call will transparently handle the
  model→tool→model round-trips. Learning this call now pays off later.

- **Rich for output (`Panel`, `Markdown`).** Purely presentational, but it makes
  the console pleasant and renders the numbered choices nicely. Kept in `main`
  so it never leaks into the agent or domain logic.

### 2.6 `tests/test_smoke.py` — evidence, with no API key

**What:** eight tests that verify the package imports, config defaults and
overrides work, provider selection, the `has_api_key` flag, and the GM
instructions encode the behavioral contract. **They pass with no API key and
no SDK installed.**

**Why it matters:**
- A **smoke test** answers the most basic question — "is the thing even
  wired together?" — fast and cheaply. If the package doesn't import, nothing
  else matters, and you want to know in 0.1 seconds, not after a model call.
- **No API key required** is a hard requirement of the whole project (it's an
  M7 acceptance criterion). Deterministic tests that need no secret and no
  network are the ones you can run on every commit, in CI, for free, and get
  the *same answer every time*. That repeatability is the foundation of trust
  in a test suite.
- These tests are **fast, deterministic, and isolated** — three properties of a
  good unit test. The `monkeypatch` fixture lets us set/unset env vars for a
  single test without polluting others.

---

## 3. Concepts you learned in M1

| Concept | Where it showed up | Why it transfers |
|--------|--------------------|------------------|
| The agent loop | `run()` while-loop + `Runner.run_sync` | Every agent app is a loop: input → agent → output → repeat. |
| Conversation state | `to_input_list()` fed back each turn | State management is *the* recurring hard problem in agents. |
| Separation of concerns | config / agent / I/O in three files | Lets you test and swap pieces independently. |
| Prompt-as-artifact | `GAME_MASTER_INSTRUCTIONS` constant | Behavior you can review, diff, and test cheaply. |
| Safe failure | no-key path, exit handling | Real software handles the unhappy path. |
| Deterministic testing | `test_smoke.py` with no key | The bedrock of a trustworthy CI suite. |

---

## 4. QA mindset in M1

Even at this tiny scale, the project already reflects a tester's instincts:

- **Testability:** the agent's contract is assertable without spending money or
  hitting the network.
- **Observability:** to know how a run is configured, you read one `Settings`
  object; to know how the agent behaves, you read one instructions constant.
- **Reproducibility:** deterministic tests give the same result every run;
  config is immutable.
- **Safe failure:** missing key → friendly message, not a crash; Ctrl+C →
  graceful exit.
- **Traceability:** requirement ("2–3 choices") → instruction line → test
  assertion. You can follow the thread end to end.

---

## 5. How to test / verify it yourself

```bash
# Deterministic suite — no API key needed
python -m pip install pytest python-dotenv pydantic rich
python -m pip install -e . --no-deps          # install the package itself
python -m pytest -m "not llm" -q              # expect: 8 passed

# Verify the safe-failure path (no key set):
#   prints a friendly "No <PROVIDER_KEY_ENV> found." message, no traceback
#   (e.g. "No ANTHROPIC_API_KEY found." for the default provider)

# Full run (needs a key):
python -m pip install -e .                     # pulls the SDK too
copy .env.example .env                          # then edit .env, add your key
dungeon-agents                                  # play; type `exit` to quit
```

**Expected smoke-test result:** `8 passed`.

---

## 6. Risks & tradeoffs (what we deliberately deferred)

- **No live end-to-end test yet.** We test the *contract* of the GM, not a real
  model reply. That's intentional: live tests are slow, cost money, and are
  non-deterministic (the model won't say the same thing twice). They belong in
  M7 behind the `llm` marker, kept out of the default suite. **Tradeoff:** the
  smoke test can't catch "the model ignored its instructions" — only M7 can.
- **Conversation grows unbounded.** Every turn is kept in full. For a long
  session this would eventually cost more tokens and could hit context limits.
  Fine for a learning demo; the *Lore Keeper* agent in M5 exists partly to
  summarize and bound this.
- **No persistence.** Close the app and the adventure is gone. Deliberate — M2
  introduces saving/loading so we can teach *external state* as its own topic.
- **Minimal structure.** We did **not** pre-create empty files for future
  milestones. That's a conscious anti-overengineering choice: files appear when
  a milestone needs them, so the repo always reflects what actually exists.

---

## 7. Bridge to TestOps AI

The Game Master is a stand-in for a future **Test Strategy Agent**. Everything
structural here carries over unchanged:

- The **single-agent loop** is the same shape whether the agent narrates a
  dungeon or drafts test scenarios from a user story.
- **Config centralization** and **safe failure** are non-negotiable in a real
  QA product (which will handle real credentials and must never crash on bad
  input).
- **Prompt-as-testable-artifact** becomes critical: in TestOps AI you'll want
  to assert that your Test Strategy Agent's instructions still say the right
  things after every edit — exactly what `test_game_master_contract_*` does.

---

## 8. What's next — Milestone 2

Add **deterministic tools** the agent can call: `roll_dice`, `load_game_state`,
`save_game_state`. The big new idea is that **some things must not be left to
the LLM** — a dice roll must come from real randomness with validated bounds,
not from the model making up a number. This is the first place we'll enforce
*"business rules belong in Python, not in the prompt."*
