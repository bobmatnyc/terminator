"""tmux terminal adapter implementation."""
from typing import Optional
from server.adapters.base import ITerminalAdapter, SessionInfo, TerminalState

class TmuxAdapter:
    """tmux adapter using libtmux.

    Provides terminal control operations via tmux sessions.
    """

    async def create_session(
        self,
        name: str,
        working_dir: Optional[str] = None
    ) -> SessionInfo:
        """Create a new tmux session."""
        raise NotImplementedError("TmuxAdapter.create_session not yet implemented")

    async def destroy_session(self, session_id: str) -> bool:
        """Destroy a tmux session."""
        raise NotImplementedError("TmuxAdapter.destroy_session not yet implemented")

    async def list_sessions(self) -> list[SessionInfo]:
        """List all tmux sessions."""
        raise NotImplementedError("TmuxAdapter.list_sessions not yet implemented")

    async def send_text(
        self,
        session_id: str,
        text: str,
        press_enter: bool = True
    ) -> bool:
        """Send text to a tmux session."""
        raise NotImplementedError("TmuxAdapter.send_text not yet implemented")

    async def send_keys(
        self,
        session_id: str,
        keys: str
    ) -> bool:
        """Send special keys to a tmux session."""
        raise NotImplementedError("TmuxAdapter.send_keys not yet implemented")

    async def get_output(
        self,
        session_id: str,
        lines: int = 100
    ) -> str:
        """Get output from a tmux session."""
        raise NotImplementedError("TmuxAdapter.get_output not yet implemented")

    async def detect_state(
        self,
        session_id: str
    ) -> TerminalState:
        """Detect the state of a tmux session."""
        raise NotImplementedError("TmuxAdapter.detect_state not yet implemented")
