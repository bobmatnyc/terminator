"""Protocol definitions for terminal adapters."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class TerminalType(Enum):
    """Terminal backend type."""

    ITERM2 = "iterm2"
    TMUX = "tmux"


class SessionState(Enum):
    """Terminal session state."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    UNKNOWN = "unknown"


class InstanceType(str, Enum):
    """Type of REPL or shell running in a session."""

    CLAUDE_CODE = "claude-code"
    AUGGIE = "auggie"
    PYTHON = "python"
    NODE = "node"
    SHELL = "shell"
    UNKNOWN = "unknown"


@dataclass
class UnifiedSession:
    """Unified session representation across terminal types."""

    id: str
    name: str
    terminal_type: TerminalType
    state: SessionState = SessionState.UNKNOWN
    last_output: str = ""
    cwd: str = ""
    # For tmux: window_index and pane_index
    window_index: int = 0
    pane_index: int = 0
    # Instance type detection
    instance_type: InstanceType = InstanceType.UNKNOWN


@dataclass
class CommandResult:
    """Result of executing a command in a session."""

    success: bool
    output: str
    state_after: SessionState
    execution_time: float


class ITerminalAdapter(Protocol):
    """Protocol for terminal backend adapters.

    Defines the interface that both iTerm2 and tmux adapters must implement.
    This enables dependency injection and testing with mock adapters.
    """

    async def connect(self) -> bool:
        """Connect to the terminal backend.

        Returns:
            True if connection successful
        """
        ...

    async def list_sessions(self) -> list[UnifiedSession]:
        """List all sessions from this backend.

        Returns:
            List of unified session objects
        """
        ...

    async def get_session_output(self, session_id: str, lines: int = 50) -> str:
        """Get recent output from a session.

        Args:
            session_id: Target session
            lines: Number of lines to retrieve

        Returns:
            Recent terminal output
        """
        ...

    async def send_command(
        self,
        session_id: str,
        command: str,
        wait_for_completion: bool = True,
        timeout: float = 30.0,
    ) -> CommandResult:
        """Send a command to a session.

        Args:
            session_id: Target session
            command: Command to execute
            wait_for_completion: Whether to wait for completion
            timeout: Maximum wait time

        Returns:
            Command execution result
        """
        ...

    async def detect_state(self, session_id: str) -> SessionState:
        """Detect whether a session is idle or running.

        Args:
            session_id: Target session

        Returns:
            Current session state
        """
        ...

    async def get_session_status(self, session_id: str) -> dict:
        """Get comprehensive status of a session with analysis.

        Args:
            session_id: Target session

        Returns:
            Dict with status information and screen digest
        """
        ...
