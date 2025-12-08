"""Verification script to test runner infrastructure."""
from rich.console import Console
from rich.panel import Panel
from server.config import Settings

console = Console()

def main():
    console.print(Panel.fit(
        "[green]TermPilot POC Runner - Hello World[/green]",
        title="TermPilot"
    ))

    # Test config loading
    settings = Settings()
    console.print(f"[blue]Default adapter:[/blue] {settings.default_adapter}")
    console.print(f"[blue]Server:[/blue] {settings.host}:{settings.port}")

    # Test imports
    console.print("\n[blue]Testing imports...[/blue]")
    from server.adapters.tmux import TmuxAdapter
    from server.adapters.iterm2 import ITerm2Adapter
    console.print("[green]✓[/green] Adapter imports successful")

    from server.container import Container
    console.print("[green]✓[/green] DI container import successful")

    console.print("\n[green]All checks passed![/green]")
