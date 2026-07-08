"""Central configuration for Dungeon Agents.

This is the ONLY module that reads environment variables. Every other module
imports settings from here. That keeps env access in one place: easy to change,
easy to mock in tests, and easy to reason about for guardrails later.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load variables from a local .env file if present. Real environment variables
# always win over .env, so CI and shells can override without editing files.
load_dotenv()

# A small, fast, inexpensive default. Overridable via DUNGEON_MODEL.
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of runtime configuration."""

    openai_api_key: str | None
    model: str

    @property
    def has_api_key(self) -> bool:
        """True when an API key is configured (needed to make model calls)."""
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    """Read configuration from the environment into a Settings object."""
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("DUNGEON_MODEL", DEFAULT_MODEL),
    )
