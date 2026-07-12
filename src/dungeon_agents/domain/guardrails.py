"""Prompt-injection detection — deterministic safety logic (Milestone 7).

A guardrail is a control that keeps an agent inside safe behavior even when the
model would drift outside it. This module holds the FIRST guardrail: detecting a
player's attempt to hijack the Game Master — "prompt injection" — such as telling
it to ignore its instructions, reveal its system prompt, or act as a different
assistant.

The project's core lesson, applied to security: what MUST hold (the player cannot
seize control of the agent) belongs in tested code, not in a prompt that merely
asks the model to resist. `detect_injection` is pure Python — it decides; the SDK
`@input_guardrail` wrapper (in the agents layer) just acts on its verdict.

Design choice (documented as a decision): this is PATTERN-BASED detection — cheap,
deterministic, and unit-testable without an API key, but only as good as its
pattern list (it can miss a novel phrasing). That is an honest first line of
defense, not a complete one; an LLM-based guardrail for novel attacks is a
deliberate later step layered on top. We start with the cheap, testable base.

The hard part is NOT catching attacks — it's NOT catching legitimate play. A game
is full of words like "ignore" ("I ignore the guard") and "system" ("I inspect
the temple's system of levers"). The patterns below target the *instruction-
manipulation* shape (addressing the assistant, overriding rules, extracting the
prompt), not those words in isolation, so normal actions pass through untouched.

Pure Python, no SDK. Fully unit-testable without an API key.
"""

from __future__ import annotations

import re

# Each pattern targets a manipulation SHAPE, not a lone keyword. They are matched
# case-insensitively against the player's input. Kept as a named list so the
# detection surface is explicit, testable, and easy to extend.
_INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Overriding or discarding the agent's instructions.
    (r"\bignore\s+(all\s+|the\s+|your\s+|previous\s+|above\s+)*instructions?\b",
     "override-instructions"),
    (r"\bdisregard\s+(all\s+|the\s+|your\s+|previous\s+|above\s+)",
     "disregard-instructions"),
    (r"\bforget\s+(everything|all|your|the|previous|above)\b.*\b(instruction|rule|prompt)",
     "forget-instructions"),
    # Reassigning the AGENT's identity / role. Targeted at "you" (the agent) or at
    # AI/assistant roles — NOT generic in-world role-play like "I pretend to be a
    # merchant" or "act quickly", which are legitimate actions in a fantasy game.
    (r"\byou\s+are\s+(now\s+)?(a|an|no\s+longer)\b", "reassign-role"),
    (r"\b(pretend|act)\s+(to\s+be|as|you\s+are|you're)\s+"
     r"(a\s+|an\s+)?(\w+\s+)?(ai|assistant|chatbot|language\s+model|llm|bot)\b",
     "reassign-role"),
    (r"\bfrom\s+now\s+on\b.*\byou\b", "reassign-role"),
    # Extracting the system prompt / hidden instructions.
    (r"\b(system|initial|original)\s+prompt\b", "extract-prompt"),
    (r"\b(reveal|show|print|repeat|tell\s+me)\b.*\byour\b.*\b(instructions?|prompt|rules?)\b",
     "extract-prompt"),
    (r"\bwhat\s+(are|is|'?s)\s+your\b.*\b(instructions?|prompt|rules?|guidelines)\b",
     "extract-prompt"),
    # Trying to speak as the privileged/system role.
    (r"\bas\s+(the\s+)?(system|developer|admin)\b", "impersonate-system"),
    (r"^\s*(system|assistant|developer)\s*:", "impersonate-system"),
    # Meta-references that only make sense when attacking the model, not the game.
    (r"\byour\s+(system\s+)?(instructions?|prompt|guidelines)\b", "reference-instructions"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in _INJECTION_PATTERNS]


class InjectionResult:
    """The verdict of an injection check — a small, explicit result object.

    `detected` is the decision the guardrail acts on; `label` names which pattern
    fired (for logging and for telling the player, in character, what was ignored).
    Plain attributes keep this module dependency-free.
    """

    def __init__(self, *, detected: bool, label: str = "") -> None:
        self.detected = detected
        self.label = label

    def __repr__(self) -> str:
        return f"InjectionResult(detected={self.detected}, label={self.label!r})"


def detect_injection(text: str) -> InjectionResult:
    """Return whether `text` looks like a prompt-injection attempt.

    Deterministic: checks the input against the known manipulation patterns and
    reports the first that matches. A clean input returns `detected=False`. This
    is the decision the `@input_guardrail` wrapper turns into a tripwire.
    """
    if not text or not text.strip():
        return InjectionResult(detected=False)
    for pattern, label in _COMPILED:
        if pattern.search(text):
            return InjectionResult(detected=True, label=label)
    return InjectionResult(detected=False)
