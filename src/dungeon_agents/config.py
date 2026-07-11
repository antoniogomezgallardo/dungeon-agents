"""Central configuration for Dungeon Agents.

This is the ONLY module that reads environment variables. Every other module
imports settings from here. That keeps env access in one place: easy to change,
easy to mock in tests, and easy to reason about for guardrails later.

Provider selection (Milestone 1.5): the game can run on either Anthropic (Claude)
or OpenAI. `DUNGEON_PROVIDER` picks which. The agent runtime is the OpenAI Agents
SDK in both cases; for Anthropic it routes through the SDK's LiteLLM adapter. This
keeps the game logic identical while the model vendor underneath is swappable —
the same abstraction we'll want in TestOps AI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load variables from a local .env file if present. Real environment variables
# always win over .env, so CI and shells can override without editing files.
load_dotenv()

# Provider identifiers.
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENAI = "openai"

DEFAULT_PROVIDER = PROVIDER_ANTHROPIC

# Per-provider default models. Both are the cheapest current-generation option
# for their vendor — plenty for short console turns.
#   claude-haiku-4-5 : $1.00/$5.00 per 1M tokens (input/output), 200K context.
#   gpt-4o-mini      : OpenAI's small, fast, inexpensive model.
DEFAULT_MODELS = {
    PROVIDER_ANTHROPIC: "claude-haiku-4-5",
    PROVIDER_OPENAI: "gpt-4o-mini",
}

# Which environment variable holds each provider's API key.
API_KEY_ENV = {
    PROVIDER_ANTHROPIC: "ANTHROPIC_API_KEY",
    PROVIDER_OPENAI: "OPENAI_API_KEY",
}


# Values that count as "on" for a boolean env var (case-insensitive).
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of runtime configuration."""

    provider: str
    api_key: str | None
    model: str
    debug: bool

    @property
    def has_api_key(self) -> bool:
        """True when an API key is configured (needed to make model calls)."""
        return bool(self.api_key)

    @property
    def api_key_env_name(self) -> str:
        """The env var the user must set for the selected provider."""
        return API_KEY_ENV[self.provider]


def load_settings() -> Settings:
    """Read configuration from the environment into a Settings object.

    `DUNGEON_PROVIDER` selects the vendor (default: anthropic). An unknown value
    falls back to the default rather than crashing — a safe, predictable default.
    `DUNGEON_MODEL` overrides the per-provider default model if set.
    `DUNGEON_DEBUG` (1/true/yes/on) starts the game in debug mode, which surfaces
    what the agent does under the hood (tool calls, timing). Off by default.
    """
    provider = os.getenv("DUNGEON_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider not in DEFAULT_MODELS:
        provider = DEFAULT_PROVIDER

    model = os.getenv("DUNGEON_MODEL") or DEFAULT_MODELS[provider]
    debug = os.getenv("DUNGEON_DEBUG", "").strip().lower() in _TRUTHY

    return Settings(
        provider=provider,
        api_key=os.getenv(API_KEY_ENV[provider]),
        model=model,
        debug=debug,
    )
