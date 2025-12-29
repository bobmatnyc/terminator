"""Project-based session registry for address resolution.

Manages mapping of project addresses (@project, @project:2) to session IDs.
Persists registry to disk for session resume capability.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ..adapters.protocols import TerminalType, UnifiedSession


@dataclass
class ProjectSession:
    """Project session metadata for address resolution."""

    address: str
    session_id: str
    project_name: str
    project_path: str
    instance_type: Optional[str]
    terminal_backend: str


class ProjectRegistry:
    """Registry for project-based session addressing.

    Maps project names to session IDs, enabling addressing like @project
    or @project:2 for multiple sessions in the same project directory.

    Features:
    - Automatic project name extraction from CWD
    - Numbered instances for multiple sessions per project
    - Persistent storage to ~/.termpilot/projects.json
    - Address resolution with fallback to primary session
    """

    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize project registry.

        Args:
            registry_path: Path to registry file (defaults to ~/.termpilot/projects.json)
        """
        if registry_path is None:
            registry_path = Path.home() / ".termpilot" / "projects.json"
        self._registry_path = registry_path
        self._registry: dict[str, list[ProjectSession]] = {}
        self._session_to_project: dict[str, str] = {}
        self._load_registry()

    async def register_session(self, session: UnifiedSession) -> str:
        """Register a session and return its project address.

        Args:
            session: Session to register

        Returns:
            Project address (@project or @project:N)
        """
        if not session.cwd:
            return ""

        project_name = self._extract_project_name(session.cwd)
        if not project_name:
            return ""

        # Get or create project entry
        if project_name not in self._registry:
            self._registry[project_name] = []

        # Check if session already registered
        existing = self._find_session_in_project(project_name, session.id)
        if existing:
            return existing.address

        # Determine instance number
        instance_num = len(self._registry[project_name]) + 1
        address = f"@{project_name}" if instance_num == 1 else f"@{project_name}:{instance_num}"

        # Extract terminal backend from session ID
        terminal_backend = self._extract_terminal_backend(session)

        # Create project session
        project_session = ProjectSession(
            address=address,
            session_id=session.id,
            project_name=project_name,
            project_path=session.cwd,
            instance_type=None,  # Placeholder for future instance type detection
            terminal_backend=terminal_backend,
        )

        # Register
        self._registry[project_name].append(project_session)
        self._session_to_project[session.id] = project_name
        await self._save_registry()

        return address

    async def unregister_session(self, session_id: str) -> None:
        """Remove a session from the registry.

        Args:
            session_id: Session ID to remove
        """
        project_name = self._session_to_project.get(session_id)
        if not project_name:
            return

        # Remove from project list
        if project_name in self._registry:
            self._registry[project_name] = [
                ps for ps in self._registry[project_name] if ps.session_id != session_id
            ]

            # Clean up empty projects
            if not self._registry[project_name]:
                del self._registry[project_name]

            # Renumber remaining sessions
            await self._renumber_project(project_name)

        # Remove from reverse mapping
        if session_id in self._session_to_project:
            del self._session_to_project[session_id]

        await self._save_registry()

    async def resolve(self, address: str) -> Optional[str]:
        """Resolve a project address to a session ID.

        Args:
            address: Project address (@project or @project:N)

        Returns:
            Session ID or None if not found

        Examples:
            @mcp-ticketer -> first session in mcp-ticketer project
            @mcp-ticketer:2 -> second session in mcp-ticketer project
        """
        if not address.startswith("@"):
            return None

        # Parse address
        address_clean = address[1:]  # Remove @
        if ":" in address_clean:
            project_name, instance_str = address_clean.split(":", 1)
            try:
                instance_num = int(instance_str)
            except ValueError:
                return None
        else:
            project_name = address_clean
            instance_num = 1  # Default to first session

        # Look up project
        if project_name not in self._registry:
            return None

        sessions = self._registry[project_name]
        if instance_num < 1 or instance_num > len(sessions):
            return None

        return sessions[instance_num - 1].session_id

    async def list_projects(self) -> dict[str, list[ProjectSession]]:
        """List all projects with their sessions.

        Returns:
            Dict mapping project names to lists of project sessions
        """
        return dict(self._registry)

    async def refresh_all(self, sessions: list[UnifiedSession]) -> None:
        """Refresh registry from current session list.

        Removes stale sessions and registers new ones.

        Args:
            sessions: Current list of active sessions
        """
        # Get current session IDs
        current_session_ids = {s.id for s in sessions}

        # Remove stale sessions
        stale_session_ids = set(self._session_to_project.keys()) - current_session_ids
        for session_id in stale_session_ids:
            await self.unregister_session(session_id)

        # Register new sessions
        for session in sessions:
            if session.id not in self._session_to_project and session.cwd:
                await self.register_session(session)

    def _extract_project_name(self, cwd: str) -> str:
        """Extract project name from working directory path.

        Args:
            cwd: Current working directory

        Returns:
            Project name (basename of path) or empty string
        """
        if not cwd:
            return ""
        path = Path(cwd)
        return path.name

    def _extract_terminal_backend(self, session: UnifiedSession) -> str:
        """Extract terminal backend from session.

        Args:
            session: Unified session

        Returns:
            Terminal backend name ("tmux" or "iterm2")
        """
        if session.terminal_type == TerminalType.TMUX:
            return "tmux"
        elif session.terminal_type == TerminalType.ITERM2:
            return "iterm2"
        return "unknown"

    def _find_session_in_project(
        self, project_name: str, session_id: str
    ) -> Optional[ProjectSession]:
        """Find a session within a project.

        Args:
            project_name: Project to search
            session_id: Session ID to find

        Returns:
            ProjectSession if found, None otherwise
        """
        if project_name not in self._registry:
            return None

        for ps in self._registry[project_name]:
            if ps.session_id == session_id:
                return ps

        return None

    async def _renumber_project(self, project_name: str) -> None:
        """Renumber sessions in a project after removal.

        Updates addresses to maintain sequential numbering.

        Args:
            project_name: Project to renumber
        """
        if project_name not in self._registry:
            return

        sessions = self._registry[project_name]
        for i, ps in enumerate(sessions, start=1):
            new_address = f"@{project_name}" if i == 1 else f"@{project_name}:{i}"
            ps.address = new_address

    def _load_registry(self) -> None:
        """Load registry from disk."""
        if not self._registry_path.exists():
            return

        try:
            with open(self._registry_path, "r") as f:
                data = json.load(f)

            # Reconstruct registry
            for project_name, sessions_data in data.items():
                sessions = [ProjectSession(**ps_data) for ps_data in sessions_data]
                self._registry[project_name] = sessions

                # Rebuild reverse mapping
                for ps in sessions:
                    self._session_to_project[ps.session_id] = project_name

        except (json.JSONDecodeError, TypeError, KeyError):
            # Corrupted registry, start fresh
            self._registry = {}
            self._session_to_project = {}

    async def _save_registry(self) -> None:
        """Save registry to disk."""
        # Ensure directory exists
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to serializable format
        data = {
            project_name: [asdict(ps) for ps in sessions]
            for project_name, sessions in self._registry.items()
        }

        # Write atomically
        temp_path = self._registry_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
        temp_path.replace(self._registry_path)
