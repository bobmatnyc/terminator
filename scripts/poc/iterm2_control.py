"""
iTerm2 Control POC - Demonstrates iTerm2 Python API capabilities.

This script demonstrates:
1. Connecting to iTerm2
2. Creating new windows/tabs/sessions
3. Sending commands to sessions
4. Reading terminal output
5. Session management (list, close)

Requirements:
- iTerm2 must be running
- Enable Python API in iTerm2: Preferences > General > Magic > Enable Python API
- Install: pip install iterm2

Usage:
    python -m scripts.runner poc.iterm2_control
    python -m scripts.runner poc.iterm2_control --demo
    python -m scripts.runner poc.iterm2_control --interactive
"""
import asyncio
import sys
from typing import Optional
from dataclasses import dataclass
from enum import Enum

import iterm2
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

console = Console()


class SessionState(Enum):
    """Terminal session state."""
    IDLE = "idle"
    RUNNING = "running"
    UNKNOWN = "unknown"


@dataclass
class SessionInfo:
    """Information about an iTerm2 session."""
    session_id: str
    name: str
    tab_id: str
    window_id: str
    columns: int
    rows: int


class ITerm2Controller:
    """
    Controller for iTerm2 terminal operations.

    Wraps the iterm2 Python API with a simpler interface
    for common terminal control operations.
    """

    def __init__(self, connection: iterm2.Connection):
        self.connection = connection
        self._app: Optional[iterm2.App] = None

    async def get_app(self) -> iterm2.App:
        """Get or cache the iTerm2 app instance."""
        if self._app is None:
            self._app = await iterm2.async_get_app(self.connection)
        return self._app

    async def list_sessions(self) -> list[SessionInfo]:
        """List all sessions across all windows and tabs."""
        app = await self.get_app()
        sessions = []

        for window in app.windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    sessions.append(SessionInfo(
                        session_id=session.session_id,
                        name=session.name or "Unnamed",
                        tab_id=tab.tab_id,
                        window_id=window.window_id,
                        columns=session.grid_size.width,
                        rows=session.grid_size.height,
                    ))

        return sessions

    async def create_window(self, profile: str = None) -> tuple[str, str]:
        """
        Create a new iTerm2 window.

        Returns:
            Tuple of (window_id, session_id)
        """
        app = await self.get_app()
        window = await iterm2.Window.async_create(self.connection, profile=profile)

        if window is None:
            raise RuntimeError("Failed to create window")

        # Get the session in the new window's current tab
        session = window.current_tab.current_session
        return window.window_id, session.session_id

    async def create_tab(self, window_id: str = None, profile: str = None) -> tuple[str, str]:
        """
        Create a new tab in a window.

        Args:
            window_id: Target window ID (uses current window if None)
            profile: iTerm2 profile name

        Returns:
            Tuple of (tab_id, session_id)
        """
        app = await self.get_app()

        if window_id:
            window = app.get_window_by_id(window_id)
        else:
            window = app.current_window

        if window is None:
            raise RuntimeError("No window available")

        tab = await window.async_create_tab(profile=profile)
        session = tab.current_session
        return tab.tab_id, session.session_id

    async def split_pane(
        self,
        session_id: str,
        vertical: bool = True,
        profile: str = None
    ) -> str:
        """
        Split an existing session into a new pane.

        Args:
            session_id: Session to split
            vertical: True for vertical split, False for horizontal
            profile: iTerm2 profile name

        Returns:
            New session ID
        """
        app = await self.get_app()
        session = app.get_session_by_id(session_id)

        if session is None:
            raise RuntimeError(f"Session not found: {session_id}")

        new_session = await session.async_split_pane(
            vertical=vertical,
            profile=profile
        )
        return new_session.session_id

    async def send_text(
        self,
        session_id: str,
        text: str,
        newline: bool = True
    ) -> bool:
        """
        Send text to a session.

        Args:
            session_id: Target session
            text: Text to send
            newline: Whether to append newline (simulates pressing Enter)

        Returns:
            True if successful
        """
        app = await self.get_app()
        session = app.get_session_by_id(session_id)

        if session is None:
            raise RuntimeError(f"Session not found: {session_id}")

        if newline:
            text = text + "\n"

        await session.async_send_text(text)
        return True

    async def get_screen_contents(
        self,
        session_id: str,
        lines: int = 50
    ) -> str:
        """
        Get the screen contents from a session.

        Args:
            session_id: Target session
            lines: Number of lines to retrieve

        Returns:
            Screen content as string
        """
        app = await self.get_app()
        session = app.get_session_by_id(session_id)

        if session is None:
            raise RuntimeError(f"Session not found: {session_id}")

        # Get screen contents
        contents = await session.async_get_screen_contents()

        # Extract text from screen lines
        output_lines = []
        line_count = min(lines, contents.number_of_lines)

        for i in range(line_count):
            line = contents.line(i)
            output_lines.append(line.string)

        return "\n".join(output_lines)

    async def get_screen_streamed(
        self,
        session_id: str,
        callback,
        duration: float = 5.0
    ):
        """
        Stream screen updates from a session.

        Args:
            session_id: Target session
            callback: Async function called with screen contents
            duration: How long to stream (seconds)
        """
        app = await self.get_app()
        session = app.get_session_by_id(session_id)

        if session is None:
            raise RuntimeError(f"Session not found: {session_id}")

        async with iterm2.ScreenStreamer(self.connection, session.session_id) as streamer:
            start_time = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start_time) < duration:
                update = await asyncio.wait_for(
                    streamer.async_get(),
                    timeout=1.0
                )
                if update:
                    await callback(update)

    async def close_session(self, session_id: str, force: bool = False) -> bool:
        """
        Close a session.

        Args:
            session_id: Session to close
            force: Force close without confirmation

        Returns:
            True if successful
        """
        app = await self.get_app()
        session = app.get_session_by_id(session_id)

        if session is None:
            return False

        await session.async_close(force=force)
        return True

    async def set_session_name(self, session_id: str, name: str) -> bool:
        """Set the name of a session."""
        app = await self.get_app()
        session = app.get_session_by_id(session_id)

        if session is None:
            return False

        await session.async_set_name(name)
        return True

    async def get_session_variable(
        self,
        session_id: str,
        variable: str
    ) -> Optional[str]:
        """
        Get a session variable value.

        Common variables:
        - path: Current working directory
        - jobName: Current job name
        - hostname: Host name
        - username: User name
        """
        app = await self.get_app()
        session = app.get_session_by_id(session_id)

        if session is None:
            return None

        return await session.async_get_variable(variable)


async def demo_basic_operations(connection: iterm2.Connection):
    """Demonstrate basic iTerm2 operations."""
    controller = ITerm2Controller(connection)

    console.print(Panel.fit(
        "[bold green]iTerm2 Control POC - Basic Operations Demo[/bold green]",
        title="TermPilot"
    ))

    # 1. List existing sessions
    console.print("\n[blue]1. Listing existing sessions...[/blue]")
    sessions = await controller.list_sessions()

    table = Table(title="Current Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Size", style="yellow")

    for s in sessions:
        table.add_row(
            s.session_id[:20] + "...",
            s.name,
            f"{s.columns}x{s.rows}"
        )

    console.print(table)

    # 2. Create a new window
    console.print("\n[blue]2. Creating new window...[/blue]")
    window_id, session_id = await controller.create_window()
    console.print(f"[green]Created window:[/green] {window_id[:20]}...")
    console.print(f"[green]Session ID:[/green] {session_id[:20]}...")

    # Name the session
    await controller.set_session_name(session_id, "TermPilot-Demo")

    # 3. Send a command
    console.print("\n[blue]3. Sending command: echo 'Hello from TermPilot!'[/blue]")
    await controller.send_text(session_id, "echo 'Hello from TermPilot!'")

    # Wait for command to complete
    await asyncio.sleep(0.5)

    # 4. Read output
    console.print("\n[blue]4. Reading screen contents...[/blue]")
    output = await controller.get_screen_contents(session_id, lines=10)
    console.print(Panel(output, title="Screen Output", border_style="green"))

    # 5. Send another command - show current directory
    console.print("\n[blue]5. Sending command: pwd[/blue]")
    await controller.send_text(session_id, "pwd")
    await asyncio.sleep(0.3)

    output = await controller.get_screen_contents(session_id, lines=15)
    console.print(Panel(output, title="Screen Output", border_style="green"))

    # 6. Create a split pane
    console.print("\n[blue]6. Creating vertical split pane...[/blue]")
    new_session_id = await controller.split_pane(session_id, vertical=True)
    console.print(f"[green]New pane session:[/green] {new_session_id[:20]}...")

    # Send command to new pane
    await controller.send_text(new_session_id, "echo 'This is the split pane!'")
    await asyncio.sleep(0.3)

    # 7. Get session variable (working directory)
    console.print("\n[blue]7. Getting session variables...[/blue]")
    cwd = await controller.get_session_variable(session_id, "path")
    console.print(f"[green]Working directory:[/green] {cwd}")

    # Cleanup - auto-close demo window after brief pause
    console.print("\n[yellow]Demo complete![/yellow]")
    console.print("[dim]Closing demo window in 2 seconds...[/dim]")
    await asyncio.sleep(2)

    # Close the new pane first, then the original session
    await controller.close_session(new_session_id, force=True)
    await controller.close_session(session_id, force=True)
    console.print("[green]Demo window closed.[/green]")


async def interactive_mode(connection: iterm2.Connection):
    """Interactive mode for exploring iTerm2 control."""
    controller = ITerm2Controller(connection)

    console.print(Panel.fit(
        "[bold green]iTerm2 Control POC - Interactive Mode[/bold green]",
        title="TermPilot"
    ))

    # Get or create a session to work with
    sessions = await controller.list_sessions()

    if not sessions:
        console.print("[yellow]No sessions found. Creating one...[/yellow]")
        _, session_id = await controller.create_window()
    else:
        # Show sessions and let user pick
        table = Table(title="Available Sessions")
        table.add_column("#", style="cyan")
        table.add_column("Session ID", style="cyan")
        table.add_column("Name", style="green")

        for i, s in enumerate(sessions):
            table.add_row(str(i), s.session_id[:20] + "...", s.name)

        console.print(table)

        choice = Prompt.ask(
            "Select session number (or 'new' for new window)",
            default="0"
        )

        if choice.lower() == "new":
            _, session_id = await controller.create_window()
        else:
            session_id = sessions[int(choice)].session_id

    console.print(f"\n[green]Working with session:[/green] {session_id[:30]}...")

    # Interactive command loop
    while True:
        console.print("\n[bold]Commands:[/bold]")
        console.print("  [cyan]send <text>[/cyan]  - Send text to terminal")
        console.print("  [cyan]read[/cyan]         - Read screen contents")
        console.print("  [cyan]split[/cyan]        - Create split pane")
        console.print("  [cyan]list[/cyan]         - List all sessions")
        console.print("  [cyan]switch <n>[/cyan]   - Switch to session n")
        console.print("  [cyan]quit[/cyan]         - Exit")

        cmd = Prompt.ask("\nCommand")

        if cmd.lower() == "quit":
            break
        elif cmd.lower() == "read":
            output = await controller.get_screen_contents(session_id, lines=20)
            console.print(Panel(output, title="Screen", border_style="green"))
        elif cmd.lower().startswith("send "):
            text = cmd[5:]
            await controller.send_text(session_id, text)
            console.print(f"[green]Sent:[/green] {text}")
        elif cmd.lower() == "split":
            new_id = await controller.split_pane(session_id, vertical=True)
            console.print(f"[green]Created pane:[/green] {new_id[:20]}...")
        elif cmd.lower() == "list":
            sessions = await controller.list_sessions()
            for i, s in enumerate(sessions):
                marker = "→" if s.session_id == session_id else " "
                console.print(f"  {marker} [{i}] {s.name} ({s.session_id[:15]}...)")
        elif cmd.lower().startswith("switch "):
            idx = int(cmd[7:])
            sessions = await controller.list_sessions()
            if 0 <= idx < len(sessions):
                session_id = sessions[idx].session_id
                console.print(f"[green]Switched to:[/green] {sessions[idx].name}")
            else:
                console.print("[red]Invalid session index[/red]")
        else:
            console.print("[yellow]Unknown command[/yellow]")

    console.print("[green]Goodbye![/green]")


async def run_poc(mode: str = "info"):
    """
    Main entry point - connects to iTerm2 and runs the POC.

    Args:
        mode: "info" for session list, "demo" for full demo, "interactive" for REPL
    """
    try:
        connection = await iterm2.Connection.async_create()

        if mode == "demo":
            await demo_basic_operations(connection)
        elif mode == "interactive":
            await interactive_mode(connection)
        else:
            # Default: just list sessions
            controller = ITerm2Controller(connection)

            console.print(Panel.fit(
                "[bold green]iTerm2 Control POC[/bold green]",
                title="TermPilot"
            ))

            sessions = await controller.list_sessions()

            table = Table(title="iTerm2 Sessions")
            table.add_column("Session ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Window", style="yellow")
            table.add_column("Size", style="blue")

            for s in sessions:
                table.add_row(
                    s.session_id[:25] + "...",
                    s.name,
                    s.window_id[:15] + "...",
                    f"{s.columns}x{s.rows}"
                )

            console.print(table)
            console.print(f"\n[green]Total sessions:[/green] {len(sessions)}")
            console.print("\n[dim]Run with --demo for full demonstration[/dim]")
            console.print("[dim]Run with --interactive for interactive mode[/dim]")

    except Exception as e:
        if "not running" in str(e).lower():
            console.print("[red]Error: iTerm2 is not running![/red]")
            console.print("Please start iTerm2 and try again.")
            sys.exit(1)
        console.print(f"[red]Error connecting to iTerm2:[/red] {e}")
        console.print("\nMake sure:")
        console.print("  1. iTerm2 is running")
        console.print("  2. Python API is enabled: Preferences > General > Magic > Enable Python API")
        sys.exit(1)


def main(*args):
    """Entry point for the POC runner."""
    mode = "info"

    if "--demo" in args:
        mode = "demo"
    elif "--interactive" in args:
        mode = "interactive"

    asyncio.run(run_poc(mode))


if __name__ == "__main__":
    main(*sys.argv[1:])
