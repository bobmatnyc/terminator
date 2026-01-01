"""Terminal service for unified session management."""

from typing import Any, Optional

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

        Logs errors with context to aid troubleshooting while continuing
        to attempt all backends.

        Returns:
            Dict mapping backend name to connection status
        """
        import logging

        logger = logging.getLogger(__name__)
        status = {"tmux": False, "iterm2": False}

        # Connect to tmux
        try:
            if await self.tmux.connect():
                status["tmux"] = True
                self._adapters["tmux"] = self.tmux
            else:
                logger.debug("Tmux connection returned False (see tmux adapter logs)")
        except Exception as e:
            logger.warning(f"Exception while connecting to tmux: {e}")

        # Connect to iTerm2
        try:
            if await self.iterm2.connect():
                status["iterm2"] = True
                self._adapters["iterm2"] = self.iterm2
            else:
                logger.debug(
                    "iTerm2 connection returned False (see iterm2 adapter logs)"
                )
        except Exception as e:
            logger.warning(f"Exception while connecting to iTerm2: {e}")

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
                False,
                "Session not found or backend not available",
                SessionState.UNKNOWN,
                0.0,
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

    async def get_session_status(self, session_id: str) -> dict[str, Any]:
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

    async def start_session(
        self,
        project_path: str,
        agent: str = "shell",
        name: Optional[str] = None,
    ) -> str:
        """Start a new coding session.

        Creates a new terminal session in the specified project directory,
        optionally running an agent command (Claude Code, Auggie, etc.).

        Args:
            project_path: Path to the project directory
            agent: Agent type (claude-code, auggie, python, node, shell)
            name: Custom session name (defaults to project directory name)

        Returns:
            Project address (@project or @project:N)

        Raises:
            RuntimeError: If no terminal backends are available or session creation fails
        """
        from pathlib import Path

        # Validate project path
        project_dir = Path(project_path).expanduser().resolve()
        if not project_dir.exists():
            raise RuntimeError(f"Project directory does not exist: {project_path}")

        if not project_dir.is_dir():
            raise RuntimeError(f"Path is not a directory: {project_path}")

        # Determine session name (default to project directory name)
        session_name = name or project_dir.name

        # Get agent command from config
        from ..config import get_settings

        settings = get_settings()
        agent_commands = {
            "claude-code": settings.agent_claude_code_cmd,
            "auggie": settings.agent_auggie_cmd,
            "python": settings.agent_python_cmd,
            "node": settings.agent_node_cmd,
            "shell": None,  # No command for shell
        }

        if agent not in agent_commands:
            raise ValueError(
                f"Unknown agent type: {agent}. "
                f"Valid options: {', '.join(agent_commands.keys())}"
            )

        command = agent_commands[agent]

        # Try to create session with preferred backend (tmux first, then iTerm2)
        session_id: Optional[str] = None

        if "tmux" in self._adapters:
            try:
                session_id = await self.tmux.create_session(
                    name=session_name,
                    working_dir=str(project_dir),
                    command=command,
                )
            except Exception:
                # Log error but try next backend
                pass

        if not session_id and "iterm2" in self._adapters:
            try:
                session_id = await self.iterm2.create_session(
                    name=session_name,
                    working_dir=str(project_dir),
                    command=command,
                )
            except Exception as e:
                raise RuntimeError(f"Failed to create iTerm2 session: {e}") from e

        if not session_id:
            raise RuntimeError(
                "No terminal backends available. Please ensure tmux or iTerm2 is running."
            )

        # Refresh sessions to register the new one
        await self.list_all_sessions()

        # Get project address
        project_address = await self.project_registry.resolve(f"@{session_name}")
        if not project_address:
            # If resolve fails, the session might not have been registered yet
            # Return generic address
            project_address = f"@{session_name}"

        return project_address

    async def kill_session(self, session_id: str) -> bool:
        """Kill a terminal session.

        Supports @project addressing for session lookup.

        Args:
            session_id: Target session ID or @project address

        Returns:
            True if session was killed successfully
        """
        import logging

        logger = logging.getLogger(__name__)

        logger.debug(f"kill_session called with: {session_id}")

        # Resolve @project address if needed
        resolved_id = await self._resolve_session_id(session_id)
        logger.debug(f"Resolved session ID: {resolved_id}")

        if not resolved_id:
            logger.error(f"Failed to resolve session ID: {session_id}")
            return False

        logger.debug(f"Available adapters: {list(self._adapters.keys())}")
        adapter = self._get_adapter_for_session(resolved_id)
        logger.debug(f"Got adapter: {adapter}")

        if not adapter:
            logger.error(f"No adapter found for session: {resolved_id}")
            return False

        # Kill the session
        logger.debug(f"Calling adapter.kill_session({resolved_id})")
        try:
            success = await adapter.kill_session(resolved_id)
            logger.debug(f"adapter.kill_session returned: {success}")
        except Exception as e:
            logger.exception(f"Exception during kill_session: {e}")
            return False

        # Remove from cache if successful
        if success and resolved_id in self._sessions_cache:
            del self._sessions_cache[resolved_id]
            logger.debug(f"Removed {resolved_id} from cache")

        return success
