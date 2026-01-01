"""Tmux terminal adapter implementation."""

import asyncio
import logging
import re
import subprocess
import time
from typing import Any, Optional

import libtmux

from .protocols import (
    CommandResult,
    SessionState,
    TerminalType,
    UnifiedSession,
)

logger = logging.getLogger(__name__)


class TmuxAdapter:
    """Adapter for tmux terminal operations.

    Wraps libtmux to conform to the ITerminalAdapter protocol.
    All sync operations are wrapped with asyncio.to_thread().
    """

    def __init__(self) -> None:
        self._server: Optional[libtmux.Server] = None
        self._sessions_cache: dict[str, UnifiedSession] = {}

    def _parse_version(self, version_string: str) -> tuple[int, int, str]:
        """Parse tmux version string like 'tmux 3.6a' into (3, 6, 'a').

        Args:
            version_string: Version string from tmux (e.g., 'tmux 3.6a')

        Returns:
            Tuple of (major, minor, suffix) where suffix is empty string if not present
        """
        match = re.match(r"tmux (\d+)\.(\d+)([a-z]?)", version_string.strip())
        if match:
            return (int(match.group(1)), int(match.group(2)), match.group(3))
        return (0, 0, "")

    def _versions_compatible(
        self, client: tuple[int, int, str], server: tuple[int, int, str]
    ) -> bool:
        """Check if client and server versions are compatible.

        Tmux requires exact major.minor match between client and server.

        Args:
            client: Client version tuple (major, minor, suffix)
            server: Server version tuple (major, minor, suffix)

        Returns:
            True if versions are compatible (major.minor match)
        """
        return client[0] == server[0] and client[1] == server[1]

    def _format_version(self, version: tuple[int, int, str]) -> str:
        """Format version tuple as string.

        Args:
            version: Version tuple (major, minor, suffix)

        Returns:
            Formatted version string (e.g., '3.6a')
        """
        return f"{version[0]}.{version[1]}{version[2]}"

    async def connect(self) -> bool:
        """Connect to tmux server with version compatibility checking.

        Detects and warns about tmux client/server version mismatches which
        can cause "not a terminal" errors. Provides actionable troubleshooting.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Get client version via tmux -V
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["tmux", "-V"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                client_version_str = result.stdout.strip()
                client_version = self._parse_version(client_version_str)
                logger.debug(
                    f"Tmux client version: {self._format_version(client_version)}"
                )
            except FileNotFoundError:
                logger.error(
                    "tmux command not found. Please install tmux: brew install tmux"
                )
                self._server = None
                return False
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to get tmux client version: {e}")
                client_version = (0, 0, "")

            # Connect to tmux server
            self._server = await asyncio.to_thread(libtmux.Server)

            # Get server version via display-message
            try:
                server_version_result = await asyncio.to_thread(
                    self._server.cmd, "display-message", "-p", "#{version}"
                )
                # Extract version string from tmux_cmd result
                if isinstance(server_version_result, libtmux.common.tmux_cmd):
                    server_version_str = str(server_version_result.stdout[0])
                else:
                    server_version_str = str(server_version_result)
                server_version = self._parse_version(f"tmux {server_version_str}")
                logger.debug(
                    f"Tmux server version: {self._format_version(server_version)}"
                )

                # Check version compatibility
                if client_version != (0, 0, "") and server_version != (0, 0, ""):
                    if not self._versions_compatible(client_version, server_version):
                        logger.warning(
                            f"Tmux version mismatch detected!\n"
                            f"  Client: {self._format_version(client_version)}\n"
                            f"  Server: {self._format_version(server_version)}\n"
                            f"This may cause 'not a terminal' errors.\n"
                            f"Fix: Run 'tmux kill-server' to restart with matching version."
                        )
            except Exception as e:
                logger.debug(f"Could not verify server version: {e}")

            # Test connection by listing sessions
            if self._server is not None:
                server = self._server  # Capture for type safety in lambda
                await asyncio.to_thread(lambda: server.sessions)
            return True

        except Exception as e:
            # Provide specific guidance for common errors
            error_msg = str(e)
            if "not a terminal" in error_msg.lower():
                logger.error(
                    f"Failed to connect to tmux: {e}\n"
                    f"This error typically indicates a version mismatch.\n"
                    f"Fix: Run 'tmux kill-server' and try again."
                )
            else:
                logger.error(f"Failed to connect to tmux: {e}")

            self._server = None
            return False

    async def list_sessions(self) -> list[UnifiedSession]:
        """List all tmux sessions."""
        if not self._server:
            return []

        sessions = []
        server = self._server  # Capture for type safety in lambda
        tmux_sessions = await asyncio.to_thread(lambda: server.sessions)

        for ts in tmux_sessions:
            windows = await asyncio.to_thread(lambda: list(ts.windows))
            for window in windows:
                panes = await asyncio.to_thread(lambda: list(window.panes))
                for pane in panes:
                    session_id = f"tmux:{ts.session_name}:{window.window_index}:{pane.pane_index}"
                    unified = UnifiedSession(
                        id=session_id,
                        name=f"{ts.session_name}/{window.window_name}[{pane.pane_index}]",
                        terminal_type=TerminalType.TMUX,
                        cwd=pane.pane_current_path or "",
                        window_index=int(window.window_index or 0),
                        pane_index=int(pane.pane_index or 0),
                    )
                    sessions.append(unified)
                    self._sessions_cache[session_id] = unified

        return sessions

    async def get_session_output(self, session_id: str, lines: int = 50) -> str:
        """Get pane content from tmux session."""
        if not self._server:
            return "Not connected"

        parts = session_id.split(":")
        if len(parts) != 4:
            return "Invalid session ID"

        session_name = parts[1]
        window_idx = parts[2]
        pane_idx = parts[3]

        try:
            session = await asyncio.to_thread(
                self._server.sessions.get, session_name=session_name
            )
            if not session:
                return "Session not found"

            window = await asyncio.to_thread(
                session.windows.get, window_index=window_idx
            )
            if not window:
                return "Window not found"

            pane = await asyncio.to_thread(window.panes.get, pane_index=pane_idx)
            if not pane:
                return "Pane not found"

            raw_output = await asyncio.to_thread(pane.capture_pane)
            if isinstance(raw_output, list):
                output: str = "\n".join(raw_output)
            else:
                output = str(raw_output)

            return output

        except Exception as e:
            return f"Error: {e}"

    async def send_command(
        self,
        session_id: str,
        command: str,
        wait_for_completion: bool = True,
        timeout: float = 30.0,
    ) -> CommandResult:
        """Send command to tmux pane."""
        if not self._server:
            return CommandResult(False, "Not connected", SessionState.UNKNOWN, 0)

        parts = session_id.split(":")
        if len(parts) != 4:
            return CommandResult(False, "Invalid session ID", SessionState.UNKNOWN, 0)

        session_name = parts[1]
        window_idx = parts[2]
        pane_idx = parts[3]

        start_time = time.time()

        try:
            session = await asyncio.to_thread(
                self._server.sessions.get, session_name=session_name
            )
            if not session:
                return CommandResult(
                    False, "Session not found", SessionState.UNKNOWN, 0
                )

            window = await asyncio.to_thread(
                session.windows.get, window_index=window_idx
            )
            if not window:
                return CommandResult(False, "Window not found", SessionState.UNKNOWN, 0)

            pane = await asyncio.to_thread(window.panes.get, pane_index=pane_idx)
            if not pane:
                return CommandResult(False, "Pane not found", SessionState.UNKNOWN, 0)

            # Send keys with enter
            await asyncio.to_thread(pane.send_keys, command, enter=True)

            # Wait for completion if requested
            if wait_for_completion:
                output = await self._wait_for_completion(session_id, timeout)
            else:
                await asyncio.sleep(0.5)
                output = await self.get_session_output(session_id)

            # Detect state
            state = await self.detect_state(session_id)

            execution_time = time.time() - start_time
            return CommandResult(True, output, state, execution_time)

        except Exception as e:
            return CommandResult(False, f"Error: {e}", SessionState.UNKNOWN, 0)

    async def _wait_for_completion(self, session_id: str, timeout: float) -> str:
        """Wait for command completion by monitoring output stability."""
        start_time = time.time()
        last_output = ""
        stable_count = 0
        required_stable = 3

        while (time.time() - start_time) < timeout:
            await asyncio.sleep(0.3)
            current_output = await self.get_session_output(session_id)

            if current_output == last_output:
                stable_count += 1
                if stable_count >= required_stable:
                    if self._looks_like_prompt(current_output):
                        return current_output
            else:
                stable_count = 0
                last_output = current_output

        return last_output

    def _looks_like_prompt(self, output: str) -> bool:
        """Heuristic to detect if output ends at a shell prompt."""
        if not output:
            return False

        lines = output.strip().split("\n")
        if not lines:
            return False

        last_line = lines[-1].strip()

        prompt_indicators = ["$", "#", ">", ">>>", "❯", "➜", "%"]
        for indicator in prompt_indicators:
            if last_line.endswith(indicator):
                return True
            if (
                indicator in last_line
                and last_line.index(indicator) > len(last_line) // 2
            ):
                return True

        return False

    async def detect_state(self, session_id: str) -> SessionState:
        """Detect whether session is idle or running."""
        output = await self.get_session_output(session_id, lines=10)

        if self._looks_like_prompt(output):
            return SessionState.IDLE
        else:
            return SessionState.RUNNING

    async def get_session_status(self, session_id: str) -> dict[str, Any]:
        """Get comprehensive status of a session with analysis."""
        output = await self.get_session_output(session_id, lines=100)
        analysis = self._analyze_session_status(output)

        session = self._sessions_cache.get(session_id)
        if session:
            analysis["session_name"] = session.name
            analysis["session_type"] = session.terminal_type.value
            analysis["cwd"] = session.cwd

        return analysis

    def _analyze_session_status(self, output: str) -> dict[str, Any]:
        """Analyze terminal output to determine working status."""
        if not output:
            return {
                "is_working": False,
                "status": "unknown",
                "screen_summary": "No output available",
                "last_lines": [],
                "indicators": {},
            }

        lines = output.strip().split("\n")
        last_lines = lines[-5:] if len(lines) >= 5 else lines
        last_line = lines[-1].strip() if lines else ""

        # Detect working indicators
        spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏|/-\\"
        has_spinner = any(char in output for char in spinner_chars)

        progress_patterns = [
            "[====",
            "====>",
            "loading",
            "processing",
            "Loading",
            "Processing",
            "%]",
            "% ",
            "downloading",
            "installing",
            "building",
            "compiling",
        ]
        has_progress = any(pattern in output for pattern in progress_patterns)

        working_keywords = [
            "running",
            "executing",
            "building",
            "compiling",
            "installing",
            "downloading",
            "fetching",
            "processing",
            "loading",
            "waiting",
            "analyzing",
            "generating",
            "creating",
        ]
        has_working_keyword = any(
            keyword.lower() in output.lower() for keyword in working_keywords
        )

        # Detect idle/prompt indicators
        prompt_chars = ["$", "#", ">", ">>>", "❯", "➜", "%"]
        has_prompt = any(last_line.endswith(char) for char in prompt_chars)

        # Check for waiting for input patterns
        waiting_patterns = [
            "press any key",
            "enter to continue",
            "continue?",
            "y/n",
            "password:",
            "username:",
            "[y/N]",
            "[Y/n]",
        ]
        waiting_for_input = any(
            pattern.lower() in last_line.lower() for pattern in waiting_patterns
        )

        # Determine status
        indicators = {
            "has_spinner": has_spinner,
            "has_progress": has_progress,
            "has_working_keyword": has_working_keyword,
            "has_prompt": has_prompt,
            "waiting_for_input": waiting_for_input,
        }

        is_working = (
            has_spinner or has_progress or has_working_keyword
        ) and not has_prompt

        if waiting_for_input:
            status = "waiting_for_input"
        elif has_prompt and not is_working:
            status = "idle"
        elif is_working:
            status = "working"
        else:
            status = "unknown"

        # Generate screen summary
        screen_summary = self._generate_screen_summary(lines, status, indicators)

        return {
            "is_working": is_working,
            "status": status,
            "screen_summary": screen_summary,
            "last_lines": last_lines,
            "indicators": indicators,
        }

    def _generate_screen_summary(
        self, lines: list[str], status: str, indicators: dict[str, Any]
    ) -> str:
        """Generate a concise summary of what's on screen."""
        if not lines:
            return "Empty screen"

        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            return "Empty screen"

        summary_parts = []

        # Status prefix
        if status == "working":
            summary_parts.append("Session is actively processing.")
        elif status == "idle":
            summary_parts.append("Session is idle at prompt.")
        elif status == "waiting_for_input":
            summary_parts.append("Session is waiting for user input.")

        # Detect command patterns
        commands = [
            line
            for line in non_empty
            if any(line.strip().startswith(c) for c in ["$", "#", ">", ">>>"])
        ]
        if commands:
            last_command = commands[-1].strip()
            summary_parts.append(f"Last command: {last_command[:50]}")

        # Detect error patterns
        error_keywords = ["error:", "failed", "exception", "traceback", "fatal"]
        errors = [
            line
            for line in non_empty
            if any(kw in line.lower() for kw in error_keywords)
        ]
        if errors:
            summary_parts.append(f"Errors detected ({len(errors)} lines)")

        # Detect progress/working indicators
        if indicators.get("has_progress"):
            summary_parts.append("Progress indicator visible")
        if indicators.get("has_spinner"):
            summary_parts.append("Spinner/loading animation active")

        # Detect completion messages
        completion_keywords = ["done", "complete", "finished", "success"]
        completions = [
            line
            for line in non_empty
            if any(kw in line.lower() for kw in completion_keywords)
        ]
        if completions and not indicators.get("is_working"):
            summary_parts.append("Task appears completed")

        # Add line count
        summary_parts.append(f"({len(non_empty)} lines of output)")

        return " ".join(summary_parts)

    async def create_session(
        self,
        name: str,
        working_dir: str,
        command: Optional[str] = None,
    ) -> str:
        """Create a new tmux session.

        Args:
            name: Session name
            working_dir: Initial working directory
            command: Optional command to run (if None, just opens shell)

        Returns:
            Session ID of the newly created session (format: tmux:name:0:0)

        Raises:
            RuntimeError: If session creation fails
        """
        if not self._server:
            raise RuntimeError("Not connected to tmux server")

        try:
            # Create new session with start-directory
            # The session will start in the specified directory
            session = await asyncio.to_thread(
                self._server.new_session,
                session_name=name,
                start_directory=working_dir,
                attach=False,  # Don't attach to it
            )

            # If a command is provided, send it to the first pane
            if command:
                windows = await asyncio.to_thread(lambda: list(session.windows))
                if windows:
                    window = windows[0]
                    panes = await asyncio.to_thread(lambda: list(window.panes))
                    if panes:
                        pane = panes[0]
                        # Send command with enter
                        await asyncio.to_thread(pane.send_keys, command, enter=True)

            # Build session ID (tmux:session_name:window_index:pane_index)
            session_id = f"tmux:{name}:0:0"

            return session_id

        except Exception as e:
            raise RuntimeError(f"Failed to create tmux session: {e}") from e

    async def kill_session(self, session_id: str) -> bool:
        """Kill a tmux session.

        Args:
            session_id: Target session ID (format: tmux:name:window:pane)

        Returns:
            True if session was killed successfully
        """
        import logging

        logger = logging.getLogger(__name__)

        logger.debug(f"TmuxAdapter.kill_session called with: {session_id}")
        logger.debug(f"Server connected: {self._server is not None}")

        if not self._server:
            logger.error("Not connected to tmux server")
            return False

        parts = session_id.split(":")
        logger.debug(f"Session ID parts: {parts}")

        if len(parts) != 4:
            logger.error(
                f"Invalid session ID format (expected 4 parts, got {len(parts)})"
            )
            return False

        session_name = parts[1]
        logger.debug(f"Extracted session name: {session_name}")

        try:
            # Get the session
            logger.debug(f"Getting session from tmux server: {session_name}")
            session = await asyncio.to_thread(
                self._server.sessions.get, session_name=session_name
            )
            logger.debug(f"Got session object: {session}")

            if not session:
                logger.error(f"Session not found in tmux: {session_name}")
                return False

            # Kill the entire session
            # Note: session.kill_session() was deprecated, use session.kill() instead
            logger.debug(f"Killing tmux session: {session_name}")
            await asyncio.to_thread(session.kill)
            logger.debug(f"Successfully killed tmux session: {session_name}")

            # Remove from cache
            if session_id in self._sessions_cache:
                del self._sessions_cache[session_id]
                logger.debug(f"Removed from cache: {session_id}")

            return True

        except Exception as e:
            logger.exception(f"Exception killing tmux session: {e}")
            return False
