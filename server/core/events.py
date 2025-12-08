"""Event bus for inter-component communication."""
from typing import Callable, Any

class EventBus:
    """Simple event bus for pub/sub messaging."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type."""
        raise NotImplementedError("EventBus.subscribe not yet implemented")

    def publish(self, event_type: str, data: Any) -> None:
        """Publish an event to all subscribers."""
        raise NotImplementedError("EventBus.publish not yet implemented")
