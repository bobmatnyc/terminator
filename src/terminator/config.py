"""Configuration management using pydantic-settings."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings.

    Loads configuration from environment variables with TERMINATOR_ prefix.
    For backwards compatibility, also supports TERMPILOT_ prefix as fallback.
    Also loads from .env.local and .env files.
    """

    model_config = SettingsConfigDict(
        env_prefix="TERMINATOR_",
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenRouter configuration
    openrouter_api_key: str = Field(default="")
    openrouter_model: str = "anthropic/claude-sonnet-4"

    # LLM configuration
    llm_temperature: float = 0.7

    # Agent launch commands
    agent_claude_code_cmd: str = "claude"
    agent_auggie_cmd: str = "augment"
    agent_python_cmd: str = "python"
    agent_node_cmd: str = "node"

    @field_validator("openrouter_api_key", mode="before")
    @classmethod
    def fallback_to_termpilot_prefix(cls, v: str | None) -> str:
        """Support TERMPILOT_ prefix for backwards compatibility.

        Checks for TERMINATOR_ first, then falls back to TERMPILOT_.
        This allows users to migrate gradually from old env vars.
        """
        if v:
            return v

        # Try TERMPILOT_ prefix as fallback
        legacy_key = os.getenv("TERMPILOT_OPENROUTER_API_KEY", "")
        if legacy_key:
            return legacy_key

        return ""


def get_settings() -> Settings:
    """Get application settings singleton.

    Returns:
        Settings instance

    Raises:
        ValidationError: If required environment variables are missing
    """
    return Settings()
