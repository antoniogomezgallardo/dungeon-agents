"""Agent guardrails — the SDK layer over deterministic safety logic (M7).

Thin wrappers that expose the pure `domain/guardrails.py` checks to the OpenAI
Agents SDK as an `@input_guardrail`. The SDK runs an input guardrail BEFORE the
agent sees the player's message; if the guardrail's `tripwire_triggered` is True,
the SDK raises `InputGuardrailTripwireTriggered` and the agent never processes the
input. Same split as tools: the decision lives in the tested domain, this layer
only adapts it to the SDK and reports the verdict.

Built inside functions / imported lazily so importing this module never requires
the SDK or an API key (the domain check stays test-safe on its own).
"""

from __future__ import annotations

from dungeon_agents.config import Settings
from dungeon_agents.domain.guardrails import detect_injection


def build_injection_guardrail(settings: Settings):
    """Return an SDK input guardrail that blocks prompt-injection attempts.

    Defense in depth, two layers:
    1. `detect_injection` (deterministic patterns) — blocks the obvious for free.
    2. If layer 1 lets it through, an LLM judge (`build_injection_judge`) is asked
       whether it is a novel manipulation the patterns missed. Either layer firing
       trips the wire.

    `output_info` carries which layer blocked (`pattern:<label>` or `llm`) so the
    caller can tell the player, in character, that the attempt was ignored — an
    honest, visible block rather than silent obedience.
    """
    from agents import GuardrailFunctionOutput, Runner, input_guardrail

    from dungeon_agents.agents.injection_judge import (
        JUDGE_INJECTION,
        build_injection_judge,
    )

    # Built once and reused across turns; it has no per-turn state.
    judge = build_injection_judge(settings)

    @input_guardrail
    async def injection_guardrail(context, agent, user_input):
        # user_input may be a string or the SDK's structured input list; reduce it
        # to text for the checks.
        text = user_input if isinstance(user_input, str) else str(user_input)

        # Layer 1: cheap deterministic patterns.
        pattern = detect_injection(text)
        if pattern.detected:
            return GuardrailFunctionOutput(
                output_info={"blocked_by": f"pattern:{pattern.label}"},
                tripwire_triggered=True,
            )

        # Layer 2: LLM judge for novel phrasings the patterns can't catch. Runs
        # only on inputs that survived layer 1 (one model call per surviving turn).
        verdict = (await Runner.run(judge, text)).final_output.strip().upper()
        is_injection = verdict.startswith(JUDGE_INJECTION)
        return GuardrailFunctionOutput(
            output_info={"blocked_by": "llm" if is_injection else ""},
            tripwire_triggered=is_injection,
        )

    return injection_guardrail
