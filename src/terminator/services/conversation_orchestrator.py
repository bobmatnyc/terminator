"""Conversation orchestrator for two-way Claude Code communication."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from terminator.services.claude_code_detector import (
    ClaudeCodeDetector,
    DetectionResult,
)

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    speaker: str  # Session name/address
    message: str
    response: str
    response_time: float  # seconds


@dataclass
class ConversationResult:
    """Result of a conversation."""

    turns: list[ConversationTurn]
    success: bool
    error: str | None = None
    total_time: float = 0.0


class ConversationOrchestrator:
    """Orchestrates conversations between Claude Code sessions."""

    def __init__(
        self,
        detector: ClaudeCodeDetector,
        send_command_fn: Callable[[str, str], Awaitable[None]],
        get_output_fn: Callable[[str, int], Awaitable[str]],
        ready_timeout: float = 60.0,
        response_timeout: float = 300.0,
    ):
        """Initialize orchestrator.

        Args:
            detector: Claude Code detector instance
            send_command_fn: async fn(session_id, command) -> None
            get_output_fn: async fn(session_id, lines) -> str
            ready_timeout: Seconds to wait for Claude to be ready
            response_timeout: Seconds to wait for response completion
        """
        self.detector = detector
        self.send_command = send_command_fn
        self.get_output = get_output_fn
        self.ready_timeout = ready_timeout
        self.response_timeout = response_timeout

    async def wait_for_session_ready(self, session_id: str) -> DetectionResult:
        """Wait for a Claude Code session to be ready for input.

        Args:
            session_id: Session to wait for

        Returns:
            DetectionResult when session is ready

        Raises:
            TimeoutError: If session doesn't become ready within timeout
        """

        async def get_output() -> str:
            return await self.get_output(session_id, 100)

        return await self.detector.wait_for_ready(get_output, timeout=self.ready_timeout)

    async def send_and_wait_for_response(
        self,
        session_id: str,
        message: str,
    ) -> tuple[str, float]:
        """Send message and wait for complete response.

        Args:
            session_id: Target session
            message: Message to send

        Returns:
            Tuple of (response_text, response_time_seconds)

        Raises:
            TimeoutError: If response doesn't complete within timeout
        """
        start_time = asyncio.get_event_loop().time()

        # Send the message
        await self.send_command(session_id, message)

        # Wait for response to complete
        async def get_output() -> str:
            return await self.get_output(session_id, 200)

        await self.detector.wait_for_response_complete(
            get_output,
            timeout=self.response_timeout,
        )

        # Get final output
        response = await self.get_output(session_id, 500)
        elapsed = asyncio.get_event_loop().time() - start_time

        return response, elapsed

    async def run_conversation(
        self,
        session_id: str,
        initial_message: str,
        max_turns: int = 1,
    ) -> ConversationResult:
        """Run a conversation with a single Claude Code session.

        Args:
            session_id: Target session
            initial_message: First message to send
            max_turns: Maximum conversation turns

        Returns:
            ConversationResult with turns and success status
        """
        turns: list[ConversationTurn] = []
        start_time = asyncio.get_event_loop().time()

        try:
            # Wait for session to be ready
            logger.info(f"Waiting for session {session_id} to be ready...")
            await self.wait_for_session_ready(session_id)
            logger.info(f"Session {session_id} is ready")

            # Send initial message
            message = initial_message
            for turn_num in range(max_turns):
                logger.info(f"Turn {turn_num + 1}: Sending message to {session_id}")

                response, response_time = await self.send_and_wait_for_response(
                    session_id,
                    message,
                )

                turns.append(
                    ConversationTurn(
                        speaker=session_id,
                        message=message,
                        response=response,
                        response_time=response_time,
                    )
                )

                logger.info(f"Turn {turn_num + 1} complete ({response_time:.1f}s)")

                # For multi-turn, could parse response for next message
                # For now, just do single turns
                break

            total_time = asyncio.get_event_loop().time() - start_time
            return ConversationResult(
                turns=turns,
                success=True,
                total_time=total_time,
            )

        except TimeoutError as e:
            total_time = asyncio.get_event_loop().time() - start_time
            return ConversationResult(
                turns=turns,
                success=False,
                error=str(e),
                total_time=total_time,
            )
        except Exception as e:
            total_time = asyncio.get_event_loop().time() - start_time
            logger.exception(f"Conversation failed: {e}")
            return ConversationResult(
                turns=turns,
                success=False,
                error=str(e),
                total_time=total_time,
            )

    async def relay_between_sessions(
        self,
        source_session: str,
        target_session: str,
        initial_message: str,
        max_turns: int = 3,
    ) -> ConversationResult:
        """Relay messages between two Claude Code sessions.

        This is the core two-way meta-communication feature:
        1. Send initial_message to target_session
        2. Get response from target_session
        3. Forward response to source_session
        4. Repeat for max_turns

        Args:
            source_session: The "tester" session
            target_session: The session being tested
            initial_message: First message to send to target
            max_turns: Max relay cycles

        Returns:
            ConversationResult with turns from both sessions
        """
        turns: list[ConversationTurn] = []
        start_time = asyncio.get_event_loop().time()

        try:
            # Ensure both sessions are ready
            logger.info("Waiting for both sessions to be ready...")
            await asyncio.gather(
                self.wait_for_session_ready(source_session),
                self.wait_for_session_ready(target_session),
            )
            logger.info("Both sessions ready")

            message = initial_message

            for turn_num in range(max_turns):
                # Send to target, get response
                logger.info(f"Turn {turn_num + 1}: Sending to {target_session}")
                target_response, target_time = await self.send_and_wait_for_response(
                    target_session,
                    message,
                )

                turns.append(
                    ConversationTurn(
                        speaker=target_session,
                        message=message,
                        response=target_response,
                        response_time=target_time,
                    )
                )

                # Relay to source (formatting the response)
                relay_message = (
                    f"Response from @{target_session}:\n\n{target_response[-2000:]}"
                )
                logger.info(f"Turn {turn_num + 1}: Relaying to {source_session}")

                source_response, source_time = await self.send_and_wait_for_response(
                    source_session,
                    relay_message,
                )

                turns.append(
                    ConversationTurn(
                        speaker=source_session,
                        message=(
                            relay_message[:500] + "..."
                            if len(relay_message) > 500
                            else relay_message
                        ),
                        response=source_response,
                        response_time=source_time,
                    )
                )

                # Could parse source_response for follow-up message
                # For now, end after one cycle
                break

            total_time = asyncio.get_event_loop().time() - start_time
            return ConversationResult(
                turns=turns,
                success=True,
                total_time=total_time,
            )

        except TimeoutError as e:
            total_time = asyncio.get_event_loop().time() - start_time
            return ConversationResult(
                turns=turns,
                success=False,
                error=str(e),
                total_time=total_time,
            )
        except Exception as e:
            total_time = asyncio.get_event_loop().time() - start_time
            logger.exception(f"Relay conversation failed: {e}")
            return ConversationResult(
                turns=turns,
                success=False,
                error=str(e),
                total_time=total_time,
            )
