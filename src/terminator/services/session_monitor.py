"""Session monitoring service for detecting state changes and publishing events."""

import asyncio
from datetime import datetime
from typing import Optional

from .events import EventType, MonitoredSession, SessionEvent
from .terminal import TerminalService


class SessionMonitorService:
    """Service for monitoring session state changes and publishing events.

    Uses background asyncio tasks to poll sessions and detect state transitions.
    Events are published to an asyncio.Queue for consumption by the TUI.
    """

    def __init__(
        self,
        terminal_service: TerminalService,
        poll_interval: float = 1.0,
        max_events: int = 100,
    ) -> None:
        """Initialize monitor service.

        Args:
            terminal_service: Terminal service for session operations
            poll_interval: Seconds between status polls
            max_events: Maximum events to buffer in queue
        """
        self.terminal_service = terminal_service
        self.poll_interval = poll_interval

        self._event_queue: asyncio.Queue[SessionEvent] = asyncio.Queue(maxsize=max_events)
        self._monitored: dict[str, MonitoredSession] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def start_monitoring(self, session_id: str, address: str = "") -> bool:
        """Start monitoring a session.

        Args:
            session_id: Session to monitor
            address: Optional @project address for display

        Returns:
            True if monitoring started, False if already monitoring
        """
        if session_id in self._monitored:
            return False

        monitored = MonitoredSession(
            session_id=session_id,
            session_address=address or session_id[:20],
        )
        self._monitored[session_id] = monitored

        # Start background polling task
        task = asyncio.create_task(self._poll_session(session_id))
        self._tasks[session_id] = task

        return True

    async def stop_monitoring(self, session_id: str) -> bool:
        """Stop monitoring a session.

        Args:
            session_id: Session to stop monitoring

        Returns:
            True if stopped, False if not being monitored
        """
        if session_id not in self._monitored:
            return False

        # Cancel the background task
        task = self._tasks.get(session_id)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._tasks[session_id]

        del self._monitored[session_id]
        return True

    def is_monitoring(self, session_id: str) -> bool:
        """Check if a session is being monitored."""
        return session_id in self._monitored

    def get_monitored_sessions(self) -> list[str]:
        """Get list of session IDs being monitored."""
        return list(self._monitored.keys())

    async def get_events(self, max_events: int = 10) -> list[SessionEvent]:
        """Get pending events (non-blocking).

        Args:
            max_events: Maximum events to return

        Returns:
            List of pending events (oldest first)
        """
        events: list[SessionEvent] = []
        while len(events) < max_events:
            try:
                event = self._event_queue.get_nowait()
                events.append(event)
            except asyncio.QueueEmpty:
                break
        return events

    async def _poll_session(self, session_id: str) -> None:
        """Background task that polls a session and publishes events."""
        monitored = self._monitored.get(session_id)
        if not monitored:
            return

        while True:
            try:
                # Get current status from terminal service
                status = await self.terminal_service.get_session_status(session_id)
                monitored.last_poll = datetime.now()
                monitored.poll_count += 1

                # Detect state change
                event = self._detect_state_change(monitored, status)

                if event:
                    self._publish_event(event)

                # Update previous state
                monitored.previous_status = status.get("status", "unknown")
                monitored.previous_indicators = status.get("indicators", {}).copy()

                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Publish error event
                error_event = SessionEvent(
                    event_type=EventType.ERROR,
                    session_id=session_id,
                    session_address=monitored.session_address,
                    message=f"Monitoring error: {e}",
                )
                self._publish_event(error_event)
                await asyncio.sleep(self.poll_interval * 2)  # Back off on error

    def _detect_state_change(
        self,
        monitored: MonitoredSession,
        new_status: dict,
    ) -> Optional[SessionEvent]:
        """Detect state changes and create appropriate events."""
        new_state = new_status.get("status", "unknown")
        new_indicators = new_status.get("indicators", {})
        prev_indicators = monitored.previous_indicators

        # Detect INPUT_REQUIRED: transition to waiting_for_input
        if new_indicators.get("waiting_for_input") and not prev_indicators.get("waiting_for_input"):
            return SessionEvent(
                event_type=EventType.INPUT_REQUIRED,
                session_id=monitored.session_id,
                session_address=monitored.session_address,
                message="Waiting for input",
                details={"last_lines": new_status.get("last_lines", [])[-3:]},
            )

        # Detect OUTPUT_READY: transition from working/running to idle with prompt
        if (
            monitored.previous_status in ("working", "running", "unknown")
            and new_state == "idle"
            and new_indicators.get("has_prompt")
        ):
            return SessionEvent(
                event_type=EventType.OUTPUT_READY,
                session_id=monitored.session_id,
                session_address=monitored.session_address,
                message="Command completed",
                details={"screen_summary": new_status.get("screen_summary", "")},
            )

        # Generic state change (only if actual change)
        if new_state != monitored.previous_status and monitored.poll_count > 1:
            return SessionEvent(
                event_type=EventType.STATE_CHANGED,
                session_id=monitored.session_id,
                session_address=monitored.session_address,
                message=f"{monitored.previous_status} -> {new_state}",
            )

        return None

    def _publish_event(self, event: SessionEvent) -> None:
        """Publish event to queue, dropping oldest if full."""
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest event to make room
            try:
                self._event_queue.get_nowait()
                self._event_queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass

    async def shutdown(self) -> None:
        """Stop all monitoring and cleanup tasks."""
        for session_id in list(self._tasks.keys()):
            await self.stop_monitoring(session_id)
