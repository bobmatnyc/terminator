"""iTerm2 terminal adapter implementation."""

import asyncio
import time
from typing import Optional

from .protocols import (
    CommandResult,
    ITerminalAdapter,
    SessionState,
    TerminalType,
    UnifiedSession,
)


class ITerm2Adapter:
    """Adapter for iTerm2 terminal operations.

    Wraps the iterm2 Python API to conform to the ITerminalAdapter protocol.
    """

    def __init__(self):
        self._connection: Optional[object] = None
        self._app: Optional[object] = None
        self._sessions_cache: dict[str, UnifiedSession] = {}

    async def connect(self) -> bool:
        """Connect to iTerm2."""
        try:
            import iterm2

            self._connection = await iterm2.Connection.async_create()
            self._app = await iterm2.async_get_app(self._connection)
            return True
        except Exception:
            return False

    async def list_sessions(self) -> list[UnifiedSession]:
        """List all iTerm2 sessions."""
        if not self._app:
            return []

        sessions = []
        for window in self._app.windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    session_id = f"iterm2:{session.session_id}"
                    unified = UnifiedSession(
                        id=session_id,
                        name=session.name or "Unnamed",
                        terminal_type=TerminalType.ITERM2,
                    )
                    sessions.append(unified)
                    self._sessions_cache[session_id] = unified

        return sessions

    async def get_session_output(self, session_id: str, lines: int = 50) -> str:
        """Get screen contents from iTerm2 session."""
        if not self._app:
            return "Not connected"

        iterm_session_id = session_id.replace("iterm2:", "")
        session = self._app.get_session_by_id(iterm_session_id)

        if not session:
            return "Session not found"

        contents = await session.async_get_screen_contents()
        output_lines = []
        line_count = min(lines, contents.number_of_lines)

        for i in range(line_count):
            line = contents.line(i)
            output_lines.append(line.string)

        return "\n".join(output_lines)

    async def send_command(
        self,
        session_id: str,
        command: str,
        wait_for_completion: bool = True,
        timeout: float = 30.0,
    ) -> CommandResult:
        """Send command to iTerm2 session."""
        if not self._app:
            return CommandResult(False, "Not connected", SessionState.UNKNOWN, 0)

        iterm_session_id = session_id.replace("iterm2:", "")
        session = self._app.get_session_by_id(iterm_session_id)

        if not session:
            return CommandResult(False, "Session not found", SessionState.UNKNOWN, 0)

        start_time = time.time()

        # Send command with \r (carriage return) for better REPL compatibility
        await session.async_send_text(command + "\r")

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
        """Create a new iTerm2 session.

        Args:
            name: Session name
            working_dir: Initial working directory
            command: Optional command to run (if None, just opens shell)

        Returns:
            Session ID of the newly created session (format: iterm2:session_id)

        Raises:
            RuntimeError: If session creation fails
        """
        if not self._app:
            raise RuntimeError("Not connected to iTerm2")

        try:
            import iterm2

            # Get current window or create new one
            window = self._app.current_terminal_window
            if not window:
                window = await iterm2.Window.async_create(self._connection)

            # Create new tab
            tab = await window.async_create_tab()
            if not tab:
                raise RuntimeError("Failed to create tab")

            # Get the session from the new tab
            session = tab.current_session
            if not session:
                raise RuntimeError("Failed to get session from new tab")

            # Set session name
            await session.async_set_name(name)

            # Change to working directory and run command if provided
            cd_command = f"cd {working_dir}"
            await session.async_send_text(cd_command + "\r")

            # Wait a bit for cd to complete
            await asyncio.sleep(0.3)

            # Send the command if provided
            if command:
                await session.async_send_text(command + "\r")

            # Build session ID
            session_id = f"iterm2:{session.session_id}"

            return session_id

        except Exception as e:
            raise RuntimeError(f"Failed to create iTerm2 session: {e}") from e
