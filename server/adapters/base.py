from typing import Protocol, Optional
from enum import Enum
from dataclasses import dataclass

class TerminalState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    UNKNOWN = "unknown"

@dataclass
class SessionInfo:
    id: str
    name: str
    working_dir: Optional[str]
    state: TerminalState

class ITerminalAdapter(Protocol):
    """Protocol for terminal adapters (iTerm2, tmux)."""

    # Session lifecycle
    async def create_session(
        self,
        name: str,
        working_dir: str = None
    ) -> SessionInfo: ...

    async def destroy_session(self, session_id: str) -> bool: ...

    async def list_sessions(self) -> list[SessionInfo]: ...

    # I/O operations
    async def send_text(
        self,
        session_id: str,
        text: str,
        press_enter: bool = True
    ) -> bool: ...

    async def send_keys(
        self,
        session_id: str,
        keys: str
    ) -> bool: ...

    async def get_output(
        self,
        session_id: str,
        lines: int = 100
    ) -> str: ...

    # State detection
    async def detect_state(
        self,
        session_id: str
    ) -> TerminalState: ...
