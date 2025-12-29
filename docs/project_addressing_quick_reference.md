# @Project Addressing - Quick Reference

## Address Format

| Format | Example | Description |
|--------|---------|-------------|
| `@project` | `@mcp-ticketer` | Primary session in project |
| `@project:N` | `@mcp-ticketer:2` | Nth session in project (N=2,3,4...) |
| Raw session ID | `tmux:terminator:0:0` | Still works (backward compatible) |

## CLI Commands

### List Sessions
```bash
terminator sessions
```
**Output:**
```
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Address         ┃ Instance     ┃ Session ID                      ┃ CWD                   ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ @mcp-ticketer   │ (claude-code)│ tmux:mcp-ticketer:0:0           │ ~/Projects/mcp-ticke  │
│ @mcp-ticketer:2 │ (auggie)     │ tmux:mcp-ticketer:1:0           │ ~/Projects/mcp-ticke  │
│ @terminator     │ (shell)      │ tmux:terminator:0:0             │ ~/Projects/terminator │
└─────────────────┴──────────────┴─────────────────────────────────┴───────────────────────┘
```

### Send Command
```bash
# Primary session
terminator send @mcp-ticketer "implement user login"

# Second session
terminator send @mcp-ticketer:2 "run tests"

# Still works with raw ID
terminator send tmux:terminator:0:0 "git status"
```

### Read Output
```bash
# Read recent output
terminator read @terminator

# Read more lines
terminator read @terminator --lines 100
```

## Chatbot Usage

### Natural Language
```
User: "Tell @mcp-ticketer to add error handling"
Bot: I've sent your message to the Claude Code session in mcp-ticketer.

User: "What's @terminator doing?"
Bot: The shell session in terminator is idle at the command prompt.

User: "Check on @mcp-ticketer:2"
Bot: The Auggie session in mcp-ticketer is currently processing...
```

### Chatbot Commands
All tools support @project addressing:
- `list_sessions` - Shows addresses and instance types
- `send_command` - Send to `@project` or `@project:2`
- `get_session_output` - Read from `@project`
- `get_session_state` - Check state of `@project`
- `get_session_status` - Get detailed status of `@project`

## Instance Types

| Type | Description | Detection Pattern |
|------|-------------|------------------|
| `claude-code` | Claude Code AI assistant | `"Claude Code"`, `"claude-code>"` |
| `auggie` | Auggie/Augment Code | `"Auggie"`, `"augment>"` |
| `python` | Python REPL or IPython | `">>>"`, `"In [1]:"` |
| `node` | Node.js REPL | `"> "`, `"Welcome to Node.js"` |
| `shell` | Bash/Zsh shell | `"$"`, `"#"`, `"❯"` |
| `unknown` | Could not detect | (detection failed) |

## Python API

```python
from terminator.container import get_container

container = get_container()
terminal_service = container.get_terminal_service()

# Connect and list (auto-registers projects and detects instance types)
await terminal_service.connect_all()
sessions = await terminal_service.list_all_sessions()

# Use @project addressing
result = await terminal_service.send_command("@mcp-ticketer", "run tests")
print(result.output)

# Check instance type
for session in sessions:
    print(f"{session.name}: {session.instance_type.value}")
```

## How Projects are Named

Project name is extracted from the **basename** of the current working directory:

| CWD | Project Name | Primary Address |
|-----|--------------|----------------|
| `/Users/test/Projects/mcp-ticketer` | `mcp-ticketer` | `@mcp-ticketer` |
| `/home/dev/workspace/terminator` | `terminator` | `@terminator` |
| `/var/www/my-app` | `my-app` | `@my-app` |

## Numbered Instances

When multiple sessions exist in the same project directory:

| Session # | CWD | Address |
|-----------|-----|---------|
| 1 (primary) | `/Users/test/Projects/mcp-ticketer` | `@mcp-ticketer` |
| 2 | `/Users/test/Projects/mcp-ticketer` | `@mcp-ticketer:2` |
| 3 | `/Users/test/Projects/mcp-ticketer` | `@mcp-ticketer:3` |

## Registry Location

Project registry persists to:
```
~/.terminator/projects.json
```

**Example:**
```json
{
  "mcp-ticketer": [
    {
      "address": "@mcp-ticketer",
      "session_id": "tmux:mcp-ticketer:0:0",
      "project_name": "mcp-ticketer",
      "project_path": "/Users/test/Projects/mcp-ticketer",
      "instance_type": "claude-code",
      "terminal_backend": "tmux"
    }
  ]
}
```

## Troubleshooting

### Project not found
```bash
terminator send @myproject "test"
# Error: Session not found: @myproject
```
**Solution:** Run `terminator sessions` first to register projects

### Wrong session selected
If `@project` resolves to wrong session, check numbering:
```bash
terminator sessions  # See all addresses
terminator send @project:2 "test"  # Use specific instance
```

### Instance type is "unknown"
- Detection requires screen output
- Some sessions may not have recognizable patterns
- Will default to "shell" if no match found

## Best Practices

1. **List first:** Run `terminator sessions` to see all available addresses
2. **Primary for single:** Use `@project` for single-session projects
3. **Numbered for multi:** Use `@project:2` when multiple sessions in same project
4. **Raw IDs for scripts:** Use raw session IDs in automation scripts for stability
5. **Natural language:** In chatbot, just say "@project" and it understands

## Tips

- **Tab completion** (future): `@m<tab>` → `@mcp-ticketer`
- **Fuzzy matching** (future): `@mcp` → `@mcp-ticketer`
- **Session filtering** (future): `terminator sessions --type claude-code`
