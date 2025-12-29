"""Tmux terminal adapter implementation."""

import asyncio
import time
from typing import Optional

import libtmux

from .protocols import (
    CommandResult,
    ITerminalAdapter,
    SessionState,
    TerminalType,
    UnifiedSession,
)


class TmuxAdapter:
    """Adapter for tmux terminal operations.

    Wraps libtmux to conform to the ITerminalAdapter protocol.
    All sync operations are wrapped with asyncio.to_thread().
    """

    def __init__(self):
        self._server: Optional[libtmux.Server] = None
        self._sessions_cache: dict[str, UnifiedSession] = {}

    async def connect(self) -> bool:
        """Connect to tmux server."""
        try:
            # Wrap sync operation in thread
            self._server = await asyncio.to_thread(libtmux.Server)
            # Test connection
            await asyncio.to_thread(lambda: self._server.sessions)
            return True
        except Exception:
            self._server = None
            return False

    async def list_sessions(self) -> list[UnifiedSession]:
        """List all tmux sessions."""
        if not self._server:
            return []

        sessions = []
        tmux_sessions = await asyncio.to_thread(lambda: self._server.sessions)

        for ts in tmux_sessions:
            windows = await asyncio.to_thread(lambda: list(ts.windows))
            for window in windows:
                panes = await asyncio.to_thread(lambda: list(window.panes))
                for pane in panes:
                    session_id = (
                        f"tmux:{ts.session_name}:{window.window_index}:{pane.pane_index}"
                    )
                    unified = UnifiedSession(
                        id=session_id,
                        name=f"{ts.session_name}/{window.window_name}[{pane.pane_index}]",
                        terminal_type=TerminalType.TMUX,
                        cwd=pane.pane_current_path or "",
                        window_index=int(window.window_index),
                        pane_index=int(pane.pane_index),
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

            output = await asyncio.to_thread(pane.capture_pane)
            if isinstance(output, list):
                output = "\n".join(output)

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
                return CommandResult(False, "Session not found", SessionState.UNKNOWN, 0)

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
            if indicator in last_line and last_line.index(indicator) > len(last_line) // 2:
                return True

        return False

    async def detect_state(self, session_id: str) -> SessionState:
        """Detect whether session is idle or running."""
        output = await self.get_session_output(session_id, lines=10)

        if self._looks_like_prompt(output):
            return SessionState.IDLE
        else:
            return SessionState.RUNNING

    async def get_session_status(self, session_id: str) -> dict:
        """Get comprehensive status of a session with analysis."""
        output = await self.get_session_output(session_id, lines=100)
        analysis = self._analyze_session_status(output)

        session = self._sessions_cache.get(session_id)
        if session:
            analysis["session_name"] = session.name
            analysis["session_type"] = session.terminal_type.value
            analysis["cwd"] = session.cwd

        return analysis

    def _analyze_session_status(self, output: str) -> dict:
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
        self, lines: list[str], status: str, indicators: dict
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
            line for line in non_empty if any(kw in line.lower() for kw in error_keywords)
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
