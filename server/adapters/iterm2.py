"""iTerm2 terminal adapter implementation."""
from typing import Optional
from server.adapters.base import ITerminalAdapter, SessionInfo, TerminalState

class ITerm2Adapter:
    """iTerm2 adapter using iterm2 Python API.

    Provides terminal control operations via iTerm2 scripting API.
    """

    async def create_session(
        self,
        name: str,
        working_dir: Optional[str] = None
    ) -> SessionInfo:
        """Create a new iTerm2 session."""
        raise NotImplementedError("ITerm2Adapter.create_session not yet implemented")

    async def destroy_session(self, session_id: str) -> bool:
        """Destroy an iTerm2 session."""
        raise NotImplementedError("ITerm2Adapter.destroy_session not yet implemented")

    async def list_sessions(self) -> list[SessionInfo]:
        """List all iTerm2 sessions."""
        raise NotImplementedError("ITerm2Adapter.list_sessions not yet implemented")

    async def send_text(
        self,
        session_id: str,
        text: str,
        press_enter: bool = True
    ) -> bool:
        """Send text to an iTerm2 session."""
        raise NotImplementedError("ITerm2Adapter.send_text not yet implemented")

    async def send_keys(
        self,
        session_id: str,
        keys: str
    ) -> bool:
        """Send special keys to an iTerm2 session."""
        raise NotImplementedError("ITerm2Adapter.send_keys not yet implemented")

    async def get_output(
        self,
        session_id: str,
        lines: int = 100
    ) -> str:
        """Get output from an iTerm2 session."""
        raise NotImplementedError("ITerm2Adapter.get_output not yet implemented")

    async def detect_state(
        self,
        session_id: str
    ) -> TerminalState:
        """Detect the state of an iTerm2 session."""
        raise NotImplementedError("ITerm2Adapter.detect_state not yet implemented")
