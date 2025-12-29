"""Unit tests for InstanceDetector service."""

import pytest
from unittest.mock import AsyncMock, Mock

from terminator.adapters.protocols import (
    InstanceType,
    UnifiedSession,
    TerminalType,
    SessionState,
)
from terminator.services.instance_detector import (
    InstanceDetector,
    DetectionPattern,
    DEFAULT_DETECTION_PATTERNS,
)


class TestInstanceDetector:
    """Test suite for InstanceDetector service."""

    @pytest.fixture
    def detector(self) -> InstanceDetector:
        """Create instance detector with default patterns."""
        return InstanceDetector()

    @pytest.fixture
    def mock_adapter(self) -> AsyncMock:
        """Create mock terminal adapter."""
        adapter = AsyncMock()
        return adapter

    @pytest.fixture
    def mock_session(self) -> UnifiedSession:
        """Create mock unified session."""
        return UnifiedSession(
            id="test:session:0:0",
            name="test-session",
            terminal_type=TerminalType.TMUX,
            state=SessionState.IDLE,
        )

    # Test Claude Code detection
    async def test_detect_claude_code_with_banner(self, detector: InstanceDetector):
        """Detect Claude Code from banner text."""
        screen_content = """
        Welcome to Claude Code
        Claude Opus 4.5
        Type /help for assistance
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.CLAUDE_CODE

    async def test_detect_claude_code_with_prompt(self, detector: InstanceDetector):
        """Detect Claude Code from prompt."""
        screen_content = """
        /home/user/project
        claude-code> help
        Available commands...
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.CLAUDE_CODE

    async def test_detect_claude_code_with_ui_element(self, detector: InstanceDetector):
        """Detect Claude Code from UI box characters."""
        screen_content = """
        ╭─ Claude Code Session ─╮
        │ Working on task...    │
        ╰───────────────────────╯
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.CLAUDE_CODE

    # Test Auggie detection
    async def test_detect_auggie_with_banner(self, detector: InstanceDetector):
        """Detect Auggie from banner."""
        screen_content = """
        Augment Code Assistant
        Version 1.0
        augment>
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.AUGGIE

    async def test_detect_auggie_with_prompt(self, detector: InstanceDetector):
        """Detect Auggie from prompt."""
        screen_content = "augment> show status"
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.AUGGIE

    # Test Python detection
    async def test_detect_python_repl(self, detector: InstanceDetector):
        """Detect standard Python REPL."""
        screen_content = """
        Python 3.12.0
        >>> import sys
        >>> sys.version
        '3.12.0'
        >>>
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.PYTHON

    async def test_detect_ipython(self, detector: InstanceDetector):
        """Detect IPython REPL."""
        screen_content = """
        IPython 8.18.0
        In [1]: import numpy as np
        In [2]: np.array([1, 2, 3])
        Out[2]: array([1, 2, 3])
        In [3]:
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.PYTHON

    async def test_detect_python_continuation(self, detector: InstanceDetector):
        """Detect Python continuation prompt."""
        screen_content = """>>> def hello():
...     print("world")
...
>>>"""
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.PYTHON

    # Test Node detection
    async def test_detect_node_repl(self, detector: InstanceDetector):
        """Detect Node.js REPL."""
        screen_content = """
        Welcome to Node.js v20.10.0
        Type ".help" for more information.
        > console.log('hello')
        hello
        undefined
        >
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.NODE

    async def test_detect_node_prompt(self, detector: InstanceDetector):
        """Detect Node.js from prompt only."""
        screen_content = "> const x = 42;"
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.NODE

    # Test Shell detection
    async def test_detect_shell_bash(self, detector: InstanceDetector):
        """Detect bash shell."""
        screen_content = """
        user@hostname:~$ ls -la
        total 24
        drwxr-xr-x  5 user user 4096 Dec 29 10:00 .
        drwxr-xr-x 10 user user 4096 Dec 28 15:30 ..
        user@hostname:~$
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.SHELL

    async def test_detect_shell_zsh(self, detector: InstanceDetector):
        """Detect zsh shell."""
        screen_content = """
        ~ ❯ echo $SHELL
        /bin/zsh
        ~ ❯
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.SHELL

    # Test edge cases
    async def test_detect_empty_content(self, detector: InstanceDetector):
        """Return UNKNOWN for empty content."""
        result = await detector.detect_type("test", "")
        assert result == InstanceType.UNKNOWN

    async def test_detect_whitespace_only(self, detector: InstanceDetector):
        """Return UNKNOWN for whitespace-only content."""
        result = await detector.detect_type("test", "   \n\n   ")
        assert result == InstanceType.UNKNOWN

    async def test_detect_no_match(self, detector: InstanceDetector):
        """Return UNKNOWN when no patterns match."""
        screen_content = "Some random output without recognizable patterns"
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.UNKNOWN

    # Test priority ordering
    async def test_priority_claude_over_shell(self, detector: InstanceDetector):
        """Claude Code should be detected over shell due to higher priority."""
        screen_content = """
        user@hostname:~$ claude-code
        Welcome to Claude Code
        Claude Opus 4.5
        claude-code>
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.CLAUDE_CODE

    async def test_priority_python_over_shell(self, detector: InstanceDetector):
        """Python should be detected over shell due to higher priority."""
        screen_content = """
        $ python3
        Python 3.12.0
        >>> import os
        >>>
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.PYTHON

    # Test detect_from_session
    async def test_detect_from_session_success(
        self,
        detector: InstanceDetector,
        mock_adapter: AsyncMock,
        mock_session: UnifiedSession,
    ):
        """Detect instance type from session output."""
        mock_adapter.get_session_output.return_value = """
        Python 3.12.0
        >>> print("hello")
        hello
        >>>
        """

        result = await detector.detect_from_session(mock_session, mock_adapter)

        assert result == InstanceType.PYTHON
        mock_adapter.get_session_output.assert_called_once_with(
            mock_session.id, lines=100
        )

    async def test_detect_from_session_defaults_to_shell(
        self,
        detector: InstanceDetector,
        mock_adapter: AsyncMock,
        mock_session: UnifiedSession,
    ):
        """Default to SHELL when no match found."""
        mock_adapter.get_session_output.return_value = "No recognizable patterns"

        result = await detector.detect_from_session(mock_session, mock_adapter)

        assert result == InstanceType.SHELL

    async def test_detect_from_session_handles_error(
        self,
        detector: InstanceDetector,
        mock_adapter: AsyncMock,
        mock_session: UnifiedSession,
    ):
        """Return UNKNOWN on error."""
        mock_adapter.get_session_output.side_effect = Exception("Connection failed")

        result = await detector.detect_from_session(mock_session, mock_adapter)

        assert result == InstanceType.UNKNOWN

    # Test custom patterns
    async def test_add_custom_pattern(self, detector: InstanceDetector):
        """Add custom detection pattern dynamically."""
        # Add custom pattern for vim
        detector.add_pattern(InstanceType.SHELL, r"VIM - Vi IMproved", priority=60)

        screen_content = """
        VIM - Vi IMproved
        version 9.0
        ~
        ~
        """

        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.SHELL

    async def test_custom_patterns_initialization(self):
        """Initialize detector with custom patterns."""
        custom_patterns = [
            DetectionPattern(
                instance_type=InstanceType.PYTHON,
                patterns=[r"pypy"],
                priority=100,
            ),
        ]

        detector = InstanceDetector(patterns=custom_patterns)
        screen_content = "pypy 3.10"

        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.PYTHON

    # Test case insensitivity
    async def test_case_insensitive_matching(self, detector: InstanceDetector):
        """Patterns should match case-insensitively."""
        # Lowercase "claude code"
        screen_content = "welcome to claude code"
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.CLAUDE_CODE

        # Mixed case "AUGGIE"
        screen_content = "AUGGIE assistant ready"
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.AUGGIE

    # Test multiline matching
    async def test_multiline_pattern_matching(self, detector: InstanceDetector):
        """Patterns should work across multiple lines."""
        screen_content = """
        Line 1: Some output
        Line 2: More output
        Line 3: Python 3.12.0
        Line 4: More stuff
        >>> import sys
        """
        result = await detector.detect_type("test", screen_content)
        assert result == InstanceType.PYTHON

    # Test pattern compilation
    def test_patterns_are_compiled(self, detector: InstanceDetector):
        """Patterns should be compiled for performance."""
        # Check that compiled patterns exist
        assert InstanceType.CLAUDE_CODE in detector._compiled_patterns
        assert InstanceType.PYTHON in detector._compiled_patterns
        assert len(detector._compiled_patterns[InstanceType.CLAUDE_CODE]) > 0

    def test_patterns_sorted_by_priority(self, detector: InstanceDetector):
        """Patterns should be sorted by priority descending."""
        priorities = [p.priority for p in detector._patterns]
        assert priorities == sorted(priorities, reverse=True)


class TestDetectionPattern:
    """Test DetectionPattern dataclass."""

    def test_create_detection_pattern(self):
        """Create detection pattern with required fields."""
        pattern = DetectionPattern(
            instance_type=InstanceType.CLAUDE_CODE,
            patterns=[r"claude-code>", r"Claude Code"],
            priority=100,
        )

        assert pattern.instance_type == InstanceType.CLAUDE_CODE
        assert len(pattern.patterns) == 2
        assert pattern.priority == 100

    def test_default_priority(self):
        """Default priority should be 0."""
        pattern = DetectionPattern(
            instance_type=InstanceType.SHELL,
            patterns=[r"$"],
        )

        assert pattern.priority == 0


class TestDefaultPatterns:
    """Test default detection patterns configuration."""

    def test_default_patterns_exist(self):
        """Default patterns should be defined."""
        assert len(DEFAULT_DETECTION_PATTERNS) > 0

    def test_default_patterns_have_all_types(self):
        """Default patterns should cover main instance types."""
        types_in_patterns = {p.instance_type for p in DEFAULT_DETECTION_PATTERNS}

        assert InstanceType.CLAUDE_CODE in types_in_patterns
        assert InstanceType.AUGGIE in types_in_patterns
        assert InstanceType.PYTHON in types_in_patterns
        assert InstanceType.NODE in types_in_patterns
        assert InstanceType.SHELL in types_in_patterns

    def test_default_patterns_have_priority_ordering(self):
        """Claude Code and Auggie should have higher priority than shell."""
        claude_priority = next(
            p.priority
            for p in DEFAULT_DETECTION_PATTERNS
            if p.instance_type == InstanceType.CLAUDE_CODE
        )
        shell_priority = next(
            p.priority
            for p in DEFAULT_DETECTION_PATTERNS
            if p.instance_type == InstanceType.SHELL
        )

        assert claude_priority > shell_priority
