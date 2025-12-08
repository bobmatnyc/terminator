"""Pytest fixtures for TermPilot tests."""
import pytest
from server.config import Settings
from server.container import Container

@pytest.fixture
def settings():
    """Provide test settings."""
    return Settings()

@pytest.fixture
def container():
    """Provide test container."""
    container = Container()
    container.init_resources()
    yield container
