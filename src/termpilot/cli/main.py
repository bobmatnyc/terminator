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
    name="termpilot",
    help="Remote terminal control system with LLM integration",
    no_args_is_help=False,  # Allow running without args for chat
)

console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """TermPilot - Interactive terminal control with LLM.

    Run without arguments to start interactive chat mode.
    """
    # If no subcommand provided, run chat by default
    if ctx.invoked_subcommand is None:
        chat()


@app.command(name="chat")
def chat():
    """Start interactive chat mode (default command)."""
    asyncio.run(run_chat())


async def run_chat():
    """Run the interactive chatbot."""
    console.print(
        Panel.fit(
            "[bold green]TermPilot - Terminal Chatbot[/bold green]\n"
            "[dim]LLM-powered terminal control assistant[/dim]",
            title="TermPilot",
        )
    )

    # Initialize container and services
    try:
        container = get_container()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(
            "\nPlease ensure TERMPILOT_OPENROUTER_API_KEY is set in environment or .env file"
        )
        raise typer.Exit(1)

    llm_service = container.get_llm_service()
    terminal_service = container.get_terminal_service()
    chatbot = container.get_chatbot()

    console.print(
        f"[green]✓[/green] LLM initialized (OpenRouter: {llm_service.model})"
    )

    # Connect to terminals
    console.print("[blue]Connecting to terminals...[/blue]")
    status = await terminal_service.connect_all()

    for backend, connected in status.items():
        if connected:
            console.print(f"[green]✓[/green] {backend} connected")
        else:
            console.print(f"[yellow]○[/yellow] {backend} not available")

    if not any(status.values()):
        console.print("[red]No terminal backends available![/red]")
        raise typer.Exit(1)

    # Show available sessions
    sessions = await terminal_service.list_all_sessions()
    if sessions:
        table = Table(title="Available Sessions")
        table.add_column("ID", style="cyan", no_wrap=True, max_width=40)
        table.add_column("Name", style="green")
        table.add_column("Type", style="yellow")

        for s in sessions[:10]:  # Show first 10
            table.add_row(
                s.id[:40] + "..." if len(s.id) > 40 else s.id,
                s.name,
                s.terminal_type.value,
            )

        if len(sessions) > 10:
            table.add_row("...", f"({len(sessions) - 10} more)", "...")

        console.print(table)
    else:
        console.print("[yellow]No sessions found[/yellow]")

    # Chat loop
    console.print("\n[bold]Chat with TermPilot[/bold]")
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
                    title="[bold green]TermPilot[/bold green]",
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
    """List all terminal sessions."""
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

    table = Table(title="Terminal Sessions")
    table.add_column("ID", style="cyan", no_wrap=True, max_width=50)
    table.add_column("Name", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("CWD", style="dim")

    for s in sessions:
        table.add_row(
            s.id[:50] + "..." if len(s.id) > 50 else s.id,
            s.name,
            s.terminal_type.value,
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


if __name__ == "__main__":
    app()
