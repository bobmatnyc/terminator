"""FastAPI dependency injection integration."""
from functools import lru_cache
from server.config import Settings

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
