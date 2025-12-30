"""Interactive session management TUI using Rich."""

import asyncio
import select
import subprocess
import sys
import termios
import tty

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ...adapters.protocols import UnifiedSession
from ...services.terminal import TerminalService
from ...services.session_monitor import SessionMonitorService
from ...services.events import SessionEvent, EventType


class SessionManagerTUI:
    """Interactive terminal UI for managing sessions.

    Features:
    - List all sessions with @project addresses, instance type, session ID
    - Arrow keys to navigate/select sessions
    - Keyboard shortcuts:
        - a/Enter: Attach to selected session (runs tmux attach -t <session>)
        - k/d: Kill selected session
        - r: Refresh session list
        - q/Esc: Quit
    - Show session details in panel when selected
    - Confirmation prompt before killing
    """

    def __init__(
        self,
        terminal_service: TerminalService,
        session_monitor: SessionMonitorService,
    ) -> None:
        """Initialize session manager TUI.

        Args:
            terminal_service: Terminal service for session operations
            session_monitor: Session monitor service for event tracking
        """
        # Existing
        self.terminal_service = terminal_service
        self.console = Console()
        self.sessions: list[UnifiedSession] = []
        self.selected_index = 0
        self.session_to_address: dict[str, str] = {}
        self.running = True
        self.message: str = ""
        self.message_type: str = "info"  # info, success, error, warning

        # NEW: Monitoring state
        self.session_monitor = session_monitor
        self.monitored_sessions: set[str] = set()
        self.event_log: list[SessionEvent] = []
        self.max_events = 50
        self.show_events = True

    async def run(self) -> None:
        """Run the interactive TUI."""
        # Load initial sessions
        await self.refresh_sessions()

        if not self.sessions:
            self.console.print(
                "[yellow]No sessions found. Press any key to exit.[/yellow]"
            )
            self._get_key()
            return

        # Set up terminal for raw input
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setcbreak(fd)

            with Live(
                self._render(),
                console=self.console,
                refresh_per_second=4,
                screen=True,
            ) as live:
                while self.running:
                    # Non-blocking key read with timeout
                    key = await asyncio.to_thread(self._get_key_nonblocking)

                    if key:
                        await self._handle_key(key)

                    # NEW: Process events
                    await self._process_events()

                    # Update display
                    live.update(self._render())

                    # Small delay to prevent CPU spinning
                    await asyncio.sleep(0.05)

        finally:
            # NEW: Cleanup monitoring
            await self.session_monitor.shutdown()
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _get_key_nonblocking(self) -> str:
        """Get a key press without blocking (with 50ms timeout).

        Handles escape sequences (arrow keys) by reading full sequence.

        Returns:
            Key character or full escape sequence, or empty string if no key pressed
        """
        # Check if stdin has data available (50ms timeout)
        if select.select([sys.stdin], [], [], 0.05)[0]:
            key = sys.stdin.read(1)

            # If ESC, check for arrow key sequence
            if key == "\x1b":
                # Check if more characters available (with short timeout)
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    # Read next 2 characters for arrow key sequence
                    next_chars = sys.stdin.read(2)
                    # Return full escape sequence
                    return key + next_chars

            return key
        return ""

    def _get_key(self) -> str:
        """Get a single key press (blocking).

        Returns:
            Key character
        """
        return sys.stdin.read(1)

    async def _handle_key(self, key: str) -> None:
        """Handle keyboard input.

        Args:
            key: Key character or escape sequence
        """
        # Arrow keys (escape sequences) - now come as full sequences from _get_key_nonblocking
        if key == "\x1b[A":  # Up arrow
            self.selected_index = max(0, self.selected_index - 1)
            self.message = ""
        elif key == "\x1b[B":  # Down arrow
            self.selected_index = min(
                len(self.sessions) - 1, self.selected_index + 1
            )
            self.message = ""
        elif key == "\x1b":  # Just ESC key - quit
            self.running = False

        # Navigation
        elif key in ("j", "J"):  # Down (vim-style)
            self.selected_index = min(len(self.sessions) - 1, self.selected_index + 1)
            self.message = ""
        elif key in ("k", "K"):  # Up (vim-style)
            self.selected_index = max(0, self.selected_index - 1)
            self.message = ""

        # Actions
        elif key in ("a", "A", "\r", "\n"):  # Attach (Enter)
            await self._attach_session()
        elif key in ("d", "D"):  # Kill
            await self._kill_session()
        elif key in ("r", "R"):  # Refresh
            await self.refresh_sessions()
            self.message = "Sessions refreshed"
            self.message_type = "success"
        elif key in ("q", "Q"):  # Quit
            self.running = False

        # Toggle monitoring for selected session
        elif key in ("m", "M"):
            await self._toggle_monitoring()

        # Toggle event panel visibility
        elif key in ("e", "E"):
            self.show_events = not self.show_events
            self.message = "Event panel " + ("shown" if self.show_events else "hidden")
            self.message_type = "info"

    async def refresh_sessions(self) -> None:
        """Refresh the session list from terminal service."""
        self.sessions = await self.terminal_service.list_all_sessions()

        # Build project address map
        projects = await self.terminal_service.project_registry.list_projects()
        self.session_to_address = {}
        for project_name, project_sessions in projects.items():
            for ps in project_sessions:
                self.session_to_address[ps.session_id] = ps.address

        # Clamp selected index
        if self.selected_index >= len(self.sessions):
            self.selected_index = max(0, len(self.sessions) - 1)

    async def _attach_session(self) -> None:
        """Attach to the selected session using tmux attach."""
        if not self.sessions:
            return

        session = self.sessions[self.selected_index]

        # Only tmux sessions support attach via tmux command
        if not session.id.startswith("tmux:"):
            self.message = "Attach only supported for tmux sessions"
            self.message_type = "error"
            return

        # Extract tmux session name from ID (format: tmux:name:window:pane)
        parts = session.id.split(":")
        if len(parts) < 2:
            self.message = "Invalid session ID format"
            self.message_type = "error"
            return

        session_name = parts[1]

        # Exit TUI and attach to tmux session
        self.running = False

        # Clear screen before attaching
        self.console.clear()

        # Run tmux attach in foreground
        try:
            subprocess.run(["tmux", "attach", "-t", session_name], check=True)
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Error attaching to session: {e}[/red]")
        except FileNotFoundError:
            self.console.print("[red]tmux command not found[/red]")

    async def _kill_session(self) -> None:
        """Kill the selected session with confirmation."""
        if not self.sessions:
            return

        session = self.sessions[self.selected_index]
        address = self.session_to_address.get(session.id, session.id[:30])

        # Confirmation prompt - temporarily restore terminal
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            self.console.clear()
            self.console.print(
                Panel(
                    f"[bold red]Kill session?[/bold red]\n\n"
                    f"Address: [cyan]{address}[/cyan]\n"
                    f"Instance: [magenta]({session.instance_type.value})[/magenta]\n"
                    f"CWD: [green]{session.cwd}[/green]\n\n"
                    f"[yellow]Press 'y' to confirm, any other key to cancel[/yellow]",
                    title="Confirm Kill",
                    border_style="red",
                )
            )

            # Get confirmation
            key = sys.stdin.read(1)

            if key.lower() == "y":
                # Kill the session
                success = await self.terminal_service.kill_session(session.id)

                if success:
                    self.message = f"Killed session: {address}"
                    self.message_type = "success"
                    # Refresh session list
                    await self.refresh_sessions()
                else:
                    self.message = "Failed to kill session"
                    self.message_type = "error"
            else:
                self.message = "Kill cancelled"
                self.message_type = "info"

        finally:
            # Restore raw mode
            tty.setcbreak(fd)

    async def _toggle_monitoring(self) -> None:
        """Toggle monitoring for selected session."""
        if not self.sessions:
            return

        session = self.sessions[self.selected_index]
        address = self.session_to_address.get(session.id, session.id[:20])

        if self.session_monitor.is_monitoring(session.id):
            await self.session_monitor.stop_monitoring(session.id)
            self.monitored_sessions.discard(session.id)
            self.message = f"Stopped monitoring: {address}"
            self.message_type = "info"
        else:
            success = await self.session_monitor.start_monitoring(session.id, address)
            if success:
                self.monitored_sessions.add(session.id)
                self.message = f"Monitoring: {address}"
                self.message_type = "success"
            else:
                self.message = f"Already monitoring: {address}"
                self.message_type = "warning"

    async def _process_events(self) -> None:
        """Process pending events from session monitor."""
        events = await self.session_monitor.get_events(max_events=10)

        for event in events:
            self.event_log.append(event)

            # Trim event log if too long
            if len(self.event_log) > self.max_events:
                self.event_log = self.event_log[-self.max_events :]

            # Show notification for important events
            if event.event_type == EventType.INPUT_REQUIRED:
                self.message = f"INPUT NEEDED: {event.session_address}"
                self.message_type = "warning"
            elif event.event_type == EventType.OUTPUT_READY:
                self.message = f"OUTPUT READY: {event.session_address}"
                self.message_type = "success"

    def _get_status_indicator(self, session_id: str) -> str:
        """Get status indicator for a session."""
        if session_id not in self.monitored_sessions:
            return "  "

        # Check recent events for this session
        recent_events = [e for e in self.event_log[-10:] if e.session_id == session_id]

        if not recent_events:
            return "* "  # Monitoring, no events yet

        latest = recent_events[-1]

        if latest.event_type == EventType.INPUT_REQUIRED:
            return "! "  # Input needed
        elif latest.event_type == EventType.OUTPUT_READY:
            return "v "  # Output ready
        elif latest.event_type == EventType.ERROR:
            return "x "  # Error
        else:
            return "* "  # Generic monitoring

    def _render_events_panel(self) -> Panel:
        """Render the events log panel."""
        if not self.event_log:
            content = "[dim]No events yet. Press 'm' to monitor a session.[/dim]"
        else:
            display_events = self.event_log[-6:]  # Show last 6
            lines = []
            for event in display_events:
                time_str = event.timestamp.strftime("%H:%M:%S")

                if event.event_type == EventType.INPUT_REQUIRED:
                    style = "bold red"
                    icon = "!"
                elif event.event_type == EventType.OUTPUT_READY:
                    style = "bold green"
                    icon = "v"
                elif event.event_type == EventType.ERROR:
                    style = "red"
                    icon = "x"
                else:
                    style = "dim"
                    icon = "*"

                line = f"[{style}]{icon}[/{style}] [{style}]{time_str}[/{style}] {event.session_address}: {event.message}"
                lines.append(line)

            content = "\n".join(lines)

        return Panel(
            content,
            title=f"Events ({len(self.event_log)} total)",
            border_style="yellow",
        )

    def _render(self) -> Layout:
        """Render the TUI layout.

        Returns:
            Rich Layout object
        """
        layout = Layout()

        if self.show_events and self.monitored_sessions:
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body", ratio=2),
                Layout(name="events", size=8),
                Layout(name="details", size=6),
                Layout(name="footer", size=3),
            )
        else:
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body"),
                Layout(name="details", size=6),
                Layout(name="footer", size=3),
            )

        # Header
        layout["header"].update(
            Panel(
                "[bold green]Terminator Session Manager[/bold green]",
                border_style="green",
            )
        )

        # Body - session list
        if self.sessions:
            table = Table(show_header=True, header_style="bold cyan", box=None)
            table.add_column("", width=2)  # Selection indicator
            table.add_column("St", width=3)  # NEW: Status indicator
            table.add_column("Address", style="cyan", no_wrap=True, width=20)
            table.add_column("Instance", style="magenta", width=15)
            table.add_column("Session ID", style="dim", no_wrap=True, width=35)

            for i, session in enumerate(self.sessions):
                # Selection indicator
                indicator = ">" if i == self.selected_index else " "

                # NEW: Status indicator
                status_indicator = self._get_status_indicator(session.id)

                # Get address
                address = self.session_to_address.get(
                    session.id, session.id[:20] + "..."
                )

                # Instance type
                instance = f"({session.instance_type.value})"

                # Truncate session ID
                session_id = (
                    session.id[:35] + "..." if len(session.id) > 35 else session.id
                )

                # Highlight selected row
                style = "bold white on blue" if i == self.selected_index else ""

                table.add_row(
                    Text(indicator, style=style),
                    Text(status_indicator, style=style),
                    Text(address, style=style),
                    Text(instance, style=style),
                    Text(session_id, style=style),
                )

            layout["body"].update(Panel(table, border_style="white"))
        else:
            layout["body"].update(
                Panel(
                    "[yellow]No sessions found. Press 'q' to quit.[/yellow]",
                    border_style="yellow",
                )
            )

        # NEW: Events panel (only if show_events and monitored_sessions)
        if self.show_events and self.monitored_sessions:
            layout["events"].update(self._render_events_panel())

        # Details panel - show selected session info
        if self.sessions and 0 <= self.selected_index < len(self.sessions):
            session = self.sessions[self.selected_index]
            details = (
                f"[cyan]CWD:[/cyan] {session.cwd or 'N/A'}\n"
                f"[cyan]State:[/cyan] {session.state.value.upper()}\n"
                f"[cyan]Instance:[/cyan] {session.instance_type.value}\n"
                f"[cyan]Type:[/cyan] {session.terminal_type.value}"
            )
            layout["details"].update(
                Panel(details, title="Session Details", border_style="blue")
            )
        else:
            layout["details"].update(Panel("No session selected", border_style="dim"))

        # Footer - help and message
        help_text = (
            "[bold cyan]jk[/bold cyan]: Nav  "
            "[bold green]a[/bold green]: Attach  "
            "[bold red]d[/bold red]: Kill  "
            "[bold yellow]m[/bold yellow]: Monitor  "
            "[bold magenta]e[/bold magenta]: Events  "
            "[bold white]q[/bold white]: Quit"
        )

        if self.message:
            # Show message with color based on type
            colors = {
                "info": "blue",
                "success": "green",
                "error": "red",
                "warning": "yellow",
            }
            color = colors.get(self.message_type, "white")
            footer_content = f"[{color}]{self.message}[/{color}]\n{help_text}"
        else:
            footer_content = help_text

        layout["footer"].update(Panel(footer_content, border_style="cyan"))

        return layout
