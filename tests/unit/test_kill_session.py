"""Unit tests for kill_session functionality."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from terminator.adapters.tmux import TmuxAdapter
from terminator.adapters.iterm2 import ITerm2Adapter
from terminator.services.terminal import TerminalService


class TestTmuxAdapterKillSession:
    """Test TmuxAdapter.kill_session method."""

    @pytest.mark.asyncio
    async def test_kill_session_success(self):
        """Test successful session kill."""
        adapter = TmuxAdapter()
        adapter._server = Mock()

        # Mock session
        mock_session = Mock()
        mock_session.kill_session = Mock()

        # Mock server.sessions.get
        adapter._server.sessions.get = Mock(return_value=mock_session)

        # Add to cache
        session_id = "tmux:test-session:0:0"
        adapter._sessions_cache[session_id] = Mock()

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            # First call returns session, second call kills it
            mock_to_thread.side_effect = [mock_session, None]

            result = await adapter.kill_session(session_id)

            assert result is True
            assert session_id not in adapter._sessions_cache

    @pytest.mark.asyncio
    async def test_kill_session_not_connected(self):
        """Test kill when not connected to tmux."""
        adapter = TmuxAdapter()
        adapter._server = None

        result = await adapter.kill_session("tmux:test:0:0")

        assert result is False

    @pytest.mark.asyncio
    async def test_kill_session_invalid_id(self):
        """Test kill with invalid session ID."""
        adapter = TmuxAdapter()
        adapter._server = Mock()

        result = await adapter.kill_session("invalid-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_kill_session_not_found(self):
        """Test kill when session doesn't exist."""
        adapter = TmuxAdapter()
        adapter._server = Mock()

        # Mock server.sessions.get returns None (session not found)
        adapter._server.sessions.get = Mock(return_value=None)

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = None

            result = await adapter.kill_session("tmux:nonexistent:0:0")

            assert result is False

    @pytest.mark.asyncio
    async def test_kill_session_exception(self):
        """Test kill when exception occurs."""
        adapter = TmuxAdapter()
        adapter._server = Mock()

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = Exception("Kill failed")

            result = await adapter.kill_session("tmux:test:0:0")

            assert result is False


class TestITerm2AdapterKillSession:
    """Test ITerm2Adapter.kill_session method."""

    @pytest.mark.asyncio
    async def test_kill_session_success(self):
        """Test successful session kill."""
        adapter = ITerm2Adapter()

        # Mock app with windows, tabs, and sessions
        mock_session = Mock()
        mock_session.session_id = "test-session-id"
        mock_session.async_close = AsyncMock()

        mock_tab = Mock()
        mock_tab.sessions = [mock_session]

        mock_window = Mock()
        mock_window.tabs = [mock_tab]

        mock_app = Mock()
        mock_app.windows = [mock_window]

        adapter._app = mock_app

        # Add to cache
        session_id = "iterm2:test-session-id"
        adapter._sessions_cache[session_id] = Mock()

        result = await adapter.kill_session(session_id)

        assert result is True
        assert session_id not in adapter._sessions_cache
        mock_session.async_close.assert_called_once_with(force=True)

    @pytest.mark.asyncio
    async def test_kill_session_not_connected(self):
        """Test kill when not connected to iTerm2."""
        adapter = ITerm2Adapter()
        adapter._app = None

        result = await adapter.kill_session("iterm2:test-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_kill_session_invalid_id(self):
        """Test kill with invalid session ID."""
        adapter = ITerm2Adapter()
        adapter._app = Mock()

        result = await adapter.kill_session("invalid-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_kill_session_not_found(self):
        """Test kill when session doesn't exist."""
        adapter = ITerm2Adapter()

        # Mock app with no matching session
        mock_session = Mock()
        mock_session.session_id = "different-id"

        mock_tab = Mock()
        mock_tab.sessions = [mock_session]

        mock_window = Mock()
        mock_window.tabs = [mock_tab]

        mock_app = Mock()
        mock_app.windows = [mock_window]

        adapter._app = mock_app

        result = await adapter.kill_session("iterm2:nonexistent-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_kill_session_exception(self):
        """Test kill when exception occurs."""
        adapter = ITerm2Adapter()

        # Mock app that raises exception
        mock_app = Mock()
        mock_app.windows = Mock(side_effect=Exception("iTerm2 error"))

        adapter._app = mock_app

        result = await adapter.kill_session("iterm2:test-id")

        assert result is False


class TestTerminalServiceKillSession:
    """Test TerminalService.kill_session method."""

    @pytest.mark.asyncio
    async def test_kill_session_success(self):
        """Test successful session kill via service."""
        # Mock adapters
        mock_tmux = Mock()
        mock_tmux.kill_session = AsyncMock(return_value=True)

        mock_iterm2 = Mock()

        service = TerminalService(mock_iterm2, mock_tmux)
        service._adapters["tmux"] = mock_tmux

        # Add to cache
        session_id = "tmux:test:0:0"
        service._sessions_cache[session_id] = Mock()

        result = await service.kill_session(session_id)

        assert result is True
        assert session_id not in service._sessions_cache
        mock_tmux.kill_session.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_kill_session_with_project_address(self):
        """Test kill session using @project address."""
        # Mock adapters
        mock_tmux = Mock()
        mock_tmux.kill_session = AsyncMock(return_value=True)

        mock_iterm2 = Mock()

        service = TerminalService(mock_iterm2, mock_tmux)
        service._adapters["tmux"] = mock_tmux

        # Mock project registry
        mock_registry = Mock()
        mock_registry.resolve = AsyncMock(return_value="tmux:test:0:0")
        service.project_registry = mock_registry

        result = await service.kill_session("@test")

        assert result is True
        mock_registry.resolve.assert_called_once_with("@test")
        mock_tmux.kill_session.assert_called_once_with("tmux:test:0:0")

    @pytest.mark.asyncio
    async def test_kill_session_not_found(self):
        """Test kill when session not found."""
        service = TerminalService(Mock(), Mock())

        # Mock project registry that can't resolve
        mock_registry = Mock()
        mock_registry.resolve = AsyncMock(return_value=None)
        service.project_registry = mock_registry

        result = await service.kill_session("@nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_kill_session_no_adapter(self):
        """Test kill when no adapter available for session."""
        service = TerminalService(Mock(), Mock())
        service._adapters = {}

        result = await service.kill_session("tmux:test:0:0")

        assert result is False
