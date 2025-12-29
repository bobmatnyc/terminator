"""Integration tests for @project addressing throughout the system.

Tests the full flow from CLI/chatbot -> TerminalService -> ProjectRegistry -> session resolution.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from terminator.adapters.protocols import (
    UnifiedSession,
    TerminalType,
    SessionState,
    CommandResult,
    InstanceType,
)
from terminator.services.terminal import TerminalService
from terminator.services.project_registry import ProjectRegistry
from terminator.services.instance_detector import InstanceDetector
from terminator.adapters.iterm2 import ITerm2Adapter
from terminator.adapters.tmux import TmuxAdapter


@pytest.fixture
def mock_iterm2_adapter() -> Mock:
    """Create mock iTerm2 adapter."""
    adapter = Mock(spec=ITerm2Adapter)
    adapter.connect = AsyncMock(return_value=False)  # Not available in tests
    adapter.list_sessions = AsyncMock(return_value=[])
    return adapter


@pytest.fixture
def mock_tmux_adapter() -> Mock:
    """Create mock tmux adapter with test sessions."""
    adapter = Mock(spec=TmuxAdapter)
    adapter.connect = AsyncMock(return_value=True)

    # Create test sessions
    sessions = [
        UnifiedSession(
            id="tmux:mcp-ticketer:0:0",
            name="mcp-ticketer",
            terminal_type=TerminalType.TMUX,
            cwd="/Users/test/Projects/mcp-ticketer",
            state=SessionState.IDLE,
            instance_type=InstanceType.UNKNOWN,  # Will be detected
        ),
        UnifiedSession(
            id="tmux:mcp-ticketer:1:0",
            name="mcp-ticketer",
            terminal_type=TerminalType.TMUX,
            cwd="/Users/test/Projects/mcp-ticketer",
            state=SessionState.IDLE,
            instance_type=InstanceType.UNKNOWN,  # Will be detected
        ),
        UnifiedSession(
            id="tmux:terminator:0:0",
            name="terminator",
            terminal_type=TerminalType.TMUX,
            cwd="/Users/test/Projects/terminator",
            state=SessionState.IDLE,
            instance_type=InstanceType.UNKNOWN,  # Will be detected
        ),
    ]

    adapter.list_sessions = AsyncMock(return_value=sessions)

    # Return different outputs for instance detection
    def get_session_output_side_effect(session_id: str, lines: int = 50) -> str:
        if session_id == "tmux:mcp-ticketer:0:0":
            return "Claude Code v1.0.0\nWelcome to Claude Code\n>>> "
        elif session_id == "tmux:mcp-ticketer:1:0":
            return "Auggie - Augment Code Assistant\naugment> "
        else:
            return "$ Test output"

    adapter.get_session_output = AsyncMock(side_effect=get_session_output_side_effect)
    adapter.send_command = AsyncMock(
        return_value=CommandResult(
            success=True,
            output="Command executed",
            state_after=SessionState.IDLE,
            execution_time=0.5,
        )
    )
    adapter.detect_state = AsyncMock(return_value=SessionState.IDLE)
    adapter.get_session_status = AsyncMock(
        return_value={
            "is_working": False,
            "status": "idle",
            "screen_summary": "Session is idle",
            "last_lines": ["$ "],
            "indicators": {},
        }
    )

    return adapter


@pytest.fixture
def project_registry() -> ProjectRegistry:
    """Create project registry for testing."""
    import tempfile
    from pathlib import Path

    temp_dir = Path(tempfile.mkdtemp())
    registry = ProjectRegistry(registry_path=temp_dir / "test_projects.json")
    return registry


@pytest.fixture
def instance_detector() -> InstanceDetector:
    """Create instance detector for testing."""
    return InstanceDetector()


@pytest.fixture
async def terminal_service(
    mock_iterm2_adapter: Mock,
    mock_tmux_adapter: Mock,
    project_registry: ProjectRegistry,
    instance_detector: InstanceDetector,
) -> TerminalService:
    """Create terminal service with mock adapters."""
    service = TerminalService(
        iterm2_adapter=mock_iterm2_adapter,
        tmux_adapter=mock_tmux_adapter,
        project_registry=project_registry,
        instance_detector=instance_detector,
    )

    # Connect to backends
    await service.connect_all()

    return service


@pytest.mark.asyncio
class TestProjectAddressing:
    """Test @project addressing integration."""

    async def test_list_sessions_registers_projects(
        self, terminal_service: TerminalService
    ):
        """Test that listing sessions auto-registers projects."""
        sessions = await terminal_service.list_all_sessions()

        # Verify sessions returned
        assert len(sessions) == 3

        # Verify projects registered
        projects = await terminal_service.project_registry.list_projects()
        assert "mcp-ticketer" in projects
        assert "terminator" in projects

        # Verify addresses assigned
        mcp_sessions = projects["mcp-ticketer"]
        assert len(mcp_sessions) == 2
        assert mcp_sessions[0].address == "@mcp-ticketer"
        assert mcp_sessions[1].address == "@mcp-ticketer:2"

        terminator_sessions = projects["terminator"]
        assert len(terminator_sessions) == 1
        assert terminator_sessions[0].address == "@terminator"

    async def test_list_sessions_detects_instance_types(
        self, terminal_service: TerminalService
    ):
        """Test that listing sessions detects instance types."""
        sessions = await terminal_service.list_all_sessions()

        # Find sessions by ID
        session_map = {s.id: s for s in sessions}

        # Verify instance types detected (from mock data)
        assert (
            session_map["tmux:mcp-ticketer:0:0"].instance_type
            == InstanceType.CLAUDE_CODE
        )
        assert (
            session_map["tmux:mcp-ticketer:1:0"].instance_type == InstanceType.AUGGIE
        )
        assert (
            session_map["tmux:terminator:0:0"].instance_type == InstanceType.SHELL
        )

    async def test_send_command_with_project_address(
        self, terminal_service: TerminalService
    ):
        """Test sending command using @project address."""
        # First, list sessions to register projects
        await terminal_service.list_all_sessions()

        # Send command using @project address
        result = await terminal_service.send_command(
            "@mcp-ticketer", "run tests", wait_for_completion=True
        )

        # Verify command executed successfully
        assert result.success
        assert result.output == "Command executed"

        # Verify adapter called with correct session ID
        terminal_service.tmux.send_command.assert_called_once()
        call_args = terminal_service.tmux.send_command.call_args
        assert call_args[0][0] == "tmux:mcp-ticketer:0:0"  # Resolved session ID
        assert call_args[0][1] == "run tests"

    async def test_send_command_with_numbered_address(
        self, terminal_service: TerminalService
    ):
        """Test sending command to second instance using @project:2."""
        # First, list sessions to register projects
        await terminal_service.list_all_sessions()

        # Send command using @project:2 address
        result = await terminal_service.send_command(
            "@mcp-ticketer:2", "run build", wait_for_completion=True
        )

        # Verify command executed successfully
        assert result.success

        # Verify adapter called with correct session ID (second instance)
        terminal_service.tmux.send_command.assert_called_once()
        call_args = terminal_service.tmux.send_command.call_args
        assert call_args[0][0] == "tmux:mcp-ticketer:1:0"  # Second session

    async def test_get_session_output_with_project_address(
        self, terminal_service: TerminalService
    ):
        """Test reading session output using @project address."""
        # First, list sessions to register projects
        await terminal_service.list_all_sessions()

        # Reset mock to clear detection calls
        terminal_service.tmux.get_session_output.reset_mock()

        # Get output using @project address
        output = await terminal_service.get_session_output("@terminator", lines=50)

        # Verify output retrieved
        assert "Test output" in output

        # Verify adapter called with correct session ID
        terminal_service.tmux.get_session_output.assert_called_once()
        call_args = terminal_service.tmux.get_session_output.call_args
        assert call_args[0][0] == "tmux:terminator:0:0"

    async def test_resolve_nonexistent_project(
        self, terminal_service: TerminalService
    ):
        """Test resolving non-existent @project returns error."""
        # First, list sessions to register projects
        await terminal_service.list_all_sessions()

        # Try to send command to non-existent project
        result = await terminal_service.send_command(
            "@nonexistent", "test", wait_for_completion=True
        )

        # Verify error returned
        assert not result.success
        assert "not found" in result.output.lower()

    async def test_detect_state_with_project_address(
        self, terminal_service: TerminalService
    ):
        """Test detecting session state using @project address."""
        # First, list sessions to register projects
        await terminal_service.list_all_sessions()

        # Detect state using @project address
        state = await terminal_service.detect_state("@mcp-ticketer")

        # Verify state detected
        assert state == SessionState.IDLE

        # Verify adapter called with correct session ID
        terminal_service.tmux.detect_state.assert_called_once()
        call_args = terminal_service.tmux.detect_state.call_args
        assert call_args[0][0] == "tmux:mcp-ticketer:0:0"

    async def test_get_session_status_with_project_address(
        self, terminal_service: TerminalService
    ):
        """Test getting session status using @project address."""
        # First, list sessions to register projects
        await terminal_service.list_all_sessions()

        # Get status using @project address
        status = await terminal_service.get_session_status("@terminator")

        # Verify status retrieved
        assert status["status"] == "idle"
        assert not status["is_working"]

        # Verify adapter called with correct session ID
        terminal_service.tmux.get_session_status.assert_called_once()
        call_args = terminal_service.tmux.get_session_status.call_args
        assert call_args[0][0] == "tmux:terminator:0:0"

    async def test_raw_session_id_still_works(
        self, terminal_service: TerminalService
    ):
        """Test that raw session IDs still work alongside @project addressing."""
        # First, list sessions to register projects
        await terminal_service.list_all_sessions()

        # Send command using raw session ID
        result = await terminal_service.send_command(
            "tmux:mcp-ticketer:0:0", "test", wait_for_completion=True
        )

        # Verify command executed successfully
        assert result.success

        # Verify adapter called with same session ID (no resolution needed)
        terminal_service.tmux.send_command.assert_called_once()
        call_args = terminal_service.tmux.send_command.call_args
        assert call_args[0][0] == "tmux:mcp-ticketer:0:0"

    async def test_project_registry_persistence(
        self, terminal_service: TerminalService
    ):
        """Test that project registry persists across instances."""
        # First, list sessions to register projects
        await terminal_service.list_all_sessions()

        # Get initial projects
        projects_before = await terminal_service.project_registry.list_projects()
        assert "mcp-ticketer" in projects_before

        # Create new registry with same file path
        new_registry = ProjectRegistry(
            registry_path=terminal_service.project_registry._registry_path
        )

        # Verify projects loaded from disk
        projects_after = await new_registry.list_projects()
        assert "mcp-ticketer" in projects_after
        assert len(projects_after["mcp-ticketer"]) == 2


@pytest.mark.asyncio
class TestChatbotIntegration:
    """Test chatbot integration with @project addressing."""

    async def test_list_sessions_includes_addresses(
        self, terminal_service: TerminalService
    ):
        """Test that chatbot list_sessions tool includes @project addresses."""
        from terminator.chat.chatbot import TerminalChatbot
        from terminator.services.llm import LLMService

        # Create mock LLM service
        llm_service = Mock(spec=LLMService)

        # Create chatbot
        chatbot = TerminalChatbot(
            llm_service=llm_service, terminal_service=terminal_service
        )

        # First, list sessions to register projects
        await terminal_service.list_all_sessions()

        # Execute list_sessions tool
        from terminator.services.llm import ToolCall

        tool_call = ToolCall(id="test", name="list_sessions", arguments={})
        result_json = await chatbot.execute_tool(tool_call)

        # Parse result
        import json

        result = json.loads(result_json)

        # Verify addresses included
        assert result["count"] == 3

        sessions = result["sessions"]
        session_map = {s["id"]: s for s in sessions}

        # Verify @project addresses
        assert session_map["tmux:mcp-ticketer:0:0"]["address"] == "@mcp-ticketer"
        assert session_map["tmux:mcp-ticketer:1:0"]["address"] == "@mcp-ticketer:2"
        assert session_map["tmux:terminator:0:0"]["address"] == "@terminator"

        # Verify instance types included
        assert (
            session_map["tmux:mcp-ticketer:0:0"]["instance_type"] == "claude-code"
        )
        assert session_map["tmux:mcp-ticketer:1:0"]["instance_type"] == "auggie"
        assert session_map["tmux:terminator:0:0"]["instance_type"] == "shell"
