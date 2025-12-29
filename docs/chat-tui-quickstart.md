# Chat TUI Quick Start

## Installation

```bash
# Install dependencies
pip install -e .
```

## Basic Usage

```bash
# Start TUI chat (default)
terminator chat

# Start focused on a session
terminator chat @mcp-ticketer

# Use simple mode instead
terminator chat --simple
```

## Commands You Can Use

### Natural Language
```
What sessions are running?
What's @terminator doing?
Send "npm test" to @my-app
Run the linter in @project
Is @mcp-ticketer still working?
```

### Special Commands
| Command | Description |
|---------|-------------|
| `/sessions` | List all available sessions |
| `/focus @project` | Focus on specific session |
| `/clear` | Clear chat history |
| `/quit` or `/exit` | Exit TUI |

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Up/Down` | Navigate history |
| `Ctrl+C` | Quit |
| `Ctrl+L` | Clear |

## Examples

### Example 1: Check Status
```
You: What's happening in @terminator?

Terminator: The session is idle at the shell prompt.
```

### Example 2: Run Commands
```
You: /focus @my-app
Focused on @my-app

You: Run the tests
Terminator: ✓ Sent command
✓ send_command

The tests are passing!
```

### Example 3: Multi-session
```
You: List sessions
Terminator: You have 3 sessions:
  • @terminator (claude-code)
  • @my-app (python)
  • @docs (shell)

You: What's @docs doing?
Terminator: The shell is idle in /Users/you/docs
```

## Troubleshooting

**TUI won't start?**
```bash
# Use simple mode
terminator chat --simple
```

**Can't see sessions?**
```bash
# Check backends
tmux list-sessions
```

**API errors?**
```bash
# Verify API key
echo $TERMINATOR_OPENROUTER_API_KEY
```

## More Info

See full documentation: `docs/chat-tui.md`
