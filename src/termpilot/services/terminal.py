"""Terminal service for unified session management."""

from typing import Optional

from ..adapters.protocols import (
    CommandResult,
    ITerminalAdapter,
    SessionState,
    UnifiedSession,
)
from ..adapters.iterm2 import ITerm2Adapter
from ..adapters.tmux import TmuxAdapter


class TerminalService:
    """High-level service for terminal operations.

    Manages multiple terminal adapters (iTerm2, tmux) through a unified interface.
    Provides service-level operations like listing all sessions, sending commands,
    and monitoring session status.
    """

    def __init__(self, iterm2_adapter: ITerm2Adapter, tmux_adapter: TmuxAdapter):
        """Initialize terminal service.

        Args:
            iterm2_adapter: iTerm2 adapter instance
            tmux_adapter: Tmux adapter instance
        """
        self.iterm2 = iterm2_adapter
        self.tmux = tmux_adapter
        self._adapters: dict[str, ITerminalAdapter] = {}
        self._sessions_cache: dict[str, UnifiedSession] = {}

    async def connect_all(self) -> dict[str, bool]:
        """Connect to all available terminal backends.

        Returns:
            Dict mapping backend name to connection status
        """
        status = {"tmux": False, "iterm2": False}

        # Connect to tmux
        try:
            if await self.tmux.connect():
                status["tmux"] = True
                self._adapters["tmux"] = self.tmux
        except Exception:
            pass

        # Connect to iTerm2
        try:
            if await self.iterm2.connect():
                status["iterm2"] = True
                self._adapters["iterm2"] = self.iterm2
        except Exception:
            pass

        return status

    async def list_all_sessions(self) -> list[UnifiedSession]:
        """List all sessions from all connected backends.

        Returns:
            Combined list of sessions from all backends
        """
        sessions = []

        # Get tmux sessions
        if "tmux" in self._adapters:
            tmux_sessions = await self.tmux.list_sessions()
            sessions.extend(tmux_sessions)
            for s in tmux_sessions:
                self._sessions_cache[s.id] = s

        # Get iTerm2 sessions
        if "iterm2" in self._adapters:
            iterm2_sessions = await self.iterm2.list_sessions()
            sessions.extend(iterm2_sessions)
            for s in iterm2_sessions:
                self._sessions_cache[s.id] = s

        return sessions

    async def get_session_output(self, session_id: str, lines: int = 50) -> str:
        """Get recent output from a session.

        Args:
            session_id: Target session ID
            lines: Number of lines to retrieve

        Returns:
            Recent terminal output
        """
        adapter = self._get_adapter_for_session(session_id)
        if not adapter:
            return "Session not found or backend not available"

        return await adapter.get_session_output(session_id, lines)

    async def send_command(
        self,
        session_id: str,
        command: str,
        wait_for_completion: bool = True,
        timeout: float = 30.0,
    ) -> CommandResult:
        """Send a command to a session.

        Args:
            session_id: Target session ID
            command: Command to execute
            wait_for_completion: Whether to wait for completion
            timeout: Maximum wait time

        Returns:
            Command execution result
        """
        adapter = self._get_adapter_for_session(session_id)
        if not adapter:
            return CommandResult(
                False, "Session not found or backend not available", SessionState.UNKNOWN, 0
            )

        return await adapter.send_command(
            session_id, command, wait_for_completion, timeout
        )

    async def detect_state(self, session_id: str) -> SessionState:
        """Detect whether a session is idle or running.

        Args:
            session_id: Target session ID

        Returns:
            Current session state
        """
        adapter = self._get_adapter_for_session(session_id)
        if not adapter:
            return SessionState.UNKNOWN

        return await adapter.detect_state(session_id)

    async def get_session_status(self, session_id: str) -> dict:
        """Get comprehensive status of a session with analysis.

        Args:
            session_id: Target session ID

        Returns:
            Dict with status information and screen digest
        """
        adapter = self._get_adapter_for_session(session_id)
        if not adapter:
            return {
                "is_working": False,
                "status": "unknown",
                "screen_summary": "Session not found",
                "last_lines": [],
                "indicators": {},
            }

        return await adapter.get_session_status(session_id)

    def _get_adapter_for_session(self, session_id: str) -> Optional[ITerminalAdapter]:
        """Get the appropriate adapter for a session ID.

        Args:
            session_id: Session ID (format: "backend:...")

        Returns:
            Adapter instance or None if not available
        """
        if session_id.startswith("tmux:"):
            return self._adapters.get("tmux")
        elif session_id.startswith("iterm2:"):
            return self._adapters.get("iterm2")
        return None
