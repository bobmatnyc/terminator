from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Server
    host: str = "127.0.0.1"
    port: int = 7777

    # Adapters
    default_adapter: str = "tmux"  # or "iterm2"

    # LLM
    openrouter_api_key: Optional[str] = None
    local_llm_enabled: bool = True
    local_llm_model: str = "qwen2.5-coder:1.5b"

    # Security
    auth_token: Optional[str] = None

    model_config = {
        "env_file": ".env",
        "env_prefix": "TERMPILOT_",
    }
