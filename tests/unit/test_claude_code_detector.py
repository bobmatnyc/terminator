"""Unit tests for ClaudeCodeDetector service."""

import pytest
from unittest.mock import AsyncMock

from terminator.services.claude_code_detector import (
    ClaudeCodeDetector,
    ClaudeCodeState,
    DetectionResult,
)


class TestClaudeCodeDetector:
    """Test suite for ClaudeCodeDetector service."""

    @pytest.fixture
    def detector(self) -> ClaudeCodeDetector:
        """Create detector with default settings."""
        return ClaudeCodeDetector()

    @pytest.fixture
    def fast_detector(self) -> ClaudeCodeDetector:
        """Create detector with fast polling for tests."""
        return ClaudeCodeDetector(
            ready_timeout=2.0,
            response_timeout=3.0,
            poll_interval=0.1,
        )

    # Test detect_state() with READY patterns
    def test_detect_ready_with_prompt(self, detector: ClaudeCodeDetector):
        """Detect READY state from prompt character."""
        output = """Previous output...
>
"""
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.READY
        assert result.confidence == 0.9
        # Should match either bare prompt or prompt with space pattern
        assert result.matched_pattern in [r"^\s*>\s+", r"^\s*>\s*$"]

    def test_detect_ready_with_ui_header(self, detector: ClaudeCodeDetector):
        """Detect READY state from UI header."""
        output = """
        ╭─ Claude Code ─╮
        │ Version: 1.0  │
        ╰────────────────╯
        >
        """
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.READY
        # Should match UI header first, or any of the prompt patterns
        assert result.matched_pattern in [r"╭─.*Claude", r"^\s*>\s+", r"^\s*>\s*$"]

    def test_detect_ready_with_help_prompt(self, detector: ClaudeCodeDetector):
        """Detect READY state from help text."""
        output = "What would you like to do?"
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.READY
        assert result.confidence == 0.9

    def test_detect_ready_with_suggestion(self, detector: ClaudeCodeDetector):
        """Detect READY state with Claude's suggestion prompt."""
        output = '''> Try "edit chat-bot-fixed.tsx to..."'''
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.READY
        assert result.confidence == 0.9
        assert result.matched_pattern == r"^\s*>\s+"

    def test_detect_ready_with_status_bar_project(self, detector: ClaudeCodeDetector):
        """Detect READY state from status bar with project name."""
        output = "matsuoka-com | git: main | Opus 4.5 |"
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.READY
        assert result.confidence == 0.9
        assert result.matched_pattern == r"matsuoka-com \| git:"

    def test_detect_ready_with_status_bar_model(self, detector: ClaudeCodeDetector):
        """Detect READY state from status bar model indicator."""
        output = "| Opus 4.5 | Budget: 95%"
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.READY
        assert result.confidence == 0.9
        assert result.matched_pattern == r"\| Opus \d+\.\d+ \|"

    def test_detect_ready_multiline_with_suggestion(self, detector: ClaudeCodeDetector):
        """Detect READY state with suggestion in multiline output."""
        output = """Previous command output...
Some results here

> Try "edit main.py to add logging"
"""
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.READY
        assert result.confidence == 0.9

    # Test detect_state() with THINKING patterns
    def test_detect_thinking_with_spinner(self, detector: ClaudeCodeDetector):
        """Detect THINKING state from spinner characters."""
        spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        for char in spinner_chars:
            output = f"Processing {char}"
            result = detector.detect_state(output)

            assert result.state == ClaudeCodeState.THINKING
            assert result.confidence == 0.8

    def test_detect_thinking_with_text(self, detector: ClaudeCodeDetector):
        """Detect THINKING state from thinking text."""
        outputs = [
            "Thinking...",
            "Working...",
            "Processing...",
        ]
        for output in outputs:
            result = detector.detect_state(output)

            assert result.state == ClaudeCodeState.THINKING
            assert result.confidence == 0.8

    # Test detect_state() with RESPONDING patterns
    def test_detect_responding_with_divider(self, detector: ClaudeCodeDetector):
        """Detect RESPONDING state from horizontal dividers."""
        output = """
        ───────────────────
        Analysis Results
        ───────────────────
        """
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.RESPONDING
        assert result.confidence == 0.7

    def test_detect_responding_with_code_block(self, detector: ClaudeCodeDetector):
        """Detect RESPONDING state from code blocks."""
        output = """
        Here's the solution:
        ```python
        def hello():
            print("world")
        ```
        """
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.RESPONDING

    def test_detect_responding_with_bullet_points(self, detector: ClaudeCodeDetector):
        """Detect RESPONDING state from bullet points."""
        output = """
        Key findings:
        • First point
        • Second point
        • Third point
        """
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.RESPONDING

    # Test detect_state() with UNKNOWN
    def test_detect_unknown_with_no_patterns(self, detector: ClaudeCodeDetector):
        """Return UNKNOWN when no patterns match."""
        output = "Random output without any recognizable patterns"
        result = detector.detect_state(output)

        assert result.state == ClaudeCodeState.UNKNOWN
        assert result.confidence == 0.0
        assert result.matched_pattern is None

    def test_detect_unknown_with_empty_output(self, detector: ClaudeCodeDetector):
        """Return UNKNOWN for empty output."""
        result = detector.detect_state("")

        assert result.state == ClaudeCodeState.UNKNOWN
        assert result.confidence == 0.0

    # Test is_startup_complete()
    def test_startup_complete_with_sufficient_patterns(
        self, detector: ClaudeCodeDetector
    ):
        """Detect startup completion with 2+ patterns."""
        output = """
        Claude Code
        Version: 1.0.0
        Ready for input
        """
        assert detector.is_startup_complete(output) is True

    def test_startup_complete_with_all_patterns(self, detector: ClaudeCodeDetector):
        """Detect startup with all startup patterns present."""
        output = """
        Welcome to Claude Code
        Version: 1.2.3
        Tips: Type /help for assistance
        What would you like to do?
        """
        assert detector.is_startup_complete(output) is True

    def test_startup_incomplete_with_single_pattern(self, detector: ClaudeCodeDetector):
        """Don't detect startup with only 1 pattern."""
        output = "Claude Code starting..."
        assert detector.is_startup_complete(output) is False

    def test_startup_incomplete_with_no_patterns(self, detector: ClaudeCodeDetector):
        """Don't detect startup with no patterns."""
        output = "Random terminal output"
        assert detector.is_startup_complete(output) is False

    def test_startup_case_insensitive(self, detector: ClaudeCodeDetector):
        """Startup detection should be case-insensitive."""
        output = """
        claude code
        version: 1.0.0
        """
        assert detector.is_startup_complete(output) is True

    # Test wait_for_ready()
    @pytest.mark.asyncio
    async def test_wait_for_ready_immediate_success(
        self, fast_detector: ClaudeCodeDetector
    ):
        """Return immediately when already ready."""
        output = """Claude Code initialized
>
"""
        get_output = AsyncMock(return_value=output)

        result = await fast_detector.wait_for_ready(get_output)

        assert result.state == ClaudeCodeState.READY
        assert result.confidence == 0.9
        # Should only call once since ready immediately
        assert get_output.call_count == 1

    @pytest.mark.asyncio
    async def test_wait_for_ready_after_polling(
        self, fast_detector: ClaudeCodeDetector
    ):
        """Wait for ready state after several polls."""
        outputs = [
            "Starting Claude Code...",
            "Loading modules...",
            "Claude Code\nVersion: 1.0\nReady\n>",
        ]
        call_count = 0

        async def get_output():
            nonlocal call_count
            output = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            return output

        result = await fast_detector.wait_for_ready(get_output)

        assert result.state == ClaudeCodeState.READY
        assert call_count == 3  # Called 3 times before finding ready state

    @pytest.mark.asyncio
    async def test_wait_for_ready_timeout(self, fast_detector: ClaudeCodeDetector):
        """Raise TimeoutError when ready state not reached."""
        get_output = AsyncMock(return_value="Still starting...")

        with pytest.raises(TimeoutError) as exc_info:
            await fast_detector.wait_for_ready(get_output, timeout=0.5)

        assert "did not become ready within" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_ready_logs_startup_progress(
        self, fast_detector: ClaudeCodeDetector, caplog
    ):
        """Log when startup is complete but not yet ready."""
        outputs = [
            "Starting...",
            "Claude Code\nVersion: 1.0",  # Startup complete
            "Loading...",
            ">",  # Ready
        ]
        call_count = 0

        async def get_output():
            nonlocal call_count
            output = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            return output

        with caplog.at_level("DEBUG"):
            result = await fast_detector.wait_for_ready(get_output)

        assert result.state == ClaudeCodeState.READY
        # Should log startup completion
        assert any("startup complete" in record.message for record in caplog.records)

    # Test wait_for_response_complete()
    @pytest.mark.asyncio
    async def test_wait_for_response_ready_state(
        self, fast_detector: ClaudeCodeDetector
    ):
        """Return when READY state is detected."""
        outputs = [
            "Generating response...",
            "Here is the answer",
            ">",  # Back to ready
        ]
        call_count = 0

        async def get_output():
            nonlocal call_count
            output = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            return output

        result = await fast_detector.wait_for_response_complete(get_output)

        assert result.state == ClaudeCodeState.READY
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_wait_for_response_output_stability(
        self, fast_detector: ClaudeCodeDetector
    ):
        """Return when output is stable for multiple checks."""
        outputs = [
            "Generating...",
            "Response text here",
            "Response text here",  # Same (1)
            "Response text here",  # Same (2)
            "Response text here",  # Same (3) - triggers stability
        ]
        call_count = 0

        async def get_output():
            nonlocal call_count
            output = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            return output

        result = await fast_detector.wait_for_response_complete(
            get_output, stability_checks=3
        )

        assert result.state == ClaudeCodeState.IDLE
        assert result.confidence == 0.7
        # Should check multiple times for stability
        assert call_count >= 4

    @pytest.mark.asyncio
    async def test_wait_for_response_stability_reset_on_change(
        self, fast_detector: ClaudeCodeDetector
    ):
        """Reset stability counter when output changes."""
        outputs = [
            "Generating...",
            "Response A",
            "Response A",  # Stable 1
            "Response B",  # Changed - reset counter
            "Response B",  # Stable 1
            "Response B",  # Stable 2
            "Response B",  # Stable 3 - triggers
        ]
        call_count = 0

        async def get_output():
            nonlocal call_count
            output = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            return output

        result = await fast_detector.wait_for_response_complete(
            get_output, stability_checks=3
        )

        assert result.state == ClaudeCodeState.IDLE
        assert call_count == 7  # Takes longer due to reset

    @pytest.mark.asyncio
    async def test_wait_for_response_timeout(self, fast_detector: ClaudeCodeDetector):
        """Raise TimeoutError when response doesn't complete."""
        # Return different output each time to prevent stability detection
        call_count = 0

        async def get_output():
            nonlocal call_count
            call_count += 1
            return f"Still generating... {call_count}"

        with pytest.raises(TimeoutError) as exc_info:
            await fast_detector.wait_for_response_complete(get_output, timeout=0.5)

        assert "did not complete within" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_response_custom_stability_checks(
        self, fast_detector: ClaudeCodeDetector
    ):
        """Use custom stability_checks parameter."""
        outputs = [
            "Response",
            "Response",  # Stable 1
            "Response",  # Stable 2 - triggers with checks=2
        ]
        call_count = 0

        async def get_output():
            nonlocal call_count
            output = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            return output

        result = await fast_detector.wait_for_response_complete(
            get_output, stability_checks=2
        )

        assert result.state == ClaudeCodeState.IDLE
        assert call_count == 3

    # Test edge cases
    def test_detect_state_truncates_raw_output(self, detector: ClaudeCodeDetector):
        """Raw output should be truncated to last 500 chars."""
        long_output = "x" * 1000 + "\n>"
        result = detector.detect_state(long_output)

        assert result.state == ClaudeCodeState.READY
        # Raw output should be last 500 chars
        assert len(result.raw_output) <= 500
        assert result.raw_output.endswith(">")

    def test_detect_state_priority_ready_over_responding(
        self, detector: ClaudeCodeDetector
    ):
        """READY state should have priority over RESPONDING."""
        output = """Here's the code:
```python
print("hello")
```
>
"""
        result = detector.detect_state(output)

        # Should detect READY (prompt) instead of RESPONDING (code block)
        assert result.state == ClaudeCodeState.READY

    def test_detect_state_priority_thinking_over_responding(
        self, detector: ClaudeCodeDetector
    ):
        """THINKING state should have priority over RESPONDING."""
        output = """
        ```python
        code here
        ```
        Thinking...
        """
        result = detector.detect_state(output)

        # THINKING has higher priority than RESPONDING
        # But this is NOT the case in the implementation
        # Let's check actual behavior
        # Actually, THINKING comes AFTER READY in checks, so it wins
        assert result.state == ClaudeCodeState.THINKING

    @pytest.mark.asyncio
    async def test_custom_timeouts(self):
        """Use custom timeout values."""
        detector = ClaudeCodeDetector(
            ready_timeout=1.0,
            response_timeout=2.0,
            poll_interval=0.05,
        )

        assert detector.ready_timeout == 1.0
        assert detector.response_timeout == 2.0
        assert detector.poll_interval == 0.05

        # Test that custom timeout is used
        get_output = AsyncMock(return_value="not ready")
        with pytest.raises(TimeoutError):
            await detector.wait_for_ready(get_output, timeout=0.2)


class TestDetectionResult:
    """Test DetectionResult dataclass."""

    def test_create_detection_result(self):
        """Create DetectionResult with all fields."""
        result = DetectionResult(
            state=ClaudeCodeState.READY,
            confidence=0.9,
            raw_output="some output",
            matched_pattern=r"^>",
        )

        assert result.state == ClaudeCodeState.READY
        assert result.confidence == 0.9
        assert result.raw_output == "some output"
        assert result.matched_pattern == r"^>"

    def test_detection_result_optional_pattern(self):
        """matched_pattern is optional."""
        result = DetectionResult(
            state=ClaudeCodeState.UNKNOWN,
            confidence=0.0,
            raw_output="",
        )

        assert result.matched_pattern is None


class TestClaudeCodeState:
    """Test ClaudeCodeState enum."""

    def test_enum_values_exist(self):
        """All expected states should exist."""
        assert ClaudeCodeState.UNKNOWN
        assert ClaudeCodeState.STARTING
        assert ClaudeCodeState.READY
        assert ClaudeCodeState.THINKING
        assert ClaudeCodeState.RESPONDING
        assert ClaudeCodeState.IDLE

    def test_enum_values_unique(self):
        """Each state should have unique value."""
        states = [
            ClaudeCodeState.UNKNOWN,
            ClaudeCodeState.STARTING,
            ClaudeCodeState.READY,
            ClaudeCodeState.THINKING,
            ClaudeCodeState.RESPONDING,
            ClaudeCodeState.IDLE,
        ]
        assert len(states) == len(set(states))
