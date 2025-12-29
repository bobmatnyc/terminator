"""Unit tests for session creation functionality."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from tempfile import TemporaryDirectory

from terminator.services.terminal import TerminalService
from terminator.adapters.protocols import (
    TerminalType,
    UnifiedSession,
    SessionState,
)
from terminator.config import Settings


class TestStartSession:
    """Test suite for start_session functionality."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        import os

        os.environ["TERMINATOR_OPENROUTER_API_KEY"] = "test-key"
        os.environ["TERMINATOR_AGENT_CLAUDE_CODE_CMD"] = "claude"
        os.environ["TERMINATOR_AGENT_AUGGIE_CMD"] = "augment"
        os.environ["TERMINATOR_AGENT_PYTHON_CMD"] = "python"
        os.environ["TERMINATOR_AGENT_NODE_CMD"] = "node"
        return Settings()

    @pytest.fixture
    def mock_tmux_adapter(self) -> AsyncMock:
        """Create mock tmux adapter."""
        adapter = AsyncMock()
        adapter.create_session = AsyncMock(return_value="tmux:test-project:0:0")
        adapter.list_sessions = AsyncMock(return_value=[])
        adapter.get_session_output = AsyncMock(return_value="$ ")
        return adapter

    @pytest.fixture
    def mock_iterm2_adapter(self) -> AsyncMock:
        """Create mock iTerm2 adapter."""
        adapter = AsyncMock()
        adapter.create_session = AsyncMock(return_value="iterm2:test-session-id")
        adapter.list_sessions = AsyncMock(return_value=[])
        adapter.get_session_output = AsyncMock(return_value="$ ")
        return adapter

    @pytest.fixture
    def terminal_service(
        self, mock_tmux_adapter: AsyncMock, mock_iterm2_adapter: AsyncMock
    ) -> TerminalService:
        """Create terminal service with mock adapters."""
        service = TerminalService(
            iterm2_adapter=mock_iterm2_adapter,
            tmux_adapter=mock_tmux_adapter,
        )
        # Simulate connected backends
        service._adapters = {"tmux": mock_tmux_adapter, "iterm2": mock_iterm2_adapter}
        return service

    async def test_start_session_with_claude_code(
        self, terminal_service: TerminalService, settings: Settings
    ):
        """Test starting a Claude Code session."""
        with TemporaryDirectory() as tmpdir:
            project_path = tmpdir

            # Mock get_settings to return our test settings
            with patch("terminator.config.get_settings", return_value=settings):
                address = await terminal_service.start_session(
                    project_path=project_path,
                    agent="claude-code",
                    name="test-project",
                )

                # Verify session was created with correct command
                terminal_service.tmux.create_session.assert_called_once()
                call_args = terminal_service.tmux.create_session.call_args
                assert call_args.kwargs["name"] == "test-project"
                assert call_args.kwargs["command"] == "claude"
                assert Path(call_args.kwargs["working_dir"]) == Path(project_path).resolve()

    async def test_start_session_with_auggie(
        self, terminal_service: TerminalService, settings: Settings
    ):
        """Test starting an Auggie session."""
        with TemporaryDirectory() as tmpdir:
            project_path = tmpdir

            with patch("terminator.config.get_settings", return_value=settings):
                address = await terminal_service.start_session(
                    project_path=project_path,
                    agent="auggie",
                    name="test-project",
                )

                # Verify session was created with augment command
                terminal_service.tmux.create_session.assert_called_once()
                call_args = terminal_service.tmux.create_session.call_args
                assert call_args.kwargs["command"] == "augment"

    async def test_start_session_with_shell(
        self, terminal_service: TerminalService, settings: Settings
    ):
        """Test starting a shell session (no command)."""
        with TemporaryDirectory() as tmpdir:
            project_path = tmpdir

            with patch("terminator.config.get_settings", return_value=settings):
                address = await terminal_service.start_session(
                    project_path=project_path,
                    agent="shell",
                    name="test-project",
                )

                # Verify session was created with no command
                terminal_service.tmux.create_session.assert_called_once()
                call_args = terminal_service.tmux.create_session.call_args
                assert call_args.kwargs["command"] is None

    async def test_start_session_custom_name(
        self, terminal_service: TerminalService, settings: Settings
    ):
        """Test starting session with custom name."""
        with TemporaryDirectory() as tmpdir:
            project_path = tmpdir

            with patch("terminator.config.get_settings", return_value=settings):
                address = await terminal_service.start_session(
                    project_path=project_path,
                    agent="shell",
                    name="my-custom-session",
                )

                # Verify custom name was used
                terminal_service.tmux.create_session.assert_called_once()
                call_args = terminal_service.tmux.create_session.call_args
                assert call_args.kwargs["name"] == "my-custom-session"

    async def test_start_session_default_name(
        self, terminal_service: TerminalService, settings: Settings
    ):
        """Test starting session with default name (directory name)."""
        with TemporaryDirectory() as tmpdir:
            # Create a subdirectory with known name
            project_dir = Path(tmpdir) / "my-project"
            project_dir.mkdir()

            with patch("terminator.config.get_settings", return_value=settings):
                address = await terminal_service.start_session(
                    project_path=str(project_dir),
                    agent="shell",
                )

                # Verify directory name was used
                terminal_service.tmux.create_session.assert_called_once()
                call_args = terminal_service.tmux.create_session.call_args
                assert call_args.kwargs["name"] == "my-project"

    async def test_start_session_nonexistent_directory(
        self, terminal_service: TerminalService, settings: Settings
    ):
        """Test error when directory doesn't exist."""
        with patch("terminator.config.get_settings", return_value=settings):
            with pytest.raises(RuntimeError, match="does not exist"):
                await terminal_service.start_session(
                    project_path="/nonexistent/path",
                    agent="shell",
                )

    async def test_start_session_invalid_agent(
        self, terminal_service: TerminalService, settings: Settings
    ):
        """Test error when invalid agent type is provided."""
        with TemporaryDirectory() as tmpdir:
            with patch("terminator.config.get_settings", return_value=settings):
                with pytest.raises(ValueError, match="Unknown agent type"):
                    await terminal_service.start_session(
                        project_path=tmpdir,
                        agent="invalid-agent",
                    )

    async def test_start_session_fallback_to_iterm2(
        self, terminal_service: TerminalService, settings: Settings
    ):
        """Test fallback to iTerm2 when tmux fails."""
        with TemporaryDirectory() as tmpdir:
            # Make tmux raise an error
            terminal_service.tmux.create_session.side_effect = RuntimeError("tmux failed")

            with patch("terminator.config.get_settings", return_value=settings):
                address = await terminal_service.start_session(
                    project_path=tmpdir,
                    agent="shell",
                    name="test-project",
                )

                # Verify iTerm2 was used as fallback
                terminal_service.iterm2.create_session.assert_called_once()

    async def test_start_session_no_backends_available(self, settings: Settings):
        """Test error when no backends are available."""
        # Create service with no connected adapters
        mock_tmux = AsyncMock()
        mock_iterm2 = AsyncMock()
        service = TerminalService(
            iterm2_adapter=mock_iterm2,
            tmux_adapter=mock_tmux,
        )
        # No adapters in _adapters dict (not connected)
        service._adapters = {}

        with TemporaryDirectory() as tmpdir:
            with patch("terminator.config.get_settings", return_value=settings):
                with pytest.raises(RuntimeError, match="No terminal backends available"):
                    await service.start_session(
                        project_path=tmpdir,
                        agent="shell",
                    )
