"""Test container integration for conversation orchestrator."""

from terminator.container import Container
from terminator.services.conversation_orchestrator import ConversationOrchestrator


def test_get_conversation_orchestrator():
    """Test container creates conversation orchestrator correctly."""
    container = Container()
    orchestrator = container.get_conversation_orchestrator()

    assert orchestrator is not None
    assert isinstance(orchestrator, ConversationOrchestrator)
    assert orchestrator.detector is not None
    assert orchestrator.send_command is not None
    assert orchestrator.get_output is not None


def test_get_conversation_orchestrator_singleton():
    """Test conversation orchestrator is a singleton."""
    container = Container()
    orchestrator1 = container.get_conversation_orchestrator()
    orchestrator2 = container.get_conversation_orchestrator()

    assert orchestrator1 is orchestrator2


def test_orchestrator_dependencies():
    """Test orchestrator has correct dependencies injected."""
    container = Container()
    orchestrator = container.get_conversation_orchestrator()
    detector = container.get_claude_code_detector()

    # Verify detector is the same instance
    assert orchestrator.detector is detector


def test_orchestrator_reset():
    """Test orchestrator is reset with container."""
    container = Container()
    orchestrator1 = container.get_conversation_orchestrator()

    container.reset()
    orchestrator2 = container.get_conversation_orchestrator()

    # After reset, should get new instance
    assert orchestrator1 is not orchestrator2
