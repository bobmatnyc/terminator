"""Example usage of ProjectRegistry service.

This example demonstrates how to use ProjectRegistry for project-based
session addressing in the Terminator application.
"""

import asyncio
from pathlib import Path

from terminator.adapters.protocols import SessionState, TerminalType, UnifiedSession
from terminator.services.project_registry import ProjectRegistry


async def main() -> None:
    """Demonstrate ProjectRegistry usage."""
    # Create registry (uses ~/.terminator/projects.json by default)
    registry = ProjectRegistry()

    # Create sample sessions
    sessions = [
        UnifiedSession(
            id="tmux:mcp-ticketer:0:0",
            name="mcp-ticketer",
            terminal_type=TerminalType.TMUX,
            state=SessionState.IDLE,
            cwd="/Users/masa/Projects/mcp-ticketer",
        ),
        UnifiedSession(
            id="tmux:mcp-ticketer:0:1",
            name="mcp-ticketer-2",
            terminal_type=TerminalType.TMUX,
            state=SessionState.IDLE,
            cwd="/Users/masa/Projects/mcp-ticketer",
        ),
        UnifiedSession(
            id="iterm2:terminator:abc123",
            name="terminator",
            terminal_type=TerminalType.ITERM2,
            state=SessionState.IDLE,
            cwd="/Users/masa/Projects/terminator",
        ),
    ]

    # Register sessions
    print("Registering sessions...")
    for session in sessions:
        address = await registry.register_session(session)
        print(f"  {session.id} -> {address}")

    print()

    # List all projects
    print("Projects:")
    projects = await registry.list_projects()
    for project_name, project_sessions in projects.items():
        print(f"  {project_name}:")
        for ps in project_sessions:
            print(f"    {ps.address} -> {ps.session_id}")
            print(f"      Backend: {ps.terminal_backend}")
            print(f"      Path: {ps.project_path}")

    print()

    # Resolve addresses
    print("Resolving addresses:")
    test_addresses = [
        "@mcp-ticketer",
        "@mcp-ticketer:1",
        "@mcp-ticketer:2",
        "@terminator",
        "@nonexistent",
    ]

    for address in test_addresses:
        resolved = await registry.resolve(address)
        if resolved:
            print(f"  {address} -> {resolved}")
        else:
            print(f"  {address} -> NOT FOUND")

    print()

    # Unregister a session
    print("Unregistering mcp-ticketer:0:1...")
    await registry.unregister_session("tmux:mcp-ticketer:0:1")

    print("Projects after unregister:")
    projects = await registry.list_projects()
    for project_name, project_sessions in projects.items():
        print(f"  {project_name}:")
        for ps in project_sessions:
            print(f"    {ps.address} -> {ps.session_id}")

    print()

    # Refresh from current sessions (simulating session discovery)
    print("Refreshing from active sessions...")
    current_sessions = [sessions[0], sessions[2]]  # Only first and third
    await registry.refresh_all(current_sessions)

    print("Projects after refresh:")
    projects = await registry.list_projects()
    for project_name, project_sessions in projects.items():
        print(f"  {project_name}:")
        for ps in project_sessions:
            print(f"    {ps.address} -> {ps.session_id}")


if __name__ == "__main__":
    asyncio.run(main())
