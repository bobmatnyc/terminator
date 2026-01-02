"""Claude Code specific detection for two-way meta-communication."""

import asyncio
import re
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class ClaudeCodeState(Enum):
    """States of Claude Code session."""

    UNKNOWN = auto()
    STARTING = auto()
    READY = auto()
    THINKING = auto()
    RESPONDING = auto()
    IDLE = auto()


@dataclass
class DetectionResult:
    """Result of state detection."""

    state: ClaudeCodeState
    confidence: float  # 0.0 to 1.0
    raw_output: str
    matched_pattern: str | None = None


class ClaudeCodeDetector:
    """Detects Claude Code states from terminal output.

    This detector analyzes terminal output to identify when Claude Code
    is ready for input, thinking, responding, or idle. It uses pattern
    matching and output stability checks to ensure reliable detection.

    Example:
        detector = ClaudeCodeDetector()
        result = await detector.wait_for_ready(get_output_fn, timeout=60.0)
        if result.state == ClaudeCodeState.READY:
            print("Claude Code is ready!")
    """

    # Patterns that indicate Claude Code is ready for input
    READY_PATTERNS = [
        r"^\s*>\s+",  # Claude Code prompt with suggestion (> followed by space and text)
        r"^\s*>\s*$",  # Claude Code prompt (bare > at end of line)
        r"matsuoka-com \| git:",  # Status bar pattern (project name)
        r"\| Opus \d+\.\d+ \|",  # Model indicator in status bar
        r"╭─.*Claude",  # Claude Code UI header
        r"What would you like to do\?",  # Initial prompt
        r"How can I help",  # Help prompt
    ]

    # Patterns that indicate Claude Code is thinking/processing
    THINKING_PATTERNS = [
        r"⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏",  # Spinner characters
        r"Thinking\.\.\.",
        r"Working\.\.\.",
        r"Processing\.\.\.",
    ]

    # Patterns that indicate Claude Code is responding
    RESPONDING_PATTERNS = [
        r"─{3,}",  # Horizontal dividers in output
        r"```",  # Code blocks
        r"•\s",  # Bullet points
    ]

    # Patterns that indicate startup is complete
    STARTUP_COMPLETE_PATTERNS = [
        r"Claude Code",
        r"Version:",
        r"Tips:",
        r"What would you like",
    ]

    def __init__(
        self,
        ready_timeout: float = 60.0,
        response_timeout: float = 300.0,
        poll_interval: float = 0.5,
    ):
        """Initialize detector.

        Args:
            ready_timeout: Maximum time to wait for ready state (seconds)
            response_timeout: Maximum time to wait for response completion (seconds)
            poll_interval: How often to poll for state changes (seconds)
        """
        self.ready_timeout = ready_timeout
        self.response_timeout = response_timeout
        self.poll_interval = poll_interval

    def detect_state(self, output: str) -> DetectionResult:
        """Detect current Claude Code state from terminal output.

        Checks patterns in priority order:
        1. READY (highest priority - indicates ready for input)
        2. THINKING (actively processing)
        3. RESPONDING (generating output)
        4. UNKNOWN (no patterns matched)

        Args:
            output: Terminal output to analyze

        Returns:
            DetectionResult with detected state and metadata
        """
        # Check for ready state (highest priority)
        for pattern in self.READY_PATTERNS:
            if re.search(pattern, output, re.MULTILINE):
                return DetectionResult(
                    state=ClaudeCodeState.READY,
                    confidence=0.9,
                    raw_output=output[-500:],
                    matched_pattern=pattern,
                )

        # Check for thinking state
        for pattern in self.THINKING_PATTERNS:
            if re.search(pattern, output):
                return DetectionResult(
                    state=ClaudeCodeState.THINKING,
                    confidence=0.8,
                    raw_output=output[-500:],
                    matched_pattern=pattern,
                )

        # Check for responding state
        for pattern in self.RESPONDING_PATTERNS:
            if re.search(pattern, output):
                return DetectionResult(
                    state=ClaudeCodeState.RESPONDING,
                    confidence=0.7,
                    raw_output=output[-500:],
                    matched_pattern=pattern,
                )

        return DetectionResult(
            state=ClaudeCodeState.UNKNOWN,
            confidence=0.0,
            raw_output=output[-500:],
        )

    def is_startup_complete(self, output: str) -> bool:
        """Check if Claude Code startup is complete.

        Requires at least 2 startup patterns to match for reliability.

        Args:
            output: Terminal output to analyze

        Returns:
            True if startup appears complete, False otherwise
        """
        matches = sum(
            1
            for pattern in self.STARTUP_COMPLETE_PATTERNS
            if re.search(pattern, output, re.IGNORECASE)
        )
        return matches >= 2  # Need at least 2 patterns to confirm

    async def wait_for_ready(
        self,
        get_output_fn: Callable[[], Awaitable[str]],
        timeout: float | None = None,
    ) -> DetectionResult:
        """Wait for Claude Code to be ready for input.

        Polls terminal output at poll_interval until:
        - Claude Code shows ready prompt (READY state detected)
        - Timeout is reached (raises TimeoutError)

        Args:
            get_output_fn: Async function that returns terminal output
            timeout: Maximum time to wait (uses self.ready_timeout if None)

        Returns:
            DetectionResult when ready state is detected

        Raises:
            TimeoutError: If Claude Code doesn't become ready within timeout
        """
        timeout = timeout or self.ready_timeout
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Claude Code did not become ready within {timeout}s"
                )

            output = await get_output_fn()
            result = self.detect_state(output)

            if result.state == ClaudeCodeState.READY:
                logger.info(
                    "Claude Code ready (confidence: %.2f, pattern: %s)",
                    result.confidence,
                    result.matched_pattern,
                )
                return result

            if self.is_startup_complete(output):
                logger.debug("Claude Code startup complete, waiting for ready prompt")

            await asyncio.sleep(self.poll_interval)

    async def wait_for_response_complete(
        self,
        get_output_fn: Callable[[], Awaitable[str]],
        timeout: float | None = None,
        stability_checks: int = 3,
    ) -> DetectionResult:
        """Wait for Claude Code to finish responding.

        Polls terminal output until:
        - Claude Code returns to READY state (ready for next input)
        - Output is stable for stability_checks consecutive polls
        - Timeout is reached (raises TimeoutError)

        Args:
            get_output_fn: Async function that returns terminal output
            timeout: Maximum time to wait (uses self.response_timeout if None)
            stability_checks: Number of consecutive stable checks required

        Returns:
            DetectionResult when response is complete

        Raises:
            TimeoutError: If response doesn't complete within timeout
        """
        timeout = timeout or self.response_timeout
        start_time = asyncio.get_event_loop().time()
        last_output = ""
        stable_count = 0

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Claude Code response did not complete within {timeout}s"
                )

            output = await get_output_fn()
            result = self.detect_state(output)

            # If we're back to READY state, response is complete
            if result.state == ClaudeCodeState.READY:
                logger.info("Claude Code response complete (ready for next input)")
                return result

            # Check for output stability (no changes = response done)
            if output == last_output:
                stable_count += 1
                if stable_count >= stability_checks:
                    logger.info(
                        "Claude Code response complete (output stable for %d checks)",
                        stability_checks,
                    )
                    return DetectionResult(
                        state=ClaudeCodeState.IDLE,
                        confidence=0.7,
                        raw_output=output[-500:],
                    )
            else:
                stable_count = 0
                last_output = output

            await asyncio.sleep(self.poll_interval)
