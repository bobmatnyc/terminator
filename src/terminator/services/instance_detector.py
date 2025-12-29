"""Instance type detection service.

Analyzes terminal screen content to detect the type of REPL or shell running.
Supports detection of Claude Code, Auggie, Python, Node, and shell sessions.
"""

import re
from dataclasses import dataclass
from typing import Optional

from ..adapters.protocols import (
    ITerminalAdapter,
    InstanceType,
    UnifiedSession,
)


@dataclass(frozen=True)
class DetectionPattern:
    """Pattern configuration for instance type detection."""

    instance_type: InstanceType
    patterns: list[str]
    priority: int = 0  # Higher priority checked first


# Detection patterns in priority order (higher priority = more specific)
DEFAULT_DETECTION_PATTERNS: list[DetectionPattern] = [
    # Claude Code (priority 100 - very specific)
    DetectionPattern(
        instance_type=InstanceType.CLAUDE_CODE,
        patterns=[
            r"Claude Code",
            r"claude-code>",
            r"anthropic.*claude",
            r"╭─.*Claude",  # Claude Code UI elements
            r"Claude\s+Opus",
            r"Claude\s+Sonnet",
        ],
        priority=100,
    ),
    # Auggie (priority 90 - very specific)
    DetectionPattern(
        instance_type=InstanceType.AUGGIE,
        patterns=[
            r"Auggie",
            r"augment>",
            r"Augment Code",
            r"augment-code",
        ],
        priority=90,
    ),
    # Python REPL (priority 50 - moderately specific)
    DetectionPattern(
        instance_type=InstanceType.PYTHON,
        patterns=[
            r"^>>>",  # Standard Python prompt
            r"^\.\.\.\s",  # Python continuation prompt (with space)
            r"^In \[\d+\]:",  # IPython prompt
            r"^Out\[\d+\]:",  # IPython output
            r"Python \d+\.\d+",  # Python version string
        ],
        priority=50,
    ),
    # Node REPL (priority 40 - moderately specific)
    DetectionPattern(
        instance_type=InstanceType.NODE,
        patterns=[
            r"^>\s",  # Node REPL prompt (with space after >)
            r"Welcome to Node\.js",
            r"node v\d+\.\d+",
        ],
        priority=40,
    ),
    # Shell (priority 10 - least specific, catch-all)
    DetectionPattern(
        instance_type=InstanceType.SHELL,
        patterns=[
            r"[$#%❯➜]\s*$",  # Shell prompt at end of line (including zsh arrows)
            r"bash-\d+\.\d+",
            r"zsh \d+\.\d+",
            r"/bin/zsh",  # zsh path
            r"/bin/bash",  # bash path
        ],
        priority=10,
    ),
]


class InstanceDetector:
    """Service for detecting instance types from terminal screen content.

    Uses regex pattern matching against screen output to identify
    Claude Code, Auggie, Python, Node, shell, or unknown sessions.

    Example:
        detector = InstanceDetector()
        instance_type = await detector.detect_from_session(session, adapter)
    """

    def __init__(
        self,
        patterns: Optional[list[DetectionPattern]] = None,
    ):
        """Initialize instance detector.

        Args:
            patterns: Custom detection patterns (uses defaults if None)
        """
        self._patterns = patterns or DEFAULT_DETECTION_PATTERNS
        # Sort by priority descending (highest priority first)
        self._patterns.sort(key=lambda p: p.priority, reverse=True)

        # Compile regex patterns for performance
        self._compiled_patterns: dict[InstanceType, list[re.Pattern[str]]] = {}
        for pattern in self._patterns:
            compiled = [
                re.compile(p, re.MULTILINE | re.IGNORECASE) for p in pattern.patterns
            ]
            if pattern.instance_type not in self._compiled_patterns:
                self._compiled_patterns[pattern.instance_type] = []
            self._compiled_patterns[pattern.instance_type].extend(compiled)

    async def detect_type(
        self, session_id: str, screen_content: str
    ) -> InstanceType:
        """Analyze screen content to determine REPL type.

        Args:
            session_id: Session identifier (for logging/debugging)
            screen_content: Raw terminal screen output

        Returns:
            Detected instance type (UNKNOWN if no match)
        """
        if not screen_content or not screen_content.strip():
            return InstanceType.UNKNOWN

        # Check patterns in priority order
        for pattern in self._patterns:
            compiled_patterns = self._compiled_patterns[pattern.instance_type]
            for regex in compiled_patterns:
                if regex.search(screen_content):
                    return pattern.instance_type

        # No match found, default to UNKNOWN (caller may set to SHELL)
        return InstanceType.UNKNOWN

    async def detect_from_session(
        self,
        session: UnifiedSession,
        adapter: ITerminalAdapter,
        lines: int = 100,
    ) -> InstanceType:
        """Capture session output and detect instance type.

        Args:
            session: Unified session to analyze
            adapter: Terminal adapter to capture output
            lines: Number of lines to capture (default 100 for better detection)

        Returns:
            Detected instance type
        """
        try:
            # Capture screen content
            screen_content = await adapter.get_session_output(session.id, lines=lines)

            # Detect instance type
            instance_type = await self.detect_type(session.id, screen_content)

            # If still unknown, default to shell (most sessions are shells)
            if instance_type == InstanceType.UNKNOWN:
                instance_type = InstanceType.SHELL

            return instance_type

        except Exception:
            # On error, default to unknown
            return InstanceType.UNKNOWN

    def add_pattern(
        self,
        instance_type: InstanceType,
        pattern: str,
        priority: int = 0,
    ) -> None:
        """Add a custom detection pattern dynamically.

        Args:
            instance_type: Type to detect
            pattern: Regex pattern string
            priority: Priority level (higher = checked first)
        """
        compiled = re.compile(pattern, re.MULTILINE | re.IGNORECASE)

        if instance_type not in self._compiled_patterns:
            self._compiled_patterns[instance_type] = []

        self._compiled_patterns[instance_type].append(compiled)

        # Add to patterns list and re-sort
        detection_pattern = DetectionPattern(
            instance_type=instance_type,
            patterns=[pattern],
            priority=priority,
        )
        self._patterns.append(detection_pattern)
        self._patterns.sort(key=lambda p: p.priority, reverse=True)
