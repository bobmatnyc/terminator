#!/usr/bin/env python3
"""Example: Detect instance type from terminal sessions.

Demonstrates how to use InstanceDetector to identify Claude Code, Auggie,
Python, Node, or shell sessions.
"""

import asyncio

from terminator.adapters import InstanceType
from terminator.container import get_container


async def main() -> None:
    """Detect instance types for all terminal sessions."""
    container = get_container()

    # Get services from container
    terminal_service = container.get_terminal_service()
    instance_detector = container.get_instance_detector()

    # Connect to terminals
    print("Connecting to terminal backends...")
    status = await terminal_service.connect_all()
    print(f"Connected: {status}")

    # List all sessions
    sessions = await terminal_service.list_all_sessions()
    print(f"\nFound {len(sessions)} sessions")

    # Detect instance type for each session
    for session in sessions:
        print(f"\n{'=' * 60}")
        print(f"Session: {session.name}")
        print(f"ID: {session.id}")
        print(f"Terminal: {session.terminal_type.value}")

        # Get adapter for this session
        adapter = terminal_service._get_adapter_for_session(session.id)
        if not adapter:
            print("  Instance Type: UNKNOWN (no adapter)")
            continue

        # Detect instance type
        instance_type = await instance_detector.detect_from_session(
            session, adapter, lines=100
        )

        print(f"  Instance Type: {instance_type.value}")

        # Show some context based on type
        if instance_type == InstanceType.CLAUDE_CODE:
            print("  → This is a Claude Code session!")
        elif instance_type == InstanceType.AUGGIE:
            print("  → This is an Auggie session!")
        elif instance_type == InstanceType.PYTHON:
            print("  → This is a Python REPL!")
        elif instance_type == InstanceType.NODE:
            print("  → This is a Node.js REPL!")
        elif instance_type == InstanceType.SHELL:
            print("  → This is a shell session")

        # Update session with detected type
        session.instance_type = instance_type


if __name__ == "__main__":
    asyncio.run(main())
