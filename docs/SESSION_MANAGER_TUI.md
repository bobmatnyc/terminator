# Session Manager TUI

Interactive terminal user interface for managing Terminator sessions.

## Usage

```bash
terminator manage
```

## Features

### Session List
- Displays all active sessions with:
  - **@project addresses** (e.g., `@mcp-ticketer`, `@terminator`)
  - **Instance type** (claude-code, auggie, shell, python, node)
  - **Session ID** (backend:name:window:pane)
  - **Current Working Directory**

### Navigation
- **Arrow keys** (`↑`/`↓`) or **Vim keys** (`j`/`k`): Navigate through sessions
- **Selection indicator** (`>`) shows the currently selected session

### Actions

| Key | Action | Description |
|-----|--------|-------------|
| `a` or `Enter` | **Attach** | Attach to the selected tmux session (opens in full screen) |
| `d` | **Kill** | Kill the selected session (with confirmation prompt) |
| `r` | **Refresh** | Refresh the session list |
| `q` or `Esc` | **Quit** | Exit the TUI |

### Session Details Panel
When a session is selected, the bottom panel shows:
- Current working directory
- Session state (IDLE, RUNNING, WAITING_INPUT, UNKNOWN)
- Instance type
- Backend type (tmux or iTerm2)

### Confirmation Prompts
Before killing a session, a confirmation prompt displays:
- Session address
- Instance type
- Current working directory
- Press `y` to confirm, any other key to cancel

## UI Layout

```
╭─────────────────── Terminator Session Manager ───────────────────╮
│                                                                   │
│  > @mcp-ticketer     (claude-code)  tmux:mcp-ticketer:0:0       │
│    @terminator       (shell)        tmux:terminator:0:0          │
│    @codex            (auggie)       tmux:codex:0:0               │
│                                                                   │
├───────────────────────────────────────────────────────────────────┤
│ CWD: ~/Projects/mcp-ticketer                                     │
│ State: IDLE                                                       │
│ Instance: claude-code                                             │
│ Type: tmux                                                        │
╰───────────────────────────────────────────────────────────────────╯

↑↓/jk: Navigate  a/Enter: Attach  d: Kill  r: Refresh  q/Esc: Quit
```

## Implementation Details

### Architecture
- **SessionManagerTUI**: Main TUI class using Rich library
- **Rich Live**: For live-updating display
- **termios/tty**: For raw keyboard input handling
- **TerminalService**: Backend integration for session operations

### Keyboard Input
- Uses `tty.setcbreak()` for raw terminal mode
- Non-blocking input with 50ms timeout via `select.select()`
- Restores terminal settings on exit (even on errors)

### Session Operations
- **List**: Via `TerminalService.list_all_sessions()`
- **Attach**: Subprocess call to `tmux attach -t <session_name>`
- **Kill**: Via `TerminalService.kill_session(session_id)`
- **Refresh**: Re-fetches session list from backends

### Limitations
- **Attach** only works for tmux sessions (iTerm2 sessions show error)
- Requires tmux or iTerm2 backend to be available
- Terminal must support ANSI escape sequences for Rich rendering

## Testing

Unit tests cover:
- TUI initialization and rendering
- Session list refresh and caching
- Navigation bounds checking
- Kill session workflow
- @project address resolution

Run tests:
```bash
python -m pytest tests/unit/test_session_manager_tui.py -v
python -m pytest tests/unit/test_kill_session.py -v
```

## Dependencies

- **rich**: Terminal UI rendering (already included)
- **termios/tty**: Standard library (Unix/Linux/macOS only)
- **select**: Standard library for non-blocking I/O
- **subprocess**: For tmux attach command

## Future Enhancements

- [ ] Support for iTerm2 attach (bring window to front)
- [ ] Bulk operations (kill multiple sessions)
- [ ] Search/filter sessions by name or CWD
- [ ] Sort sessions by different criteria
- [ ] Show resource usage (CPU, memory) per session
- [ ] Export session list to file
- [ ] Keyboard shortcut for creating new session
