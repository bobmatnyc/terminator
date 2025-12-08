"""Session manager for coordinating terminal sessions."""
from typing import Optional
from server.adapters.tmux import TmuxAdapter
from server.adapters.iterm2 import ITerm2Adapter
from server.adapters.base import SessionInfo

class SessionManager:
    """Manages terminal sessions across adapters."""

    def __init__(
        self,
        tmux_adapter: TmuxAdapter,
        iterm2_adapter: ITerm2Adapter,
    ):
        self.tmux_adapter = tmux_adapter
        self.iterm2_adapter = iterm2_adapter

    async def create_session(
        self,
        name: str,
        adapter: str = "tmux",
        working_dir: Optional[str] = None
    ) -> SessionInfo:
        """Create a new terminal session using the specified adapter."""
        raise NotImplementedError("SessionManager.create_session not yet implemented")

    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session info by ID."""
        raise NotImplementedError("SessionManager.get_session not yet implemented")
