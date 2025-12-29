"""Pytest fixtures for TermPilot tests."""
import pytest
from termpilot.config import Settings
from termpilot.container import Container


@pytest.fixture
def settings() -> Settings:
    """Provide test settings."""
    # Create test settings with mock API key
    import os
    os.environ["TERMPILOT_OPENROUTER_API_KEY"] = "test-key"
    return Settings()


@pytest.fixture
def container(settings: Settings) -> Container:
    """Provide test container."""
    container = Container(settings=settings)
    yield container
    container.reset()
