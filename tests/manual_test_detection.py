#!/usr/bin/env python3
"""Manual test script for instance type detection.

Run this to verify detection works correctly on sample outputs.
"""

import asyncio

from terminator.adapters import InstanceType
from terminator.services import InstanceDetector


async def test_detection_samples():
    """Test detection on sample screen outputs."""
    detector = InstanceDetector()

    samples = [
        # Claude Code samples
        (
            "Claude Code\nClaude Opus 4.5\nclaude-code>",
            InstanceType.CLAUDE_CODE,
            "Claude Code banner",
        ),
        (
            "╭─ Claude Code Session ─╮\n│ Working on task...    │\n╰───────────────────────╯",
            InstanceType.CLAUDE_CODE,
            "Claude Code UI box",
        ),
        # Auggie samples
        (
            "Augment Code Assistant\naugment> help",
            InstanceType.AUGGIE,
            "Auggie prompt",
        ),
        # Python samples
        (
            "Python 3.12.0\n>>> import sys\n>>> sys.version\n'3.12.0'\n>>>",
            InstanceType.PYTHON,
            "Python REPL",
        ),
        (
            "In [1]: import numpy as np\nIn [2]: np.array([1, 2, 3])\nOut[2]: array([1, 2, 3])",
            InstanceType.PYTHON,
            "IPython",
        ),
        # Node.js samples
        (
            "Welcome to Node.js v20.10.0\n> console.log('hello')\nhello\n>",
            InstanceType.NODE,
            "Node.js REPL",
        ),
        # Shell samples
        (
            "user@host:~$ ls -la\ntotal 24\nuser@host:~$",
            InstanceType.SHELL,
            "Bash shell",
        ),
        (
            "~ ❯ echo $SHELL\n/bin/zsh\n~ ❯",
            InstanceType.SHELL,
            "Zsh shell",
        ),
        # Unknown samples
        (
            "Random output without recognizable patterns",
            InstanceType.UNKNOWN,
            "Unknown output",
        ),
        ("", InstanceType.UNKNOWN, "Empty output"),
    ]

    print("=" * 70)
    print("Instance Type Detection - Manual Test")
    print("=" * 70)

    passed = 0
    failed = 0

    for screen_content, expected_type, description in samples:
        result = await detector.detect_type("test", screen_content)

        status = "✓ PASS" if result == expected_type else "✗ FAIL"
        if result == expected_type:
            passed += 1
        else:
            failed += 1

        print(f"\n{status} | {description}")
        print(f"  Expected: {expected_type.value}")
        print(f"  Got:      {result.value}")

        if result != expected_type:
            print(f"  Content preview: {screen_content[:80]}")

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(samples)} tests")
    print("=" * 70)

    return failed == 0


async def test_priority_ordering():
    """Test that priority ordering works correctly."""
    detector = InstanceDetector()

    # Test case where Claude Code prompt appears in shell output
    # Should detect Claude Code (higher priority) not Shell
    content = """
    user@host:~$ claude-code
    Welcome to Claude Code
    Claude Opus 4.5
    claude-code>
    """

    result = await detector.detect_type("test", content)

    print("\n" + "=" * 70)
    print("Priority Ordering Test")
    print("=" * 70)
    print(f"Content: Shell launches Claude Code")
    print(f"Expected: {InstanceType.CLAUDE_CODE.value} (higher priority)")
    print(f"Got:      {result.value}")

    if result == InstanceType.CLAUDE_CODE:
        print("✓ PASS - Correctly prioritized Claude Code over Shell")
        return True
    else:
        print("✗ FAIL - Incorrect priority handling")
        return False


async def test_custom_patterns():
    """Test adding custom patterns."""
    detector = InstanceDetector()

    # Add custom pattern for vim
    detector.add_pattern(
        instance_type=InstanceType.SHELL,
        pattern=r"VIM - Vi IMproved",
        priority=60,
    )

    content = """
    VIM - Vi IMproved
    version 9.0
    ~
    ~
    """

    result = await detector.detect_type("test", content)

    print("\n" + "=" * 70)
    print("Custom Pattern Test")
    print("=" * 70)
    print(f"Added custom pattern: 'VIM - Vi IMproved'")
    print(f"Expected: {InstanceType.SHELL.value}")
    print(f"Got:      {result.value}")

    if result == InstanceType.SHELL:
        print("✓ PASS - Custom pattern works")
        return True
    else:
        print("✗ FAIL - Custom pattern not detected")
        return False


async def main():
    """Run all manual tests."""
    print("\n🔍 Instance Type Detection Manual Tests\n")

    results = []

    # Test 1: Sample detection
    results.append(await test_detection_samples())

    # Test 2: Priority ordering
    results.append(await test_priority_ordering())

    # Test 3: Custom patterns
    results.append(await test_custom_patterns())

    print("\n" + "=" * 70)
    if all(results):
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 70 + "\n")

    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
