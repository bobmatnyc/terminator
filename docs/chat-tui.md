# Chat TUI - Interactive Terminal Session Control

The Terminator chat TUI provides an interactive, full-screen interface for conversational control of terminal sessions.

## Features

- **Split-pane layout**: Chat history (scrollable) on top, input at bottom
- **Session focus**: Target specific sessions with @mentions
- **Tool execution feedback**: Visual indicators for command execution
- **Command history**: Navigate previous inputs with up/down arrows
- **Special commands**: Built-in shortcuts for common operations

## Usage

### Basic Commands

```bash
# Start TUI chat (default mode)
terminator chat

# Start with specific session focused
terminator chat @mcp-ticketer

# Use simple (non-TUI) mode
terminator chat --simple
```

### TUI Layout

```
╭─────────────────── Terminator Chat ──────────────────╮
│ Focused: @mcp-ticketer (claude-code)                 │
├──────────────────────────────────────────────────────┤
│                                                       │
│ You: What's happening in @mcp-ticketer?              │
│                                                       │
│ Terminator: The session is idle. Last output shows   │
│ the Claude Code prompt waiting for input.            │
│                                                       │
│ You: Send "run the tests"                            │
│                                                       │
│ Terminator: ✓ Sent to @mcp-ticketer                  │
│ ✓ send_command                                        │
│                                                       │
├──────────────────────────────────────────────────────┤
│ > _                                                   │
├──────────────────────────────────────────────────────┤
│ Ctrl+C: quit | Ctrl+L: clear | /sessions /focus      │
╰──────────────────────────────────────────────────────╯
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Up/Down` | Navigate command history |
| `Ctrl+C` | Exit TUI |
| `Ctrl+L` | Clear chat history |
| `Mouse scroll` | Scroll chat history |

### Special Commands

#### `/sessions`
List all available terminal sessions with their addresses and types.

```
> /sessions
Available sessions:
  • @mcp-ticketer (claude-code)
  • @terminator (claude-code)
  • @my-app:2 (python)
```

#### `/focus @project`
Focus on a specific session. Subsequent natural language references will target this session.

```
> /focus @mcp-ticketer
Focused on @mcp-ticketer

> What's the status?
[Terminator checks @mcp-ticketer status]
```

#### `/clear`
Clear the chat history and reset the conversation context.

```
> /clear
[Chat history cleared]
```

#### `/quit` or `/exit`
Exit the TUI and return to terminal.

```
> /quit
Goodbye!
```

## Examples

### Check Session Status

```
> What's happening in @terminator?

Terminator: The session is currently idle at the shell prompt in /Users/masa/Projects/terminator.
```

### Send Commands

```
> Send "npm test" to @my-app

Terminator: ✓ Sent to @my-app
✓ send_command

The tests are running...
```

### Multi-turn Conversation

```
> List sessions

Terminator: You have 3 active sessions:
  • @mcp-ticketer (claude-code)
  • @terminator (claude-code)
  • @my-app:2 (python)

> Focus on @mcp-ticketer
Focused on @mcp-ticketer

> What's it doing?
Terminator: The session is waiting for input at the Claude Code prompt.

> Tell it to run the linter
Terminator: ✓ Message sent
✓ send_command

Claude Code is now running the linter...
```

## Tips

1. **Use @mentions**: Sessions are addressable by project name (e.g., `@terminator`, `@mcp-ticketer:2`)
2. **Natural language**: Just type naturally - "What's happening?", "Run the tests", "Check status"
3. **Tool feedback**: Watch for ✓ indicators showing successful command execution
4. **History navigation**: Use up/down arrows to recall previous messages
5. **Focus mode**: Use `/focus` to set a default target for subsequent messages

## Troubleshooting

### TUI not displaying correctly

If the TUI layout is broken, try:
```bash
# Use simple mode instead
terminator chat --simple

# Or resize your terminal window
```

### Can't connect to sessions

Ensure terminal backends are running:
```bash
# Check tmux
tmux list-sessions

# Or verify iTerm2 is open
```

### LLM not responding

Verify your API key is set:
```bash
# Check environment
echo $TERMINATOR_OPENROUTER_API_KEY

# Or check .env file
cat .env | grep OPENROUTER
```

## Architecture

The TUI is built with:
- **prompt_toolkit**: Input handling, layout, key bindings
- **rich**: Markdown formatting, panels
- **TerminalChatbot**: LLM integration and tool execution
- **TerminalService**: Session management

See `src/terminator/cli/tui/chat_interface.py` for implementation details.
