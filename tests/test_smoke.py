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
from dungeon_agents.config import (
    DEFAULT_MODELS,
    DEFAULT_PROVIDER,
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    Settings,
    load_settings,
)


def test_package_imports() -> None:
    """The top-level package imports and exposes a version."""
    pkg = importlib.import_module("dungeon_agents")
    assert pkg.__version__


def test_default_provider_and_model(monkeypatch) -> None:
    """With nothing set, we default to Anthropic + its cheapest model."""
    monkeypatch.delenv("DUNGEON_PROVIDER", raising=False)
    monkeypatch.delenv("DUNGEON_MODEL", raising=False)
    settings = load_settings()
    assert settings.provider == DEFAULT_PROVIDER == PROVIDER_ANTHROPIC
    assert settings.model == DEFAULT_MODELS[PROVIDER_ANTHROPIC] == "claude-haiku-4-5"


def test_openai_provider_selects_openai_key_and_model(monkeypatch) -> None:
    """Selecting the OpenAI provider reads OPENAI_API_KEY and its default model."""
    monkeypatch.setenv("DUNGEON_PROVIDER", "openai")
    monkeypatch.delenv("DUNGEON_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    settings = load_settings()
    assert settings.provider == PROVIDER_OPENAI
    assert settings.model == DEFAULT_MODELS[PROVIDER_OPENAI]
    assert settings.api_key == "sk-openai"
    assert settings.api_key_env_name == "OPENAI_API_KEY"


def test_unknown_provider_falls_back_to_default(monkeypatch) -> None:
    """An unrecognized provider value falls back safely, not a crash."""
    monkeypatch.setenv("DUNGEON_PROVIDER", "banana")
    assert load_settings().provider == DEFAULT_PROVIDER


def test_settings_respects_model_override(monkeypatch) -> None:
    """DUNGEON_MODEL overrides the per-provider default."""
    monkeypatch.setenv("DUNGEON_PROVIDER", "anthropic")
    monkeypatch.setenv("DUNGEON_MODEL", "claude-sonnet-4-6")
    assert load_settings().model == "claude-sonnet-4-6"


def test_has_api_key_flag() -> None:
    """has_api_key reflects whether a key is present."""
    base = dict(provider=PROVIDER_ANTHROPIC, model="claude-haiku-4-5", debug=False)
    assert Settings(api_key=None, **base).has_api_key is False
    assert Settings(api_key="sk-x", **base).has_api_key is True


def test_debug_flag_off_by_default(monkeypatch) -> None:
    """Debug mode is off unless DUNGEON_DEBUG is set to a truthy value."""
    monkeypatch.delenv("DUNGEON_DEBUG", raising=False)
    assert load_settings().debug is False


def test_debug_flag_reads_truthy_env(monkeypatch) -> None:
    """DUNGEON_DEBUG=1 (or true/yes/on) turns debug mode on."""
    monkeypatch.setenv("DUNGEON_DEBUG", "1")
    assert load_settings().debug is True
    monkeypatch.setenv("DUNGEON_DEBUG", "off")
    assert load_settings().debug is False


def test_game_master_contract_mentions_choices() -> None:
    """The GM instructions encode the 2-3 choices contract."""
    text = GAME_MASTER_INSTRUCTIONS.lower()
    assert "2 or 3" in text
    assert "concise" in text


def test_game_master_stays_in_character() -> None:
    """The GM is instructed never to reveal it is an AI."""
    assert "never break character" in GAME_MASTER_INSTRUCTIONS.lower()
