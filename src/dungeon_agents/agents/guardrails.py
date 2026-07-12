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

from dungeon_agents.domain.guardrails import detect_injection


def build_injection_guardrail():
    """Return an SDK input guardrail that blocks prompt-injection attempts.

    The guardrail runs `detect_injection` on the player's input and trips the wire
    when it looks like an attempt to hijack the agent (override instructions,
    reassign its role, extract its prompt). `output_info` carries the matched
    pattern label so the caller can tell the player, in character, what was
    ignored — an honest, visible block rather than silent obedience.
    """
    from agents import GuardrailFunctionOutput, input_guardrail

    @input_guardrail
    async def injection_guardrail(context, agent, user_input):
        # user_input may be a string or the SDK's structured input list; reduce it
        # to text for the pattern check.
        text = user_input if isinstance(user_input, str) else str(user_input)
        result = detect_injection(text)
        return GuardrailFunctionOutput(
            output_info={"label": result.label},
            tripwire_triggered=result.detected,
        )

    return injection_guardrail
