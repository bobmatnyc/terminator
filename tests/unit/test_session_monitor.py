"""Tests for session monitor service."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from terminator.services.session_monitor import SessionMonitorService
from terminator.services.events import EventType, SessionEvent


@pytest.fixture
def mock_terminal_service():
    """Create a mock terminal service."""
    service = Mock()
    service.get_session_status = AsyncMock(
        return_value={
            "status": "idle",
            "indicators": {
                "waiting_for_input": False,
                "has_prompt": True,
                "has_spinner": False,
                "has_progress": False,
            },
            "last_lines": ["$ "],
            "screen_summary": "At shell prompt",
        }
    )
    return service


class TestSessionMonitorService:
    """Tests for SessionMonitorService."""

    @pytest.mark.asyncio
    async def test_start_monitoring(self, mock_terminal_service):
        """Test starting monitoring for a session."""
        monitor = SessionMonitorService(mock_terminal_service, poll_interval=0.1)

        result = await monitor.start_monitoring("tmux:test:0:0", "@test")

        assert result is True
        assert monitor.is_monitoring("tmux:test:0:0")
        assert "tmux:test:0:0" in monitor.get_monitored_sessions()

        await monitor.shutdown()

    @pytest.mark.asyncio
    async def test_start_monitoring_already_monitoring(self, mock_terminal_service):
        """Test that starting monitoring twice returns False."""
        monitor = SessionMonitorService(mock_terminal_service, poll_interval=0.1)

        await monitor.start_monitoring("tmux:test:0:0", "@test")
        result = await monitor.start_monitoring("tmux:test:0:0", "@test")

        assert result is False

        await monitor.shutdown()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, mock_terminal_service):
        """Test stopping monitoring."""
        monitor = SessionMonitorService(mock_terminal_service, poll_interval=0.1)
        await monitor.start_monitoring("tmux:test:0:0", "@test")

        result = await monitor.stop_monitoring("tmux:test:0:0")

        assert result is True
        assert not monitor.is_monitoring("tmux:test:0:0")

        await monitor.shutdown()

    @pytest.mark.asyncio
    async def test_stop_monitoring_not_monitored(self, mock_terminal_service):
        """Test that stopping non-monitored session returns False."""
        monitor = SessionMonitorService(mock_terminal_service, poll_interval=0.1)

        result = await monitor.stop_monitoring("tmux:test:0:0")

        assert result is False

        await monitor.shutdown()

    @pytest.mark.asyncio
    async def test_get_events_empty(self, mock_terminal_service):
        """Test getting events when none exist."""
        monitor = SessionMonitorService(mock_terminal_service, poll_interval=0.1)

        events = await monitor.get_events()

        assert events == []

        await monitor.shutdown()

    @pytest.mark.asyncio
    async def test_event_detection_input_required(self, mock_terminal_service):
        """Test INPUT_REQUIRED event detection."""
        # Start with no waiting_for_input
        mock_terminal_service.get_session_status = AsyncMock(
            return_value={
                "status": "idle",
                "indicators": {"waiting_for_input": False, "has_prompt": True},
                "last_lines": ["$ "],
            }
        )

        monitor = SessionMonitorService(mock_terminal_service, poll_interval=0.05)
        await monitor.start_monitoring("tmux:test:0:0", "@test")

        # First poll establishes baseline
        await asyncio.sleep(0.1)

        # Change to waiting_for_input
        mock_terminal_service.get_session_status.return_value = {
            "status": "waiting_for_input",
            "indicators": {"waiting_for_input": True, "has_prompt": False},
            "last_lines": ["Password: "],
        }

        # Wait for poll
        await asyncio.sleep(0.1)

        events = await monitor.get_events()

        input_events = [e for e in events if e.event_type == EventType.INPUT_REQUIRED]
        assert len(input_events) >= 1
        assert input_events[0].session_address == "@test"

        await monitor.shutdown()

    @pytest.mark.asyncio
    async def test_event_detection_output_ready(self, mock_terminal_service):
        """Test OUTPUT_READY event detection."""
        # Start with working state
        mock_terminal_service.get_session_status = AsyncMock(
            return_value={
                "status": "working",
                "indicators": {"has_prompt": False, "waiting_for_input": False},
            }
        )

        monitor = SessionMonitorService(mock_terminal_service, poll_interval=0.05)
        await monitor.start_monitoring("tmux:test:0:0", "@test")

        # First poll establishes baseline
        await asyncio.sleep(0.1)

        # Transition to idle with prompt
        mock_terminal_service.get_session_status.return_value = {
            "status": "idle",
            "indicators": {"has_prompt": True, "waiting_for_input": False},
            "screen_summary": "Command completed",
        }

        # Wait for poll
        await asyncio.sleep(0.1)

        events = await monitor.get_events()

        output_events = [e for e in events if e.event_type == EventType.OUTPUT_READY]
        assert len(output_events) >= 1
        assert output_events[0].message == "Command completed"

        await monitor.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_all_tasks(self, mock_terminal_service):
        """Test that shutdown cancels all monitoring tasks."""
        monitor = SessionMonitorService(mock_terminal_service, poll_interval=0.1)

        await monitor.start_monitoring("session1", "@proj1")
        await monitor.start_monitoring("session2", "@proj2")

        assert len(monitor.get_monitored_sessions()) == 2

        await monitor.shutdown()

        assert len(monitor.get_monitored_sessions()) == 0

    @pytest.mark.asyncio
    async def test_multiple_sessions_monitored(self, mock_terminal_service):
        """Test monitoring multiple sessions simultaneously."""
        monitor = SessionMonitorService(mock_terminal_service, poll_interval=0.1)

        await monitor.start_monitoring("session1", "@proj1")
        await monitor.start_monitoring("session2", "@proj2")
        await monitor.start_monitoring("session3", "@proj3")

        sessions = monitor.get_monitored_sessions()

        assert len(sessions) == 3
        assert "session1" in sessions
        assert "session2" in sessions
        assert "session3" in sessions

        await monitor.shutdown()


class TestSessionEvent:
    """Tests for SessionEvent dataclass."""

    def test_event_str_format(self):
        """Test event string representation."""
        event = SessionEvent(
            event_type=EventType.INPUT_REQUIRED,
            session_id="tmux:test:0:0",
            session_address="@test",
            timestamp=datetime(2024, 1, 15, 14, 30, 45),
            message="Waiting for input",
        )

        result = str(event)

        assert "14:30:45" in result
        assert "@test" in result
        assert "input_required" in result
        assert "Waiting for input" in result
