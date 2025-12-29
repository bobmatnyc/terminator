# Start Command Feature

## Overview

Added CLI command to start new coding sessions via `terminator start`. This enables launching Claude Code, Auggie, Python, Node.js, or shell sessions in project directories with automatic session registration.

## Implementation

### 1. Configuration (`src/terminator/config.py`)

Added agent command configuration to Settings:

```python
class Settings(BaseSettings):
    # Agent launch commands
    agent_claude_code_cmd: str = "claude"
    agent_auggie_cmd: str = "augment"
    agent_python_cmd: str = "python"
    agent_node_cmd: str = "node"
```

Environment variable support:
- `TERMINATOR_AGENT_CLAUDE_CODE_CMD` - Command for Claude Code (default: `claude`)
- `TERMINATOR_AGENT_AUGGIE_CMD` - Command for Auggie (default: `augment`)
- `TERMINATOR_AGENT_PYTHON_CMD` - Command for Python REPL (default: `python`)
- `TERMINATOR_AGENT_NODE_CMD` - Command for Node.js REPL (default: `node`)

### 2. Protocol Updates (`src/terminator/adapters/protocols.py`)

Added `create_session` method to `ITerminalAdapter` protocol:

```python
async def create_session(
    self,
    name: str,
    working_dir: str,
    command: str | None = None,
) -> str:
    """Create a new terminal session."""
```

### 3. Adapter Implementations

#### TmuxAdapter (`src/terminator/adapters/tmux.py`)

```python
async def create_session(
    self,
    name: str,
    working_dir: str,
    command: Optional[str] = None,
) -> str:
    """Create new tmux session with start directory and optional command."""
    # Uses libtmux to create session with start_directory
    # Sends command to first pane if provided
```

#### ITerm2Adapter (`src/terminator/adapters/iterm2.py`)

```python
async def create_session(
    self,
    name: str,
    working_dir: str,
    command: Optional[str] = None,
) -> str:
    """Create new iTerm2 tab with working directory and optional command."""
    # Creates new tab, sets name, changes directory, runs command
```

### 4. Service Layer (`src/terminator/services/terminal.py`)

Added `start_session` method to `TerminalService`:

```python
async def start_session(
    self,
    project_path: str,
    agent: str = "shell",
    name: Optional[str] = None,
) -> str:
    """Start a new coding session.

    Returns:
        Project address (@project or @project:N)
    """
    # Validates project path
    # Maps agent to command
    # Creates session with preferred backend (tmux → iTerm2 fallback)
    # Refreshes sessions to register with ProjectRegistry
    # Returns @project address
```

### 5. CLI Command (`src/terminator/cli/main.py`)

```python
@app.command()
def start(
    project_path: str,
    agent: str = "shell",
    name: str | None = None,
):
    """Start a new coding session in a project directory."""
```

## Usage

### Basic Usage

```bash
# Start shell session
terminator start ~/Projects/my-app

# Start Claude Code
terminator start ~/Projects/my-app --agent claude-code

# Start Auggie
terminator start ~/Projects/my-app --agent auggie

# Start Python REPL
terminator start ~/Projects/my-app --agent python

# Start Node.js REPL
terminator start ~/Projects/my-app --agent node
```

### Custom Session Name

```bash
# Use custom name instead of directory name
terminator start ~/Projects/my-app --name my-dev-session
```

### Short Flags

```bash
# Use short flags
terminator start ~/Projects/my-app -a claude-code -n my-session
```

## Examples

### Starting Claude Code

```bash
$ terminator start ~/Projects/terminator --agent claude-code
Connecting to terminal backends...
Using tmux backend
Starting Claude Code in terminator...

✓ Session created: @terminator (claude-code)

Connect: tmux attach -t terminator
```

### Starting Auggie

```bash
$ terminator start ~/Projects/my-app --agent auggie
Connecting to terminal backends...
Using tmux backend
Starting Auggie in my-app...

✓ Session created: @my-app (auggie)

Connect: tmux attach -t my-app
```

### Custom Session Name

```bash
$ terminator start ~/Projects/my-app -a shell -n dev-session
Connecting to terminal backends...
Using tmux backend
Starting Shell in my-app...

✓ Session created: @dev-session (shell)

Connect: tmux attach -t dev-session
```

## Backend Behavior

### tmux
- Creates new session with `tmux new-session`
- Sets start directory to project path
- Sends command to first pane if provided
- Session name becomes tmux session name
- Returns session ID: `tmux:session-name:0:0`

### iTerm2
- Creates new tab in current window (or new window if none)
- Sets tab name
- Changes directory with `cd` command
- Runs agent command if provided
- Returns session ID: `iterm2:session-id`

## Error Handling

- **Directory not found**: Raises `RuntimeError` with message "does not exist"
- **Invalid agent type**: Raises `ValueError` listing valid agent types
- **No backends available**: Raises `RuntimeError` prompting to start tmux or iTerm2
- **tmux failure**: Automatically falls back to iTerm2 if available

## Project Registration

Sessions created via `start` command are automatically:
1. Added to ProjectRegistry
2. Assigned @project addresses based on directory name
3. Available for addressing in other commands (`send`, `read`, etc.)

## Testing

Comprehensive test suite in `tests/unit/test_start_session.py`:

- ✅ Test starting sessions with all agent types
- ✅ Test custom session names
- ✅ Test default session naming (directory name)
- ✅ Test nonexistent directory error
- ✅ Test invalid agent type error
- ✅ Test fallback from tmux to iTerm2
- ✅ Test error when no backends available

All 76 tests passing (including 9 new tests for start command).

## Configuration Example

Set custom agent commands via environment variables:

```bash
# .env.local
TERMINATOR_AGENT_CLAUDE_CODE_CMD=claude
TERMINATOR_AGENT_AUGGIE_CMD=augment
TERMINATOR_AGENT_PYTHON_CMD=python3.12
TERMINATOR_AGENT_NODE_CMD=node
```

## Future Enhancements

Potential improvements:
- Support for additional agent types (Ruby, Rust REPLs, etc.)
- Template-based session initialization scripts
- Multi-pane layouts for specific workflows
- Integration with project detection (e.g., detect from git repo)
- Support for session profiles with pre-configured commands
