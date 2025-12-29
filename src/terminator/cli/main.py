"""Main CLI application using Typer."""

import asyncio

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from ..container import get_container

app = typer.Typer(
    name="terminator",
    help="Remote terminal control system with LLM integration",
    no_args_is_help=False,  # Allow running without args for chat
)

console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Terminator - Interactive terminal control with LLM.

    Run without arguments to start interactive chat mode.
    """
    # If no subcommand provided, run chat by default
    if ctx.invoked_subcommand is None:
        chat()


@app.command(name="chat")
def chat(
    session: str | None = typer.Argument(
        None, help="Optional session to focus (e.g., @mcp-ticketer)"
    ),
    tui: bool = typer.Option(
        True, "--tui/--simple", help="Use TUI mode (default) or simple mode"
    ),
):
    """Start interactive chat mode (default command).

    Examples:
        terminator chat                    # Start TUI chat
        terminator chat @mcp-ticketer      # Start TUI focused on session
        terminator chat --simple           # Use simple (non-TUI) mode
    """
    asyncio.run(run_chat(initial_focus=session, use_tui=tui))


async def run_chat(initial_focus: str | None = None, use_tui: bool = True):
    """Run the interactive chatbot.

    Args:
        initial_focus: Optional session to focus on (e.g., "@mcp-ticketer")
        use_tui: If True, use TUI mode; otherwise use simple mode
    """
    # Show startup banner only for simple mode
    if not use_tui:
        console.print(
            Panel.fit(
                "[bold green]Terminator - Terminal Chatbot[/bold green]\n"
                "[dim]LLM-powered terminal control assistant[/dim]",
                title="Terminator",
            )
        )

    # Initialize container and services
    try:
        container = get_container()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(
            "\nPlease ensure TERMINATOR_OPENROUTER_API_KEY is set in environment or .env file"
        )
        raise typer.Exit(1)

    llm_service = container.get_llm_service()
    terminal_service = container.get_terminal_service()
    chatbot = container.get_chatbot()

    if not use_tui:
        console.print(
            f"[green]✓[/green] LLM initialized (OpenRouter: {llm_service.model})"
        )

    # Connect to terminals
    if not use_tui:
        console.print("[blue]Connecting to terminals...[/blue]")
    status = await terminal_service.connect_all()

    if not use_tui:
        for backend, connected in status.items():
            if connected:
                console.print(f"[green]✓[/green] {backend} connected")
            else:
                console.print(f"[yellow]○[/yellow] {backend} not available")

    if not any(status.values()):
        console.print("[red]No terminal backends available![/red]")
        raise typer.Exit(1)

    # If TUI mode, launch the TUI interface
    if use_tui:
        from .tui.chat_interface import run_chat_tui

        await run_chat_tui(chatbot, terminal_service, initial_focus=initial_focus)
        return

    # Below is simple (non-TUI) mode
    # Show available sessions with @project addresses
    sessions = await terminal_service.list_all_sessions()
    if sessions:
        # Build project address map
        project_registry = terminal_service.project_registry
        projects = await project_registry.list_projects()
        session_to_address: dict[str, str] = {}
        for project_name, project_sessions in projects.items():
            for ps in project_sessions:
                session_to_address[ps.session_id] = ps.address

        table = Table(title="Available Sessions")
        table.add_column("Address", style="cyan bold", no_wrap=True)
        table.add_column("Instance", style="magenta")
        table.add_column("Project", style="green")

        for s in sessions[:10]:  # Show first 10
            # Get project address
            address = session_to_address.get(s.id, s.id[:20] + "...")
            instance_display = f"({s.instance_type.value})"

            # Extract project name from CWD
            project_name = s.cwd.split("/")[-1] if s.cwd else s.name

            table.add_row(address, instance_display, project_name)

        if len(sessions) > 10:
            table.add_row("...", "...", f"({len(sessions) - 10} more)")

        console.print(table)
    else:
        console.print("[yellow]No sessions found[/yellow]")

    # Chat loop
    console.print("\n[bold]Chat with Terminator[/bold]")
    console.print("[dim]Type 'quit' to exit, 'clear' to reset conversation[/dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]")
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input.strip():
            continue

        if user_input.lower() == "quit":
            break

        if user_input.lower() == "clear":
            chatbot.reset_conversation()
            console.print("[dim]Conversation cleared[/dim]")
            continue

        # Get response
        console.print("[dim]Thinking...[/dim]")
        try:
            response = await chatbot.chat(user_input)
            console.print()
            console.print(
                Panel(
                    Markdown(response) if response else "[dim]No response[/dim]",
                    title="[bold green]Terminator[/bold green]",
                    border_style="green",
                )
            )
            console.print()
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    console.print("[green]Goodbye![/green]")


@app.command()
def sessions():
    """Manage terminal sessions."""
    asyncio.run(run_sessions())


async def run_sessions():
    """List all terminal sessions with @project addresses and instance types."""
    container = get_container()
    terminal_service = container.get_terminal_service()

    console.print("[blue]Connecting to terminals...[/blue]")
    status = await terminal_service.connect_all()

    if not any(status.values()):
        console.print("[red]No terminal backends available![/red]")
        raise typer.Exit(1)

    sessions = await terminal_service.list_all_sessions()

    if not sessions:
        console.print("[yellow]No sessions found[/yellow]")
        return

    # Build project address map
    project_registry = terminal_service.project_registry
    projects = await project_registry.list_projects()
    session_to_address: dict[str, str] = {}
    for project_name, project_sessions in projects.items():
        for ps in project_sessions:
            session_to_address[ps.session_id] = ps.address

    table = Table(title="Terminal Sessions")
    table.add_column("Address", style="cyan bold", no_wrap=True)
    table.add_column("Instance", style="magenta")
    table.add_column("Session ID", style="dim", no_wrap=True, max_width=35)
    table.add_column("CWD", style="green")

    for s in sessions:
        # Get project address or use truncated session ID
        address = session_to_address.get(s.id, "")
        if not address:
            # No project address, show partial session ID
            address = s.id[:20] + "..." if len(s.id) > 20 else s.id

        # Format instance type with parentheses
        instance_display = f"({s.instance_type.value})" if s.instance_type else "(unknown)"

        # Truncate session ID for display
        session_id_display = s.id[:35] + "..." if len(s.id) > 35 else s.id

        table.add_row(
            address,
            instance_display,
            session_id_display,
            s.cwd or "",
        )

    console.print(table)
    console.print(f"\n[green]Total sessions:[/green] {len(sessions)}")


@app.command()
def send(
    session_id: str = typer.Argument(..., help="Session ID to send command to"),
    command: str = typer.Argument(..., help="Command to send"),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Wait for completion"),
):
    """Send a command to a terminal session."""
    asyncio.run(run_send(session_id, command, wait))


async def run_send(session_id: str, command: str, wait: bool):
    """Send command to session."""
    container = get_container()
    terminal_service = container.get_terminal_service()

    # Connect to terminals
    await terminal_service.connect_all()

    console.print(f"[blue]Sending to {session_id}...[/blue]")
    result = await terminal_service.send_command(session_id, command, wait)

    if result.success:
        console.print(Panel(result.output, title="Output", border_style="green"))
        console.print(
            f"[dim]State: {result.state_after.value} | Time: {result.execution_time:.2f}s[/dim]"
        )
    else:
        console.print(f"[red]Error: {result.output}[/red]")
        raise typer.Exit(1)


@app.command()
def read(
    session_id: str = typer.Argument(..., help="Session ID to read from"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to read"),
):
    """Read output from a terminal session."""
    asyncio.run(run_read(session_id, lines))


async def run_read(session_id: str, lines: int):
    """Read session output."""
    container = get_container()
    terminal_service = container.get_terminal_service()

    # Connect to terminals
    await terminal_service.connect_all()

    console.print(f"[blue]Reading from {session_id}...[/blue]")
    output = await terminal_service.get_session_output(session_id, lines)

    console.print(Panel(output, title=f"Output ({lines} lines)", border_style="green"))


@app.command()
def manage():
    """Interactive session manager TUI."""
    asyncio.run(run_manage())


async def run_manage():
    """Run the interactive session manager TUI."""
    from .tui import SessionManagerTUI

    container = get_container()
    terminal_service = container.get_terminal_service()

    console.print("[blue]Connecting to terminals...[/blue]")
    status = await terminal_service.connect_all()

    if not any(status.values()):
        console.print("[red]No terminal backends available![/red]")
        console.print("Please ensure tmux or iTerm2 is running.")
        raise typer.Exit(1)

    # Show which backends are connected
    for backend, connected in status.items():
        if connected:
            console.print(f"[green]✓[/green] {backend} connected")

    # Run TUI
    tui = SessionManagerTUI(terminal_service)
    await tui.run()


@app.command()
def start(
    project_path: str = typer.Argument(..., help="Path to project directory"),
    agent: str = typer.Option(
        "shell",
        "--agent",
        "-a",
        help="Agent type (claude-code, auggie, python, node, shell)",
    ),
    name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="Custom session name (defaults to project directory name)",
    ),
):
    """Start a new coding session in a project directory."""
    asyncio.run(run_start(project_path, agent, name))


async def run_start(project_path: str, agent: str, name: str | None):
    """Start new coding session."""
    container = get_container()
    terminal_service = container.get_terminal_service()

    # Connect to terminals
    console.print("[blue]Connecting to terminal backends...[/blue]")
    status = await terminal_service.connect_all()

    if not any(status.values()):
        console.print("[red]No terminal backends available![/red]")
        console.print("Please ensure tmux or iTerm2 is running.")
        raise typer.Exit(1)

    # Show which backend will be used
    backend = "tmux" if status.get("tmux") else "iTerm2"
    console.print(f"[green]Using {backend} backend[/green]")

    # Map agent names for display
    agent_display_names = {
        "claude-code": "Claude Code",
        "auggie": "Auggie",
        "python": "Python REPL",
        "node": "Node.js REPL",
        "shell": "Shell",
    }
    agent_display = agent_display_names.get(agent, agent)

    # Get project name for display
    from pathlib import Path

    project_name = name or Path(project_path).expanduser().resolve().name

    console.print(f"[blue]Starting {agent_display} in {project_name}...[/blue]")

    try:
        # Create session
        project_address = await terminal_service.start_session(
            project_path=project_path,
            agent=agent,
            name=name,
        )

        # Success message
        console.print()
        console.print(f"[green]✓[/green] Session created: [cyan bold]{project_address}[/cyan bold] ({agent})")
        console.print()

        # Show connection instructions
        if backend == "tmux":
            console.print(f"[dim]Connect: tmux attach -t {project_name}[/dim]")
        else:
            console.print(f"[dim]Session opened in iTerm2[/dim]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
