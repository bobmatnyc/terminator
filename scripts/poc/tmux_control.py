"""
tmux Control POC - Demonstrates libtmux capabilities.

This script demonstrates:
1. Connecting to tmux server
2. Creating/managing sessions, windows, and panes
3. Sending commands to panes
4. Reading pane output
5. Session management (list, kill)

Requirements:
- tmux must be installed and running (or will be started)
- Install: pip install libtmux

Usage:
    python -m scripts.runner poc.tmux_control
    python -m scripts.runner poc.tmux_control --demo
    python -m scripts.runner poc.tmux_control --interactive
"""
import sys
import time
from typing import Optional
from dataclasses import dataclass
from enum import Enum

import libtmux
from libtmux.constants import PaneDirection
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

console = Console()


class PaneState(Enum):
    """Terminal pane state."""
    IDLE = "idle"
    RUNNING = "running"
    UNKNOWN = "unknown"


@dataclass
class TmuxSessionInfo:
    """Information about a tmux session."""
    session_id: str
    session_name: str
    window_count: int
    created: str
    attached: bool


@dataclass
class TmuxWindowInfo:
    """Information about a tmux window."""
    window_id: str
    window_name: str
    window_index: int
    pane_count: int
    active: bool


@dataclass
class TmuxPaneInfo:
    """Information about a tmux pane."""
    pane_id: str
    pane_index: int
    width: int
    height: int
    current_path: str
    active: bool


class TmuxController:
    """
    Controller for tmux terminal operations.

    Wraps libtmux with a simpler interface for common
    terminal control operations.
    """

    def __init__(self):
        self.server: Optional[libtmux.Server] = None

    def connect(self) -> bool:
        """Connect to the tmux server."""
        try:
            self.server = libtmux.Server()
            # Test connection by listing sessions
            _ = self.server.sessions
            return True
        except libtmux.exc.LibTmuxException as e:
            console.print(f"[yellow]Note: {e}[/yellow]")
            return False

    def list_sessions(self) -> list[TmuxSessionInfo]:
        """List all tmux sessions."""
        if not self.server:
            return []

        sessions = []
        for session in self.server.sessions:
            sessions.append(TmuxSessionInfo(
                session_id=session.session_id,
                session_name=session.session_name,
                window_count=len(session.windows),
                created=session.session_created or "unknown",
                attached=session.session_attached == "1",
            ))
        return sessions

    def create_session(
        self,
        name: str,
        working_dir: Optional[str] = None,
        attach: bool = False
    ) -> tuple[str, str, str]:
        """
        Create a new tmux session.

        Args:
            name: Session name
            working_dir: Starting directory
            attach: Whether to attach to the session

        Returns:
            Tuple of (session_id, window_id, pane_id)
        """
        if not self.server:
            raise RuntimeError("Not connected to tmux server")

        kwargs = {
            "session_name": name,
            "attach": attach,
        }
        if working_dir:
            kwargs["start_directory"] = working_dir

        session = self.server.new_session(**kwargs)
        window = session.active_window
        pane = window.active_pane

        return session.session_id, window.window_id, pane.pane_id

    def kill_session(self, session_name: str) -> bool:
        """Kill a tmux session by name."""
        if not self.server:
            return False

        session = self.server.sessions.get(session_name=session_name)
        if session:
            session.kill()
            return True
        return False

    def get_session(self, session_name: str) -> Optional[libtmux.Session]:
        """Get a session by name."""
        if not self.server:
            return None
        try:
            return self.server.sessions.get(session_name=session_name)
        except Exception:
            return None

    def list_windows(self, session_name: str) -> list[TmuxWindowInfo]:
        """List all windows in a session."""
        session = self.get_session(session_name)
        if not session:
            return []

        windows = []
        for window in session.windows:
            windows.append(TmuxWindowInfo(
                window_id=window.window_id,
                window_name=window.window_name,
                window_index=int(window.window_index),
                pane_count=len(window.panes),
                active=window == session.active_window,
            ))
        return windows

    def create_window(
        self,
        session_name: str,
        window_name: str,
        working_dir: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Create a new window in a session.

        Returns:
            Tuple of (window_id, pane_id)
        """
        session = self.get_session(session_name)
        if not session:
            raise RuntimeError(f"Session not found: {session_name}")

        kwargs = {"window_name": window_name}
        if working_dir:
            kwargs["start_directory"] = working_dir

        window = session.new_window(**kwargs)
        pane = window.active_pane

        return window.window_id, pane.pane_id

    def list_panes(self, session_name: str, window_index: int = 0) -> list[TmuxPaneInfo]:
        """List all panes in a window."""
        session = self.get_session(session_name)
        if not session:
            return []

        window = session.windows.get(window_index=str(window_index))
        if not window:
            return []

        panes = []
        for pane in window.panes:
            panes.append(TmuxPaneInfo(
                pane_id=pane.pane_id,
                pane_index=int(pane.pane_index),
                width=int(pane.pane_width),
                height=int(pane.pane_height),
                current_path=pane.pane_current_path or "",
                active=pane == window.active_pane,
            ))
        return panes

    def split_pane(
        self,
        session_name: str,
        window_index: int = 0,
        vertical: bool = True,
        working_dir: Optional[str] = None
    ) -> str:
        """
        Split the active pane in a window.

        Args:
            session_name: Target session
            window_index: Target window index
            vertical: True for vertical split (side-by-side), False for horizontal
            working_dir: Starting directory for new pane

        Returns:
            New pane ID
        """
        session = self.get_session(session_name)
        if not session:
            raise RuntimeError(f"Session not found: {session_name}")

        window = session.windows.get(window_index=str(window_index))
        if not window:
            raise RuntimeError(f"Window not found: {window_index}")

        pane = window.active_pane
        # Use PaneDirection: Right for vertical (side-by-side), Below for horizontal
        direction = PaneDirection.Right if vertical else PaneDirection.Below
        kwargs = {"direction": direction}
        if working_dir:
            kwargs["start_directory"] = working_dir

        new_pane = pane.split(**kwargs)
        return new_pane.pane_id

    def send_keys(
        self,
        session_name: str,
        keys: str,
        window_index: int = 0,
        pane_index: int = 0,
        enter: bool = True
    ) -> bool:
        """
        Send keys/text to a pane.

        Args:
            session_name: Target session
            keys: Text or keys to send
            window_index: Target window index
            pane_index: Target pane index
            enter: Whether to press Enter after keys

        Returns:
            True if successful
        """
        session = self.get_session(session_name)
        if not session:
            return False

        window = session.windows.get(window_index=str(window_index))
        if not window:
            return False

        pane = window.panes.get(pane_index=str(pane_index))
        if not pane:
            return False

        pane.send_keys(keys, enter=enter)
        return True

    def capture_pane(
        self,
        session_name: str,
        window_index: int = 0,
        pane_index: int = 0,
        lines: int = 50
    ) -> str:
        """
        Capture the content of a pane.

        Args:
            session_name: Target session
            window_index: Target window index
            pane_index: Target pane index
            lines: Number of lines to capture (negative for history)

        Returns:
            Pane content as string
        """
        session = self.get_session(session_name)
        if not session:
            return ""

        window = session.windows.get(window_index=str(window_index))
        if not window:
            return ""

        pane = window.panes.get(pane_index=str(pane_index))
        if not pane:
            return ""

        # Capture pane content
        output = pane.capture_pane()
        if isinstance(output, list):
            output = "\n".join(output)

        return output

    def get_pane_cwd(
        self,
        session_name: str,
        window_index: int = 0,
        pane_index: int = 0
    ) -> str:
        """Get the current working directory of a pane."""
        session = self.get_session(session_name)
        if not session:
            return ""

        window = session.windows.get(window_index=str(window_index))
        if not window:
            return ""

        pane = window.panes.get(pane_index=str(pane_index))
        if not pane:
            return ""

        return pane.pane_current_path or ""

    def resize_pane(
        self,
        session_name: str,
        window_index: int = 0,
        pane_index: int = 0,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> bool:
        """Resize a pane."""
        session = self.get_session(session_name)
        if not session:
            return False

        window = session.windows.get(window_index=str(window_index))
        if not window:
            return False

        pane = window.panes.get(pane_index=str(pane_index))
        if not pane:
            return False

        if width:
            pane.resize(width=width)
        if height:
            pane.resize(height=height)

        return True


def demo_basic_operations():
    """Demonstrate basic tmux operations."""
    controller = TmuxController()

    console.print(Panel.fit(
        "[bold green]tmux Control POC - Basic Operations Demo[/bold green]",
        title="Terminator"
    ))

    # 1. Connect to tmux
    console.print("\n[blue]1. Connecting to tmux server...[/blue]")
    if not controller.connect():
        console.print("[yellow]No existing tmux server. Will create one.[/yellow]")
        controller.server = libtmux.Server()

    # 2. List existing sessions
    console.print("\n[blue]2. Listing existing sessions...[/blue]")
    sessions = controller.list_sessions()

    if sessions:
        table = Table(title="Current Sessions")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="dim")
        table.add_column("Windows", style="yellow")
        table.add_column("Attached", style="green")

        for s in sessions:
            table.add_row(
                s.session_name,
                s.session_id,
                str(s.window_count),
                "✓" if s.attached else ""
            )
        console.print(table)
    else:
        console.print("[dim]No existing sessions[/dim]")

    # 3. Create a demo session
    demo_session_name = "terminator-demo"
    console.print(f"\n[blue]3. Creating session: {demo_session_name}[/blue]")

    # Kill existing demo session if present
    if controller.get_session(demo_session_name):
        controller.kill_session(demo_session_name)
        console.print("[dim]Removed existing demo session[/dim]")

    session_id, window_id, pane_id = controller.create_session(demo_session_name)
    console.print(f"[green]Created session:[/green] {session_id}")
    console.print(f"[green]Window ID:[/green] {window_id}")
    console.print(f"[green]Pane ID:[/green] {pane_id}")

    # 4. Send a command
    console.print("\n[blue]4. Sending command: echo 'Hello from Terminator!'[/blue]")
    controller.send_keys(demo_session_name, "echo 'Hello from Terminator!'")

    # Wait for command to complete
    time.sleep(0.5)

    # 5. Capture output
    console.print("\n[blue]5. Capturing pane output...[/blue]")
    output = controller.capture_pane(demo_session_name)
    console.print(Panel(output, title="Pane Output", border_style="green"))

    # 6. Create a new window
    console.print("\n[blue]6. Creating new window: 'editor'[/blue]")
    new_window_id, new_pane_id = controller.create_window(
        demo_session_name,
        window_name="editor"
    )
    console.print(f"[green]New window:[/green] {new_window_id}")

    # List windows
    windows = controller.list_windows(demo_session_name)
    table = Table(title="Session Windows")
    table.add_column("Index", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Panes", style="yellow")
    table.add_column("Active", style="blue")

    for w in windows:
        table.add_row(
            str(w.window_index),
            w.window_name,
            str(w.pane_count),
            "→" if w.active else ""
        )
    console.print(table)

    # 7. Split pane
    console.print("\n[blue]7. Splitting pane vertically...[/blue]")
    split_pane_id = controller.split_pane(demo_session_name, window_index=1, vertical=True)
    console.print(f"[green]New pane:[/green] {split_pane_id}")

    # Send command to new pane
    controller.send_keys(demo_session_name, "echo 'This is the split pane!'", window_index=1, pane_index=1)
    time.sleep(0.3)

    # List panes
    panes = controller.list_panes(demo_session_name, window_index=1)
    table = Table(title="Window Panes")
    table.add_column("Index", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Size", style="yellow")
    table.add_column("Active", style="blue")

    for p in panes:
        table.add_row(
            str(p.pane_index),
            p.pane_id,
            f"{p.width}x{p.height}",
            "→" if p.active else ""
        )
    console.print(table)

    # 8. Get current working directory
    console.print("\n[blue]8. Getting pane working directory...[/blue]")
    cwd = controller.get_pane_cwd(demo_session_name, window_index=0)
    console.print(f"[green]Working directory:[/green] {cwd}")

    # 9. Capture both panes
    console.print("\n[blue]9. Capturing output from split panes...[/blue]")

    for pane_idx in range(2):
        output = controller.capture_pane(demo_session_name, window_index=1, pane_index=pane_idx)
        console.print(Panel(
            output or "[dim]<empty>[/dim]",
            title=f"Pane {pane_idx}",
            border_style="green"
        ))

    # Cleanup
    console.print("\n[yellow]Demo complete![/yellow]")
    console.print("[dim]Cleaning up demo session in 2 seconds...[/dim]")
    time.sleep(2)

    controller.kill_session(demo_session_name)
    console.print(f"[green]Killed session:[/green] {demo_session_name}")


def interactive_mode():
    """Interactive mode for exploring tmux control."""
    controller = TmuxController()

    console.print(Panel.fit(
        "[bold green]tmux Control POC - Interactive Mode[/bold green]",
        title="Terminator"
    ))

    # Connect
    if not controller.connect():
        console.print("[yellow]No tmux server running. Creating one...[/yellow]")
        controller.server = libtmux.Server()

    # Show sessions
    sessions = controller.list_sessions()
    if sessions:
        table = Table(title="Available Sessions")
        table.add_column("#", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Windows", style="yellow")

        for i, s in enumerate(sessions):
            table.add_row(str(i), s.session_name, str(s.window_count))
        console.print(table)

    # Select or create session
    choice = Prompt.ask(
        "Select session number, or enter name to create new",
        default="terminator-interactive"
    )

    if choice.isdigit() and sessions:
        session_name = sessions[int(choice)].session_name
    else:
        session_name = choice
        if not controller.get_session(session_name):
            controller.create_session(session_name)
            console.print(f"[green]Created session:[/green] {session_name}")

    console.print(f"\n[green]Working with session:[/green] {session_name}")

    # Track current window/pane
    current_window = 0
    current_pane = 0

    # Interactive loop
    while True:
        console.print(f"\n[dim]Session: {session_name} | Window: {current_window} | Pane: {current_pane}[/dim]")
        console.print("[bold]Commands:[/bold]")
        console.print("  [cyan]send <text>[/cyan]   - Send text to pane")
        console.print("  [cyan]read[/cyan]          - Read pane output")
        console.print("  [cyan]split [v|h][/cyan]   - Split pane (v=vertical, h=horizontal)")
        console.print("  [cyan]window <name>[/cyan] - Create new window")
        console.print("  [cyan]windows[/cyan]       - List windows")
        console.print("  [cyan]panes[/cyan]         - List panes")
        console.print("  [cyan]select w p[/cyan]    - Select window w, pane p")
        console.print("  [cyan]sessions[/cyan]      - List all sessions")
        console.print("  [cyan]quit[/cyan]          - Exit (keeps session)")
        console.print("  [cyan]kill[/cyan]          - Kill session and exit")

        try:
            cmd = Prompt.ask("\nCommand")
        except EOFError:
            break

        if cmd.lower() == "quit":
            console.print(f"[blue]Session '{session_name}' left running.[/blue]")
            console.print(f"[dim]Attach with: tmux attach -t {session_name}[/dim]")
            break

        elif cmd.lower() == "kill":
            controller.kill_session(session_name)
            console.print(f"[green]Killed session:[/green] {session_name}")
            break

        elif cmd.lower() == "read":
            output = controller.capture_pane(session_name, current_window, current_pane)
            console.print(Panel(output or "[dim]<empty>[/dim]", title="Output", border_style="green"))

        elif cmd.lower().startswith("send "):
            text = cmd[5:]
            controller.send_keys(session_name, text, current_window, current_pane)
            console.print(f"[green]Sent:[/green] {text}")

        elif cmd.lower().startswith("split"):
            parts = cmd.split()
            vertical = True
            if len(parts) > 1 and parts[1].lower() == "h":
                vertical = False

            new_pane_id = controller.split_pane(
                session_name,
                window_index=current_window,
                vertical=vertical
            )
            console.print(f"[green]Created pane:[/green] {new_pane_id}")

        elif cmd.lower().startswith("window "):
            name = cmd[7:].strip()
            window_id, pane_id = controller.create_window(session_name, name)
            console.print(f"[green]Created window:[/green] {name}")

        elif cmd.lower() == "windows":
            windows = controller.list_windows(session_name)
            for w in windows:
                marker = "→" if w.window_index == current_window else " "
                console.print(f"  {marker} [{w.window_index}] {w.window_name} ({w.pane_count} panes)")

        elif cmd.lower() == "panes":
            panes = controller.list_panes(session_name, current_window)
            for p in panes:
                marker = "→" if p.pane_index == current_pane else " "
                console.print(f"  {marker} [{p.pane_index}] {p.width}x{p.height} - {p.current_path}")

        elif cmd.lower().startswith("select "):
            parts = cmd.split()
            if len(parts) >= 3:
                current_window = int(parts[1])
                current_pane = int(parts[2])
                console.print(f"[green]Selected:[/green] window {current_window}, pane {current_pane}")
            elif len(parts) == 2:
                current_window = int(parts[1])
                current_pane = 0
                console.print(f"[green]Selected:[/green] window {current_window}")

        elif cmd.lower() == "sessions":
            sessions = controller.list_sessions()
            for s in sessions:
                marker = "→" if s.session_name == session_name else " "
                console.print(f"  {marker} {s.session_name} ({s.window_count} windows)")

        else:
            console.print("[yellow]Unknown command[/yellow]")

    console.print("[green]Goodbye![/green]")


def run_poc(mode: str = "info"):
    """
    Main entry point.

    Args:
        mode: "info" for session list, "demo" for full demo, "interactive" for REPL
    """
    controller = TmuxController()

    if mode == "demo":
        demo_basic_operations()
    elif mode == "interactive":
        interactive_mode()
    else:
        # Default: just list sessions
        console.print(Panel.fit(
            "[bold green]tmux Control POC[/bold green]",
            title="Terminator"
        ))

        console.print("\n[blue]Connecting to tmux server...[/blue]")
        if not controller.connect():
            console.print("[yellow]No tmux server running.[/yellow]")
            console.print("[dim]Start tmux first: tmux new-session -d -s main[/dim]")
            return

        sessions = controller.list_sessions()

        table = Table(title="tmux Sessions")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="dim")
        table.add_column("Windows", style="yellow")
        table.add_column("Attached", style="green")

        for s in sessions:
            table.add_row(
                s.session_name,
                s.session_id,
                str(s.window_count),
                "✓" if s.attached else ""
            )

        console.print(table)
        console.print(f"\n[green]Total sessions:[/green] {len(sessions)}")
        console.print("\n[dim]Run with --demo for full demonstration[/dim]")
        console.print("[dim]Run with --interactive for interactive mode[/dim]")


def main(*args):
    """Entry point for the POC runner."""
    mode = "info"

    if "--demo" in args:
        mode = "demo"
    elif "--interactive" in args:
        mode = "interactive"

    run_poc(mode)


if __name__ == "__main__":
    main(*sys.argv[1:])
