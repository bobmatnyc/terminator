"""Interactive session management TUI using Rich."""

import asyncio
import subprocess
import sys
import termios
import tty
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ...adapters.protocols import UnifiedSession
from ...services.terminal import TerminalService


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

    def __init__(self, terminal_service: TerminalService):
        """Initialize TUI.

        Args:
            terminal_service: Terminal service for session operations
        """
        self.terminal_service = terminal_service
        self.console = Console()
        self.sessions: list[UnifiedSession] = []
        self.selected_index = 0
        self.session_to_address: dict[str, str] = {}
        self.running = True
        self.message: str = ""
        self.message_type: str = "info"  # info, success, error, warning

    async def run(self) -> None:
        """Run the interactive TUI."""
        # Load initial sessions
        await self.refresh_sessions()

        if not self.sessions:
            self.console.print("[yellow]No sessions found. Press any key to exit.[/yellow]")
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

                    # Update display
                    live.update(self._render())

                    # Small delay to prevent CPU spinning
                    await asyncio.sleep(0.05)

        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _get_key_nonblocking(self) -> str:
        """Get a key press without blocking (with 50ms timeout).

        Returns:
            Key character or empty string if no key pressed
        """
        import select

        # Check if stdin has data available (50ms timeout)
        if select.select([sys.stdin], [], [], 0.05)[0]:
            return sys.stdin.read(1)
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
            key: Key character pressed
        """
        # Arrow keys (escape sequences)
        if key == "\x1b":  # ESC
            # Check for arrow key sequence
            next_chars = sys.stdin.read(2) if select.select([sys.stdin], [], [], 0.01)[0] else ""
            if next_chars == "[A":  # Up arrow
                self.selected_index = max(0, self.selected_index - 1)
                self.message = ""
            elif next_chars == "[B":  # Down arrow
                self.selected_index = min(len(self.sessions) - 1, self.selected_index + 1)
                self.message = ""
            else:
                # Just ESC key - quit
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

    def _render(self) -> Layout:
        """Render the TUI layout.

        Returns:
            Rich Layout object
        """
        layout = Layout()
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
            table.add_column("Address", style="cyan", no_wrap=True, width=25)
            table.add_column("Instance", style="magenta", width=15)
            table.add_column("Session ID", style="dim", no_wrap=True, width=40)

            for i, session in enumerate(self.sessions):
                # Selection indicator
                indicator = ">" if i == self.selected_index else " "

                # Get address
                address = self.session_to_address.get(session.id, session.id[:20] + "...")

                # Instance type
                instance = f"({session.instance_type.value})"

                # Truncate session ID
                session_id = session.id[:40] + "..." if len(session.id) > 40 else session.id

                # Highlight selected row
                style = "bold white on blue" if i == self.selected_index else ""

                table.add_row(
                    Text(indicator, style=style),
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
            "[bold cyan]↑↓[/bold cyan]/[bold cyan]jk[/bold cyan]: Navigate  "
            "[bold green]a[/bold green]/[bold green]Enter[/bold green]: Attach  "
            "[bold red]d[/bold red]: Kill  "
            "[bold yellow]r[/bold yellow]: Refresh  "
            "[bold white]q[/bold white]/[bold white]Esc[/bold white]: Quit"
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


# Import select at module level for use in _get_key_nonblocking and _handle_key
import select
