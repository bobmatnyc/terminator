"""Unit tests for ProjectRegistry service."""

import json
from pathlib import Path
from typing import Generator

import pytest

from termpilot.adapters.protocols import SessionState, TerminalType, UnifiedSession
from termpilot.services.project_registry import ProjectRegistry, ProjectSession


@pytest.fixture
def temp_registry_path(tmp_path: Path) -> Path:
    """Create temporary registry file path."""
    return tmp_path / "test_projects.json"


@pytest.fixture
def registry(temp_registry_path: Path) -> Generator[ProjectRegistry, None, None]:
    """Create ProjectRegistry instance with temp path."""
    reg = ProjectRegistry(registry_path=temp_registry_path)
    yield reg


@pytest.fixture
def sample_sessions() -> list[UnifiedSession]:
    """Create sample sessions for testing."""
    return [
        UnifiedSession(
            id="tmux:mcp-ticketer:0:0",
            name="mcp-ticketer",
            terminal_type=TerminalType.TMUX,
            state=SessionState.IDLE,
            cwd="/Users/masa/Projects/mcp-ticketer",
        ),
        UnifiedSession(
            id="tmux:mcp-ticketer:0:1",
            name="mcp-ticketer-2",
            terminal_type=TerminalType.TMUX,
            state=SessionState.IDLE,
            cwd="/Users/masa/Projects/mcp-ticketer",
        ),
        UnifiedSession(
            id="iterm2:terminator:abc123",
            name="terminator",
            terminal_type=TerminalType.ITERM2,
            state=SessionState.IDLE,
            cwd="/Users/masa/Projects/terminator",
        ),
        UnifiedSession(
            id="tmux:no-cwd:0:0",
            name="no-cwd",
            terminal_type=TerminalType.TMUX,
            state=SessionState.IDLE,
            cwd="",
        ),
    ]


class TestProjectRegistryBasics:
    """Test basic ProjectRegistry functionality."""

    @pytest.mark.asyncio
    async def test_register_first_session(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test registering first session for a project."""
        session = sample_sessions[0]
        address = await registry.register_session(session)

        assert address == "@mcp-ticketer"

        # Verify registry state
        projects = await registry.list_projects()
        assert "mcp-ticketer" in projects
        assert len(projects["mcp-ticketer"]) == 1

        ps = projects["mcp-ticketer"][0]
        assert ps.address == "@mcp-ticketer"
        assert ps.session_id == session.id
        assert ps.project_name == "mcp-ticketer"
        assert ps.project_path == session.cwd
        assert ps.terminal_backend == "tmux"

    @pytest.mark.asyncio
    async def test_register_multiple_sessions_same_project(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test registering multiple sessions for same project."""
        # Register first session
        addr1 = await registry.register_session(sample_sessions[0])
        assert addr1 == "@mcp-ticketer"

        # Register second session
        addr2 = await registry.register_session(sample_sessions[1])
        assert addr2 == "@mcp-ticketer:2"

        # Verify both sessions registered
        projects = await registry.list_projects()
        assert len(projects["mcp-ticketer"]) == 2

    @pytest.mark.asyncio
    async def test_register_session_no_cwd(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test registering session without CWD returns empty string."""
        session = sample_sessions[3]  # no-cwd session
        address = await registry.register_session(session)

        assert address == ""

        # Verify not added to registry
        projects = await registry.list_projects()
        assert len(projects) == 0

    @pytest.mark.asyncio
    async def test_register_session_idempotent(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test re-registering same session returns same address."""
        session = sample_sessions[0]

        addr1 = await registry.register_session(session)
        addr2 = await registry.register_session(session)

        assert addr1 == addr2 == "@mcp-ticketer"

        # Verify only one entry
        projects = await registry.list_projects()
        assert len(projects["mcp-ticketer"]) == 1

    @pytest.mark.asyncio
    async def test_register_different_projects(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test registering sessions from different projects."""
        addr1 = await registry.register_session(sample_sessions[0])
        addr2 = await registry.register_session(sample_sessions[2])

        assert addr1 == "@mcp-ticketer"
        assert addr2 == "@terminator"

        projects = await registry.list_projects()
        assert len(projects) == 2
        assert "mcp-ticketer" in projects
        assert "terminator" in projects


class TestProjectRegistryResolution:
    """Test address resolution."""

    @pytest.mark.asyncio
    async def test_resolve_primary_session(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test resolving @project to first session."""
        session = sample_sessions[0]
        await registry.register_session(session)

        resolved = await registry.resolve("@mcp-ticketer")
        assert resolved == session.id

    @pytest.mark.asyncio
    async def test_resolve_numbered_session(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test resolving @project:2 to second session."""
        await registry.register_session(sample_sessions[0])
        await registry.register_session(sample_sessions[1])

        resolved1 = await registry.resolve("@mcp-ticketer:1")
        resolved2 = await registry.resolve("@mcp-ticketer:2")

        assert resolved1 == sample_sessions[0].id
        assert resolved2 == sample_sessions[1].id

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_project(self, registry: ProjectRegistry) -> None:
        """Test resolving non-existent project returns None."""
        resolved = await registry.resolve("@nonexistent")
        assert resolved is None

    @pytest.mark.asyncio
    async def test_resolve_invalid_instance_number(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test resolving invalid instance number returns None."""
        await registry.register_session(sample_sessions[0])

        # Instance 0 doesn't exist (starts at 1)
        assert await registry.resolve("@mcp-ticketer:0") is None

        # Instance 2 doesn't exist (only 1 session)
        assert await registry.resolve("@mcp-ticketer:2") is None

    @pytest.mark.asyncio
    async def test_resolve_invalid_address_format(self, registry: ProjectRegistry) -> None:
        """Test resolving invalid address format returns None."""
        # No @ prefix
        assert await registry.resolve("mcp-ticketer") is None

        # Invalid instance (not a number)
        assert await registry.resolve("@mcp-ticketer:abc") is None


class TestProjectRegistryUnregister:
    """Test session unregistration."""

    @pytest.mark.asyncio
    async def test_unregister_session(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test unregistering a session."""
        session = sample_sessions[0]
        await registry.register_session(session)

        await registry.unregister_session(session.id)

        # Verify removed
        projects = await registry.list_projects()
        assert len(projects) == 0

        # Verify resolution fails
        resolved = await registry.resolve("@mcp-ticketer")
        assert resolved is None

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_session(self, registry: ProjectRegistry) -> None:
        """Test unregistering non-existent session is safe."""
        await registry.unregister_session("nonexistent-session-id")
        # Should not raise, registry should be empty
        projects = await registry.list_projects()
        assert len(projects) == 0

    @pytest.mark.asyncio
    async def test_unregister_renumbers_sessions(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test removing middle session renumbers remaining sessions."""
        # Register 3 sessions
        await registry.register_session(sample_sessions[0])
        await registry.register_session(sample_sessions[1])

        # Create third session
        session3 = UnifiedSession(
            id="tmux:mcp-ticketer:0:2",
            name="mcp-ticketer-3",
            terminal_type=TerminalType.TMUX,
            state=SessionState.IDLE,
            cwd="/Users/masa/Projects/mcp-ticketer",
        )
        await registry.register_session(session3)

        # Remove second session
        await registry.unregister_session(sample_sessions[1].id)

        # Verify renumbering
        projects = await registry.list_projects()
        sessions = projects["mcp-ticketer"]
        assert len(sessions) == 2
        assert sessions[0].address == "@mcp-ticketer"
        assert sessions[1].address == "@mcp-ticketer:2"

        # Verify resolution still works
        assert await registry.resolve("@mcp-ticketer") == sample_sessions[0].id
        assert await registry.resolve("@mcp-ticketer:2") == session3.id


class TestProjectRegistryRefresh:
    """Test registry refresh functionality."""

    @pytest.mark.asyncio
    async def test_refresh_removes_stale_sessions(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test refresh removes sessions no longer active."""
        # Register two sessions
        await registry.register_session(sample_sessions[0])
        await registry.register_session(sample_sessions[1])

        # Refresh with only first session
        await registry.refresh_all([sample_sessions[0]])

        # Verify second session removed
        projects = await registry.list_projects()
        assert len(projects["mcp-ticketer"]) == 1
        assert projects["mcp-ticketer"][0].session_id == sample_sessions[0].id

    @pytest.mark.asyncio
    async def test_refresh_registers_new_sessions(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test refresh registers new sessions."""
        # Start with empty registry
        await registry.refresh_all(sample_sessions[:2])

        # Verify both registered
        projects = await registry.list_projects()
        assert len(projects["mcp-ticketer"]) == 2

    @pytest.mark.asyncio
    async def test_refresh_handles_empty_session_list(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test refresh with empty session list clears registry."""
        # Register sessions
        await registry.register_session(sample_sessions[0])

        # Refresh with empty list
        await registry.refresh_all([])

        # Verify registry cleared
        projects = await registry.list_projects()
        assert len(projects) == 0


class TestProjectRegistryPersistence:
    """Test registry persistence."""

    @pytest.mark.asyncio
    async def test_save_and_load_registry(
        self,
        temp_registry_path: Path,
        sample_sessions: list[UnifiedSession],
    ) -> None:
        """Test registry persists to disk and loads correctly."""
        # Register sessions
        registry1 = ProjectRegistry(registry_path=temp_registry_path)
        await registry1.register_session(sample_sessions[0])
        await registry1.register_session(sample_sessions[1])

        # Create new registry instance (should load from disk)
        registry2 = ProjectRegistry(registry_path=temp_registry_path)

        # Verify loaded correctly
        projects = await registry2.list_projects()
        assert len(projects["mcp-ticketer"]) == 2
        assert projects["mcp-ticketer"][0].session_id == sample_sessions[0].id
        assert projects["mcp-ticketer"][1].session_id == sample_sessions[1].id

    @pytest.mark.asyncio
    async def test_load_nonexistent_registry(self, temp_registry_path: Path) -> None:
        """Test loading when registry file doesn't exist."""
        registry = ProjectRegistry(registry_path=temp_registry_path)
        projects = await registry.list_projects()
        assert len(projects) == 0

    @pytest.mark.asyncio
    async def test_load_corrupted_registry(
        self, temp_registry_path: Path, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test loading corrupted registry file starts fresh."""
        # Write corrupted JSON
        temp_registry_path.parent.mkdir(parents=True, exist_ok=True)
        temp_registry_path.write_text("invalid json{")

        # Should not raise, should start with empty registry
        registry = ProjectRegistry(registry_path=temp_registry_path)
        projects = await registry.list_projects()
        assert len(projects) == 0

        # Should be able to register sessions
        await registry.register_session(sample_sessions[0])
        projects = await registry.list_projects()
        assert len(projects) == 1

    @pytest.mark.asyncio
    async def test_atomic_write(
        self, temp_registry_path: Path, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test registry writes are atomic."""
        registry = ProjectRegistry(registry_path=temp_registry_path)
        await registry.register_session(sample_sessions[0])

        # Verify no .tmp file left behind
        assert not temp_registry_path.with_suffix(".tmp").exists()
        assert temp_registry_path.exists()


class TestProjectRegistryEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_terminal_backend_extraction_tmux(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test terminal backend extracted correctly for tmux."""
        session = sample_sessions[0]
        await registry.register_session(session)

        projects = await registry.list_projects()
        assert projects["mcp-ticketer"][0].terminal_backend == "tmux"

    @pytest.mark.asyncio
    async def test_terminal_backend_extraction_iterm2(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test terminal backend extracted correctly for iTerm2."""
        session = sample_sessions[2]
        await registry.register_session(session)

        projects = await registry.list_projects()
        assert projects["terminator"][0].terminal_backend == "iterm2"

    @pytest.mark.asyncio
    async def test_project_name_from_nested_path(self, registry: ProjectRegistry) -> None:
        """Test project name extraction from deeply nested path."""
        session = UnifiedSession(
            id="tmux:test:0:0",
            name="test",
            terminal_type=TerminalType.TMUX,
            state=SessionState.IDLE,
            cwd="/very/deeply/nested/path/to/my-project",
        )

        address = await registry.register_session(session)
        assert address == "@my-project"

    @pytest.mark.asyncio
    async def test_instance_type_placeholder(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test instance_type is None (placeholder for future)."""
        await registry.register_session(sample_sessions[0])

        projects = await registry.list_projects()
        assert projects["mcp-ticketer"][0].instance_type is None

    @pytest.mark.asyncio
    async def test_list_projects_returns_copy(
        self, registry: ProjectRegistry, sample_sessions: list[UnifiedSession]
    ) -> None:
        """Test list_projects returns a copy, not internal state."""
        await registry.register_session(sample_sessions[0])

        projects1 = await registry.list_projects()
        projects2 = await registry.list_projects()

        # Should be equal but not the same object
        assert projects1 == projects2
        assert projects1 is not projects2
