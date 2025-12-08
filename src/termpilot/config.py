"""Configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Loads configuration from environment variables with TERMPILOT_ prefix.
    Also loads from .env.local and .env files.
    """

    model_config = SettingsConfigDict(
        env_prefix="TERMPILOT_",
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenRouter configuration
    openrouter_api_key: str
    openrouter_model: str = "anthropic/claude-sonnet-4"

    # LLM configuration
    llm_temperature: float = 0.7


def get_settings() -> Settings:
    """Get application settings singleton.

    Returns:
        Settings instance

    Raises:
        ValidationError: If required environment variables are missing
    """
    return Settings()
