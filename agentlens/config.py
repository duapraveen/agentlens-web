"""Typed application settings loaded from environment variables (and .env)."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Conventions: costs are USD cents, durations are ms, scores are 0-100.
    App fields read the ``AGENTLENS_`` env prefix; the API key reads the
    standard ``ANTHROPIC_API_KEY`` so the anthropic SDK convention holds.
    """

    model_config = SettingsConfigDict(env_prefix="AGENTLENS_", env_file=".env", extra="ignore")

    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    database_url: str = "sqlite:///data/agentlens.db"
    golden_dir: Path = Path("data/golden")
    jobs_log_path: Path = Path("logs/jobs.log")
    generator_model: str = "claude-sonnet-5"
    judge_model: str = "claude-haiku-4-5"


def get_settings() -> Settings:
    """Load settings fresh from the environment. Cheap; call at use sites, don't cache."""
    return Settings()
