"""Smoke tests for Milestone 1.

These run WITHOUT an OpenAI API key and WITHOUT the SDK installed. They verify:
- the package imports;
- configuration loads and defaults correctly;
- the Game Master's behavioral contract is encoded in its instructions.

They do NOT make a real model call. A live end-to-end test would be marked
`@pytest.mark.llm` and live separately (Milestone 7).
"""

from __future__ import annotations

import importlib

from dungeon_agents.agents.game_master import GAME_MASTER_INSTRUCTIONS
from dungeon_agents.config import DEFAULT_MODEL, Settings, load_settings


def test_package_imports() -> None:
    """The top-level package imports and exposes a version."""
    pkg = importlib.import_module("dungeon_agents")
    assert pkg.__version__


def test_settings_default_model(monkeypatch) -> None:
    """With no DUNGEON_MODEL set, we fall back to the default model."""
    monkeypatch.delenv("DUNGEON_MODEL", raising=False)
    settings = load_settings()
    assert settings.model == DEFAULT_MODEL


def test_settings_respects_model_override(monkeypatch) -> None:
    """DUNGEON_MODEL overrides the default."""
    monkeypatch.setenv("DUNGEON_MODEL", "gpt-4o")
    assert load_settings().model == "gpt-4o"


def test_has_api_key_flag() -> None:
    """has_api_key reflects whether a key is present."""
    assert Settings(openai_api_key=None, model=DEFAULT_MODEL).has_api_key is False
    assert Settings(openai_api_key="sk-x", model=DEFAULT_MODEL).has_api_key is True


def test_game_master_contract_mentions_choices() -> None:
    """The GM instructions encode the 2-3 choices contract."""
    text = GAME_MASTER_INSTRUCTIONS.lower()
    assert "2 or 3" in text
    assert "concise" in text


def test_game_master_stays_in_character() -> None:
    """The GM is instructed never to reveal it is an AI."""
    assert "never break character" in GAME_MASTER_INSTRUCTIONS.lower()
