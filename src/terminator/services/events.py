"""Event types and data structures for session monitoring."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EventType(Enum):
    """Types of session events."""

    INPUT_REQUIRED = "input_required"  # Session needs user input
    OUTPUT_READY = "output_ready"  # Command completed, output stable
    STATE_CHANGED = "state_changed"  # Generic state transition
    ERROR = "error"  # Monitoring error


@dataclass
class SessionEvent:
    """Represents a session monitoring event."""

    event_type: EventType
    session_id: str
    session_address: str  # @project address for display
    timestamp: datetime = field(default_factory=datetime.now)
    message: str = ""
    details: dict = field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable event string."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        return f"[{time_str}] {self.session_address}: {self.event_type.value} - {self.message}"


@dataclass
class MonitoredSession:
    """Tracks monitoring state for a session."""

    session_id: str
    session_address: str
    previous_status: str = "unknown"
    previous_indicators: dict = field(default_factory=dict)
    poll_count: int = 0
    last_poll: Optional[datetime] = None
