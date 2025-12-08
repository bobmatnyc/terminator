"""
POC Script Runner

Usage:
    python -m scripts.runner poc.hello_world
    python -m scripts.runner poc.tmux_explorer --interactive
"""
import sys
import asyncio
import importlib
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

console = Console()

def main():
    # Load environment
    load_dotenv()

    if len(sys.argv) < 2:
        console.print("[red]Usage: python -m scripts.runner <script_name>[/red]")
        console.print("Example: python -m scripts.runner poc.hello_world")
        sys.exit(1)

    script_name = sys.argv[1]
    script_args = sys.argv[2:]

    console.print(f"[blue]Running script:[/blue] {script_name}")

    try:
        module = importlib.import_module(f"scripts.{script_name}")

        if hasattr(module, "main"):
            if asyncio.iscoroutinefunction(module.main):
                asyncio.run(module.main(*script_args))
            else:
                module.main(*script_args)
        else:
            console.print(f"[red]Script {script_name} has no main() function[/red]")
            sys.exit(1)

    except ModuleNotFoundError as e:
        console.print(f"[red]Script not found:[/red] {script_name}")
        console.print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)

if __name__ == "__main__":
    main()
