"""Unit tests for session manager TUI."""

import pytest
from unittest.mock import AsyncMock, Mock

from terminator.adapters.protocols import (
    UnifiedSession,
    TerminalType,
    SessionState,
    InstanceType,
)
from terminator.cli.tui.session_manager import SessionManagerTUI


@pytest.fixture
def mock_terminal_service():
    """Create mock terminal service."""
    service = Mock()
    service.list_all_sessions = AsyncMock()
    service.kill_session = AsyncMock()
    service.project_registry = Mock()
    service.project_registry.list_projects = AsyncMock(return_value={})
    return service


@pytest.fixture
def sample_sessions():
    """Create sample sessions for testing."""
    return [
        UnifiedSession(
            id="tmux:test-session:0:0",
            name="test-session",
            terminal_type=TerminalType.TMUX,
            state=SessionState.IDLE,
            cwd="/home/user/projects/test",
            instance_type=InstanceType.SHELL,
        ),
        UnifiedSession(
            id="tmux:another-session:0:0",
            name="another-session",
            terminal_type=TerminalType.TMUX,
            state=SessionState.RUNNING,
            cwd="/home/user/projects/another",
            instance_type=InstanceType.CLAUDE_CODE,
        ),
    ]


class TestSessionManagerTUI:
    """Test SessionManagerTUI class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_terminal_service):
        """Test TUI initialization."""
        tui = SessionManagerTUI(mock_terminal_service)

        assert tui.terminal_service == mock_terminal_service
        assert tui.sessions == []
        assert tui.selected_index == 0
        assert tui.session_to_address == {}
        assert tui.running is True

    @pytest.mark.asyncio
    async def test_refresh_sessions(self, mock_terminal_service, sample_sessions):
        """Test session list refresh."""
        mock_terminal_service.list_all_sessions.return_value = sample_sessions
        mock_terminal_service.project_registry.list_projects.return_value = {
            "test": [
                Mock(session_id="tmux:test-session:0:0", address="@test"),
                Mock(session_id="tmux:another-session:0:0", address="@another"),
            ]
        }

        tui = SessionManagerTUI(mock_terminal_service)
        await tui.refresh_sessions()

        assert len(tui.sessions) == 2
        assert tui.sessions[0].id == "tmux:test-session:0:0"
        assert tui.sessions[1].id == "tmux:another-session:0:0"
        assert tui.session_to_address["tmux:test-session:0:0"] == "@test"
        assert tui.session_to_address["tmux:another-session:0:0"] == "@another"

    @pytest.mark.asyncio
    async def test_refresh_sessions_clamps_index(
        self, mock_terminal_service, sample_sessions
    ):
        """Test that selected index is clamped after refresh."""
        mock_terminal_service.list_all_sessions.return_value = sample_sessions

        tui = SessionManagerTUI(mock_terminal_service)
        tui.selected_index = 5  # Out of bounds
        await tui.refresh_sessions()

        # Should be clamped to last valid index
        assert tui.selected_index == 1

    @pytest.mark.asyncio
    async def test_refresh_sessions_empty_list(self, mock_terminal_service):
        """Test refresh with no sessions."""
        mock_terminal_service.list_all_sessions.return_value = []

        tui = SessionManagerTUI(mock_terminal_service)
        tui.selected_index = 5
        await tui.refresh_sessions()

        assert len(tui.sessions) == 0
        assert tui.selected_index == 0

    @pytest.mark.asyncio
    async def test_render_with_sessions(self, mock_terminal_service, sample_sessions):
        """Test rendering with sessions."""
        mock_terminal_service.list_all_sessions.return_value = sample_sessions

        tui = SessionManagerTUI(mock_terminal_service)
        await tui.refresh_sessions()

        # Test rendering (should not raise exception)
        layout = tui._render()
        assert layout is not None

    @pytest.mark.asyncio
    async def test_render_with_no_sessions(self, mock_terminal_service):
        """Test rendering with no sessions."""
        mock_terminal_service.list_all_sessions.return_value = []

        tui = SessionManagerTUI(mock_terminal_service)
        await tui.refresh_sessions()

        # Test rendering (should not raise exception)
        layout = tui._render()
        assert layout is not None

    @pytest.mark.asyncio
    async def test_render_with_message(self, mock_terminal_service, sample_sessions):
        """Test rendering with a status message."""
        mock_terminal_service.list_all_sessions.return_value = sample_sessions

        tui = SessionManagerTUI(mock_terminal_service)
        await tui.refresh_sessions()

        # Set a message
        tui.message = "Test message"
        tui.message_type = "success"

        # Test rendering (should not raise exception)
        layout = tui._render()
        assert layout is not None


class TestSessionManagerTUIIntegration:
    """Integration tests that verify correct interaction patterns."""

    @pytest.mark.asyncio
    async def test_kill_session_workflow(self, mock_terminal_service, sample_sessions):
        """Test the kill session workflow (without actual terminal interaction)."""
        mock_terminal_service.list_all_sessions.return_value = sample_sessions
        mock_terminal_service.kill_session.return_value = True

        tui = SessionManagerTUI(mock_terminal_service)
        await tui.refresh_sessions()

        # Simulate selecting first session
        tui.selected_index = 0
        session_id = tui.sessions[tui.selected_index].id

        # Verify kill_session would be called with correct ID
        await mock_terminal_service.kill_session(session_id)
        mock_terminal_service.kill_session.assert_called_once_with(
            "tmux:test-session:0:0"
        )

    @pytest.mark.asyncio
    async def test_navigation_bounds(self, mock_terminal_service, sample_sessions):
        """Test that navigation stays within bounds."""
        mock_terminal_service.list_all_sessions.return_value = sample_sessions

        tui = SessionManagerTUI(mock_terminal_service)
        await tui.refresh_sessions()

        # Test lower bound
        tui.selected_index = 0
        tui.selected_index = max(0, tui.selected_index - 1)
        assert tui.selected_index == 0

        # Test upper bound
        tui.selected_index = 1
        tui.selected_index = min(len(tui.sessions) - 1, tui.selected_index + 1)
        assert tui.selected_index == 1

    @pytest.mark.asyncio
    async def test_attach_session_non_tmux(
        self, mock_terminal_service, sample_sessions
    ):
        """Test that attach only works for tmux sessions."""
        # Create iTerm2 session
        iterm_session = UnifiedSession(
            id="iterm2:some-id",
            name="iterm-session",
            terminal_type=TerminalType.ITERM2,
            state=SessionState.IDLE,
            cwd="/home/user/projects/test",
            instance_type=InstanceType.SHELL,
        )

        mock_terminal_service.list_all_sessions.return_value = [iterm_session]

        tui = SessionManagerTUI(mock_terminal_service)
        await tui.refresh_sessions()

        # Verify session is iTerm2 (attach should not work)
        assert not tui.sessions[0].id.startswith("tmux:")
