# ProjectRegistry Service Integration

## Overview

The `ProjectRegistry` service provides project-based session addressing for the Terminator application. It maps human-friendly project addresses (like `@mcp-ticketer` or `@terminator:2`) to session IDs, enabling intuitive session targeting.

## Architecture

### Components

1. **ProjectRegistry** (`src/terminator/services/project_registry.py`)
   - Main service class for address resolution
   - Manages registry state and persistence
   - Handles session registration/unregistration

2. **ProjectSession** (dataclass)
   - Metadata for registered sessions
   - Fields: `address`, `session_id`, `project_name`, `project_path`, `instance_type`, `terminal_backend`

3. **DI Container Integration** (`src/terminator/container.py`)
   - Singleton instance via `get_project_registry()`
   - Lazy initialization
   - Automatic cleanup on reset

### Addressing Rules

- **Project Name**: Extracted from basename of CWD
  - `/Users/masa/Projects/mcp-ticketer` → `mcp-ticketer`

- **Primary Session**: First session gets `@project`
  - Example: `@mcp-ticketer`

- **Multiple Sessions**: Subsequent sessions get `@project:N`
  - Example: `@mcp-ticketer:2`, `@mcp-ticketer:3`

- **Terminal Backend**: Extracted from session type
  - `TerminalType.TMUX` → `"tmux"`
  - `TerminalType.ITERM2` → `"iterm2"`

## API

### Core Methods

```python
# Register session and get project address
address = await registry.register_session(session)
# Returns: "@project" or "@project:N"

# Resolve address to session ID
session_id = await registry.resolve("@project:2")
# Returns: "tmux:project:0:1" or None

# Unregister session
await registry.unregister_session(session_id)

# List all projects with sessions
projects = await registry.list_projects()
# Returns: dict[str, list[ProjectSession]]

# Refresh registry from current sessions
await registry.refresh_all(active_sessions)
```

### Persistence

- Registry persists to `~/.terminator/projects.json`
- Atomic writes (temp file + rename)
- Automatic loading on initialization
- Corrupted registry handling (starts fresh)

## Usage Example

```python
from terminator.container import get_container
from terminator.adapters.protocols import UnifiedSession, TerminalType, SessionState

# Get registry from DI container
container = get_container()
registry = container.get_project_registry()

# Register sessions
session = UnifiedSession(
    id="tmux:mcp-ticketer:0:0",
    name="mcp-ticketer",
    terminal_type=TerminalType.TMUX,
    state=SessionState.IDLE,
    cwd="/Users/masa/Projects/mcp-ticketer",
)
address = await registry.register_session(session)
print(f"Registered: {address}")  # Output: @mcp-ticketer

# Resolve address
session_id = await registry.resolve("@mcp-ticketer")
print(f"Resolved: {session_id}")  # Output: tmux:mcp-ticketer:0:0

# List projects
projects = await registry.list_projects()
for name, sessions in projects.items():
    print(f"Project {name}:")
    for ps in sessions:
        print(f"  {ps.address} -> {ps.session_id}")
```

## Testing

### Test Coverage

- **96% code coverage** (126 statements, 5 missed)
- **25 test cases** across 6 test classes
- All edge cases covered

### Test Categories

1. **Basics**: Registration, multiple sessions, different projects
2. **Resolution**: Address parsing, invalid formats, instance numbers
3. **Unregister**: Session removal, renumbering, cleanup
4. **Refresh**: Stale session removal, new session registration
5. **Persistence**: Save/load, corrupted registry, atomic writes
6. **Edge Cases**: Terminal backend extraction, nested paths, idempotency

### Running Tests

```bash
# Run all tests
uv run pytest tests/test_project_registry.py -v

# With coverage
uv run pytest tests/test_project_registry.py \
  --cov=terminator.services.project_registry \
  --cov-report=term-missing

# Type checking
uv run mypy src/terminator/services/project_registry.py --strict
```

## Integration Points

### TerminalService

```python
# Example integration with TerminalService
terminal_service = container.get_terminal_service()
registry = container.get_project_registry()

# Get all sessions
sessions = await terminal_service.list_all_sessions()

# Refresh registry
await registry.refresh_all(sessions)

# Resolve address and send command
session_id = await registry.resolve("@mcp-ticketer")
if session_id:
    result = await terminal_service.send_command(
        session_id,
        "npm test",
        wait_for_completion=True
    )
```

### Future Enhancements

1. **Instance Type Detection**
   - Currently placeholder (`instance_type: Optional[str]`)
   - Could detect: `claude-code`, `auggie`, `shell`, `repl`
   - Use PS1 analysis or process inspection

2. **Smart Resolution**
   - Fuzzy matching for project names
   - Alias support (`@work` → `@mcp-ticketer`)
   - Last-used session tracking

3. **Multi-Backend Support**
   - Registry could support additional backends
   - Terminal backend used for routing

## Files Created

1. **Service Implementation**
   - `/Users/masa/Projects/terminator/src/terminator/services/project_registry.py`

2. **Tests**
   - `/Users/masa/Projects/terminator/tests/test_project_registry.py`

3. **Container Integration**
   - Updated: `/Users/masa/Projects/terminator/src/terminator/container.py`
   - Updated: `/Users/masa/Projects/terminator/src/terminator/services/__init__.py`

4. **Examples**
   - `/Users/masa/Projects/terminator/examples/project_registry_example.py`

5. **Documentation**
   - `/Users/masa/Projects/terminator/docs/project_registry_integration.md`
