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
from .project_registry import ProjectRegistry
from .instance_detector import InstanceDetector


class TerminalService:
    """High-level service for terminal operations.

    Manages multiple terminal adapters (iTerm2, tmux) through a unified interface.
    Provides service-level operations like listing all sessions, sending commands,
    and monitoring session status.

    Integrates ProjectRegistry for @project addressing and InstanceDetector for
    automatic detection of Claude Code, Auggie, Python, Node, and shell sessions.
    """

    def __init__(
        self,
        iterm2_adapter: ITerm2Adapter,
        tmux_adapter: TmuxAdapter,
        project_registry: Optional[ProjectRegistry] = None,
        instance_detector: Optional[InstanceDetector] = None,
    ):
        """Initialize terminal service.

        Args:
            iterm2_adapter: iTerm2 adapter instance
            tmux_adapter: Tmux adapter instance
            project_registry: Project registry for @project addressing
            instance_detector: Instance detector for automatic type detection
        """
        self.iterm2 = iterm2_adapter
        self.tmux = tmux_adapter
        self.project_registry = project_registry or ProjectRegistry()
        self.instance_detector = instance_detector or InstanceDetector()
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

        Enriches sessions with instance type detection and registers with ProjectRegistry.

        Returns:
            Combined list of sessions from all backends with instance types detected
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

        # Detect instance types for all sessions
        await self._detect_instance_types(sessions)

        # Register all sessions with project registry
        await self.project_registry.refresh_all(sessions)

        return sessions

    async def _detect_instance_types(self, sessions: list[UnifiedSession]) -> None:
        """Detect and set instance types for all sessions.

        Args:
            sessions: List of sessions to enrich with instance types
        """
        for session in sessions:
            adapter = self._get_adapter_for_session(session.id)
            if adapter:
                try:
                    instance_type = await self.instance_detector.detect_from_session(
                        session, adapter, lines=100
                    )
                    session.instance_type = instance_type
                except Exception:
                    # Keep default UNKNOWN on detection failure
                    pass

    async def get_session_output(self, session_id: str, lines: int = 50) -> str:
        """Get recent output from a session.

        Supports @project addressing for session lookup.

        Args:
            session_id: Target session ID or @project address
            lines: Number of lines to retrieve

        Returns:
            Recent terminal output
        """
        # Resolve @project address if needed
        resolved_id = await self._resolve_session_id(session_id)
        if not resolved_id:
            return f"Session not found: {session_id}"

        adapter = self._get_adapter_for_session(resolved_id)
        if not adapter:
            return "Session not found or backend not available"

        return await adapter.get_session_output(resolved_id, lines)

    async def send_command(
        self,
        session_id: str,
        command: str,
        wait_for_completion: bool = True,
        timeout: float = 30.0,
    ) -> CommandResult:
        """Send a command to a session.

        Supports @project addressing for session lookup.

        Args:
            session_id: Target session ID or @project address
            command: Command to execute
            wait_for_completion: Whether to wait for completion
            timeout: Maximum wait time

        Returns:
            Command execution result
        """
        # Resolve @project address if needed
        resolved_id = await self._resolve_session_id(session_id)
        if not resolved_id:
            return CommandResult(
                False,
                f"Session not found: {session_id}",
                SessionState.UNKNOWN,
                0.0,
            )

        adapter = self._get_adapter_for_session(resolved_id)
        if not adapter:
            return CommandResult(
                False, "Session not found or backend not available", SessionState.UNKNOWN, 0.0
            )

        return await adapter.send_command(
            resolved_id, command, wait_for_completion, timeout
        )

    async def detect_state(self, session_id: str) -> SessionState:
        """Detect whether a session is idle or running.

        Supports @project addressing for session lookup.

        Args:
            session_id: Target session ID or @project address

        Returns:
            Current session state
        """
        # Resolve @project address if needed
        resolved_id = await self._resolve_session_id(session_id)
        if not resolved_id:
            return SessionState.UNKNOWN

        adapter = self._get_adapter_for_session(resolved_id)
        if not adapter:
            return SessionState.UNKNOWN

        return await adapter.detect_state(resolved_id)

    async def get_session_status(self, session_id: str) -> dict:
        """Get comprehensive status of a session with analysis.

        Supports @project addressing for session lookup.

        Args:
            session_id: Target session ID or @project address

        Returns:
            Dict with status information and screen digest
        """
        # Resolve @project address if needed
        resolved_id = await self._resolve_session_id(session_id)
        if not resolved_id:
            return {
                "is_working": False,
                "status": "unknown",
                "screen_summary": f"Session not found: {session_id}",
                "last_lines": [],
                "indicators": {},
            }

        adapter = self._get_adapter_for_session(resolved_id)
        if not adapter:
            return {
                "is_working": False,
                "status": "unknown",
                "screen_summary": "Session not found",
                "last_lines": [],
                "indicators": {},
            }

        return await adapter.get_session_status(resolved_id)

    async def _resolve_session_id(self, session_id: str) -> Optional[str]:
        """Resolve @project address to session ID.

        Args:
            session_id: Session ID or @project address

        Returns:
            Resolved session ID or None if not found
        """
        # If it's an @project address, resolve it
        if session_id.startswith("@"):
            return await self.project_registry.resolve(session_id)

        # Otherwise, return as-is (already a session ID)
        return session_id

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
