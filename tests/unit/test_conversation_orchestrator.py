"""Tests for ConversationOrchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from terminator.services.conversation_orchestrator import (
    ConversationOrchestrator,
    ConversationResult,
    ConversationTurn,
)
from terminator.services.claude_code_detector import (
    ClaudeCodeDetector,
    ClaudeCodeState,
    DetectionResult,
)


@pytest.fixture
def mock_detector():
    """Create a mock Claude Code detector."""
    detector = MagicMock(spec=ClaudeCodeDetector)
    return detector


@pytest.fixture
def mock_send_command():
    """Create a mock send command function."""
    return AsyncMock()


@pytest.fixture
def mock_get_output():
    """Create a mock get output function."""
    return AsyncMock()


@pytest.fixture
def orchestrator(mock_detector, mock_send_command, mock_get_output):
    """Create a conversation orchestrator with mocks."""
    return ConversationOrchestrator(
        detector=mock_detector,
        send_command_fn=mock_send_command,
        get_output_fn=mock_get_output,
        ready_timeout=5.0,
        response_timeout=10.0,
    )


class TestWaitForSessionReady:
    """Tests for wait_for_session_ready method."""

    @pytest.mark.asyncio
    async def test_wait_for_session_ready_success(self, orchestrator, mock_detector):
        """Test successful wait for session ready."""
        # Setup: detector returns ready state
        ready_result = DetectionResult(
            state=ClaudeCodeState.READY,
            confidence=0.9,
            raw_output="> ",
            matched_pattern=r"^\s*>\s*$",
        )
        mock_detector.wait_for_ready = AsyncMock(return_value=ready_result)

        # Execute
        result = await orchestrator.wait_for_session_ready("tmux:session-1")

        # Verify
        assert result.state == ClaudeCodeState.READY
        assert result.confidence == 0.9
        mock_detector.wait_for_ready.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_session_ready_timeout(self, orchestrator, mock_detector):
        """Test timeout when waiting for session ready."""
        # Setup: detector times out
        mock_detector.wait_for_ready = AsyncMock(
            side_effect=TimeoutError("Session did not become ready")
        )

        # Execute & Verify
        with pytest.raises(TimeoutError):
            await orchestrator.wait_for_session_ready("tmux:session-1")


class TestSendAndWaitForResponse:
    """Tests for send_and_wait_for_response method."""

    @pytest.mark.asyncio
    async def test_send_and_wait_success(
        self, orchestrator, mock_send_command, mock_get_output, mock_detector
    ):
        """Test successful send and wait for response."""
        # Setup
        mock_detector.wait_for_response_complete = AsyncMock()
        mock_get_output.return_value = "Claude response here"

        # Execute
        response, response_time = await orchestrator.send_and_wait_for_response(
            "tmux:session-1", "Hello Claude"
        )

        # Verify
        assert response == "Claude response here"
        assert response_time >= 0.0
        mock_send_command.assert_called_once_with("tmux:session-1", "Hello Claude")
        mock_detector.wait_for_response_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_and_wait_timeout(
        self, orchestrator, mock_send_command, mock_detector
    ):
        """Test timeout when waiting for response."""
        # Setup: response never completes
        mock_detector.wait_for_response_complete = AsyncMock(
            side_effect=TimeoutError("Response did not complete")
        )

        # Execute & Verify
        with pytest.raises(TimeoutError):
            await orchestrator.send_and_wait_for_response(
                "tmux:session-1", "Hello Claude"
            )


class TestRunConversation:
    """Tests for run_conversation method."""

    @pytest.mark.asyncio
    async def test_run_conversation_single_turn_success(
        self, orchestrator, mock_detector, mock_send_command, mock_get_output
    ):
        """Test successful single-turn conversation."""
        # Setup
        mock_detector.wait_for_ready = AsyncMock(
            return_value=DetectionResult(
                state=ClaudeCodeState.READY,
                confidence=0.9,
                raw_output="> ",
            )
        )
        mock_detector.wait_for_response_complete = AsyncMock()
        mock_get_output.return_value = "Response from Claude"

        # Execute
        result = await orchestrator.run_conversation(
            session_id="tmux:session-1",
            initial_message="Test message",
            max_turns=1,
        )

        # Verify
        assert result.success is True
        assert result.error is None
        assert len(result.turns) == 1
        assert result.turns[0].speaker == "tmux:session-1"
        assert result.turns[0].message == "Test message"
        assert result.turns[0].response == "Response from Claude"
        assert result.total_time >= 0.0

    @pytest.mark.asyncio
    async def test_run_conversation_ready_timeout(self, orchestrator, mock_detector):
        """Test conversation fails when session doesn't become ready."""
        # Setup: session never becomes ready
        mock_detector.wait_for_ready = AsyncMock(
            side_effect=TimeoutError("Session did not become ready")
        )

        # Execute
        result = await orchestrator.run_conversation(
            session_id="tmux:session-1",
            initial_message="Test message",
            max_turns=1,
        )

        # Verify
        assert result.success is False
        assert "did not become ready" in result.error
        assert len(result.turns) == 0

    @pytest.mark.asyncio
    async def test_run_conversation_response_timeout(
        self, orchestrator, mock_detector, mock_send_command
    ):
        """Test conversation fails when response times out."""
        # Setup: session ready but response times out
        mock_detector.wait_for_ready = AsyncMock(
            return_value=DetectionResult(
                state=ClaudeCodeState.READY,
                confidence=0.9,
                raw_output="> ",
            )
        )
        mock_detector.wait_for_response_complete = AsyncMock(
            side_effect=TimeoutError("Response did not complete")
        )

        # Execute
        result = await orchestrator.run_conversation(
            session_id="tmux:session-1",
            initial_message="Test message",
            max_turns=1,
        )

        # Verify
        assert result.success is False
        assert "did not complete" in result.error
        assert len(result.turns) == 0

    @pytest.mark.asyncio
    async def test_run_conversation_general_exception(
        self, orchestrator, mock_detector
    ):
        """Test conversation handles general exceptions."""
        # Setup: unexpected exception
        mock_detector.wait_for_ready = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        # Execute
        result = await orchestrator.run_conversation(
            session_id="tmux:session-1",
            initial_message="Test message",
            max_turns=1,
        )

        # Verify
        assert result.success is False
        assert "Unexpected error" in result.error
        assert len(result.turns) == 0


class TestRelayBetweenSessions:
    """Tests for relay_between_sessions method."""

    @pytest.mark.asyncio
    async def test_relay_success_single_cycle(
        self, orchestrator, mock_detector, mock_send_command, mock_get_output
    ):
        """Test successful single relay cycle between sessions."""
        # Setup
        mock_detector.wait_for_ready = AsyncMock(
            return_value=DetectionResult(
                state=ClaudeCodeState.READY,
                confidence=0.9,
                raw_output="> ",
            )
        )
        mock_detector.wait_for_response_complete = AsyncMock()

        # Mock different responses for target and source
        responses = ["Target response", "Source response"]
        mock_get_output.side_effect = responses

        # Execute
        result = await orchestrator.relay_between_sessions(
            source_session="tmux:source",
            target_session="tmux:target",
            initial_message="Initial message",
            max_turns=1,
        )

        # Verify
        assert result.success is True
        assert result.error is None
        assert len(result.turns) == 2  # One turn per session

        # First turn: message to target
        assert result.turns[0].speaker == "tmux:target"
        assert result.turns[0].message == "Initial message"
        assert result.turns[0].response == "Target response"

        # Second turn: relayed response to source
        assert result.turns[1].speaker == "tmux:source"
        assert "Response from @tmux:target" in result.turns[1].message
        assert result.turns[1].response == "Source response"

        # Verify both sessions were checked for ready
        assert mock_detector.wait_for_ready.call_count == 2

        # Verify commands sent to both sessions
        assert mock_send_command.call_count == 2

    @pytest.mark.asyncio
    async def test_relay_target_not_ready(self, orchestrator, mock_detector):
        """Test relay fails when target session not ready."""
        # Setup: source ready, target times out
        ready_result = DetectionResult(
            state=ClaudeCodeState.READY,
            confidence=0.9,
            raw_output="> ",
        )

        async def wait_for_ready_side_effect(get_output_fn, timeout=None):
            # First call (source) succeeds, second (target) fails
            if not hasattr(wait_for_ready_side_effect, "called"):
                wait_for_ready_side_effect.called = True
                return ready_result
            raise TimeoutError("Target not ready")

        mock_detector.wait_for_ready = AsyncMock(side_effect=wait_for_ready_side_effect)

        # Execute
        result = await orchestrator.relay_between_sessions(
            source_session="tmux:source",
            target_session="tmux:target",
            initial_message="Initial message",
            max_turns=1,
        )

        # Verify
        assert result.success is False
        assert "Target not ready" in result.error
        assert len(result.turns) == 0

    @pytest.mark.asyncio
    async def test_relay_target_response_timeout(
        self, orchestrator, mock_detector, mock_send_command
    ):
        """Test relay fails when target response times out."""
        # Setup: both sessions ready, but target response times out
        mock_detector.wait_for_ready = AsyncMock(
            return_value=DetectionResult(
                state=ClaudeCodeState.READY,
                confidence=0.9,
                raw_output="> ",
            )
        )
        mock_detector.wait_for_response_complete = AsyncMock(
            side_effect=TimeoutError("Response timed out")
        )

        # Execute
        result = await orchestrator.relay_between_sessions(
            source_session="tmux:source",
            target_session="tmux:target",
            initial_message="Initial message",
            max_turns=1,
        )

        # Verify
        assert result.success is False
        assert "timed out" in result.error
        assert len(result.turns) == 0

    @pytest.mark.asyncio
    async def test_relay_truncates_long_messages(
        self, orchestrator, mock_detector, mock_send_command, mock_get_output
    ):
        """Test relay truncates long messages in turn history."""
        # Setup
        mock_detector.wait_for_ready = AsyncMock(
            return_value=DetectionResult(
                state=ClaudeCodeState.READY,
                confidence=0.9,
                raw_output="> ",
            )
        )
        mock_detector.wait_for_response_complete = AsyncMock()

        # Create a long response (> 2000 chars for response, > 500 for message)
        long_target_response = "x" * 3000
        source_response = "Source ack"

        mock_get_output.side_effect = [long_target_response, source_response]

        # Execute
        result = await orchestrator.relay_between_sessions(
            source_session="tmux:source",
            target_session="tmux:target",
            initial_message="Initial message",
            max_turns=1,
        )

        # Verify
        assert result.success is True

        # Target turn should have full response
        assert len(result.turns[0].response) == 3000

        # Source turn message should be truncated (relay_message[:500] + "...")
        # Relay message format: "Response from @{target}:\n\n{response[-2000:]}"
        # So it's "Response from @tmux:target:\n\n" + last 2000 chars
        # Then truncated to 500 + "..."
        assert "..." in result.turns[1].message
        assert len(result.turns[1].message) <= 504  # 500 + "..."


class TestConversationResultDataclass:
    """Tests for ConversationResult dataclass."""

    def test_conversation_result_defaults(self):
        """Test ConversationResult default values."""
        result = ConversationResult(
            turns=[],
            success=True,
        )

        assert result.turns == []
        assert result.success is True
        assert result.error is None
        assert result.total_time == 0.0

    def test_conversation_result_with_error(self):
        """Test ConversationResult with error."""
        result = ConversationResult(
            turns=[],
            success=False,
            error="Something failed",
            total_time=1.5,
        )

        assert result.success is False
        assert result.error == "Something failed"
        assert result.total_time == 1.5


class TestConversationTurnDataclass:
    """Tests for ConversationTurn dataclass."""

    def test_conversation_turn_creation(self):
        """Test ConversationTurn creation."""
        turn = ConversationTurn(
            speaker="tmux:session-1",
            message="Hello",
            response="World",
            response_time=0.5,
        )

        assert turn.speaker == "tmux:session-1"
        assert turn.message == "Hello"
        assert turn.response == "World"
        assert turn.response_time == 0.5
