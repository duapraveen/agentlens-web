"""Tests for typed settings."""

from pathlib import Path

import pytest

from agentlens.config import Settings, get_settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.database_url == "sqlite:///data/agentlens.db"
    assert settings.golden_dir == Path("data/golden")
    assert settings.jobs_log_path == Path("logs/jobs.log")
    assert settings.generator_model == "claude-sonnet-5"
    assert settings.judge_model == "claude-haiku-4-5"
    assert settings.anthropic_api_key == ""


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTLENS_DATABASE_URL", "sqlite:///tmp/other.db")
    monkeypatch.setenv("AGENTLENS_JUDGE_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    settings = get_settings()
    assert settings.database_url == "sqlite:///tmp/other.db"
    assert settings.judge_model == "claude-sonnet-5"
    assert settings.anthropic_api_key == "sk-test"
