# Instance Type Detection

The InstanceDetector service identifies the type of REPL or shell running in a terminal session by analyzing screen output patterns.

## Supported Instance Types

- **Claude Code**: Claude's conversational coding assistant
- **Auggie**: Augment Code assistant
- **Python**: Standard Python REPL or IPython
- **Node**: Node.js REPL
- **Shell**: Bash, zsh, or other shells
- **Unknown**: No recognizable patterns detected

## Usage

### Basic Detection

```python
from terminator.container import get_container

container = get_container()
detector = container.get_instance_detector()

# Detect from screen content
instance_type = await detector.detect_type(session_id, screen_content)

# Detect from session (automatically captures output)
instance_type = await detector.detect_from_session(session, adapter)
```

### Integration with TerminalService

```python
from terminator.container import get_container

async def detect_all_sessions():
    container = get_container()
    terminal_service = container.get_terminal_service()
    detector = container.get_instance_detector()

    await terminal_service.connect_all()
    sessions = await terminal_service.list_all_sessions()

    for session in sessions:
        adapter = terminal_service._get_adapter_for_session(session.id)
        instance_type = await detector.detect_from_session(session, adapter)
        session.instance_type = instance_type
        print(f"{session.name}: {instance_type.value}")
```

## Detection Patterns

The detector uses configurable regex patterns with priority ordering:

### Claude Code (Priority: 100)
```
- "Claude Code"
- "claude-code>"
- "anthropic.*claude"
- "╭─.*Claude"  # UI elements
```

### Auggie (Priority: 90)
```
- "Auggie"
- "augment>"
- "Augment Code"
```

### Python (Priority: 50)
```
- "^>>>"         # Standard Python prompt
- "^\.\.\.\s"    # Continuation prompt
- "^In \[\d+\]:" # IPython
- "Python \d+\.\d+"
```

### Node.js (Priority: 40)
```
- "^>\s"         # Node REPL prompt
- "Welcome to Node\.js"
- "node v\d+\.\d+"
```

### Shell (Priority: 10)
```
- "[$#%❯➜]\s*$" # Shell prompts
- "/bin/zsh"
- "/bin/bash"
```

## Custom Patterns

Add custom detection patterns dynamically:

```python
from terminator.adapters import InstanceType

detector = container.get_instance_detector()

# Add pattern for vim
detector.add_pattern(
    instance_type=InstanceType.SHELL,
    pattern=r"VIM - Vi IMproved",
    priority=60
)
```

Initialize with custom patterns:

```python
from terminator.services import InstanceDetector, DetectionPattern
from terminator.adapters import InstanceType

custom_patterns = [
    DetectionPattern(
        instance_type=InstanceType.PYTHON,
        patterns=[r"pypy"],
        priority=100,
    ),
]

detector = InstanceDetector(patterns=custom_patterns)
```

## Architecture

### Service Layer
- **InstanceDetector**: Service for detecting instance types
  - `detect_type(session_id, screen_content)`: Analyze text content
  - `detect_from_session(session, adapter)`: Capture and analyze session
  - `add_pattern(instance_type, pattern, priority)`: Add custom patterns

### Models
- **InstanceType**: Enum of supported instance types
- **DetectionPattern**: Pattern configuration with priority
- **UnifiedSession**: Extended with `instance_type` field

### DI Container
The InstanceDetector is registered as a singleton service:

```python
container = get_container()
detector = container.get_instance_detector()
```

## Pattern Matching

### Priority System
Patterns are checked in descending priority order. Higher priority patterns (Claude Code, Auggie) are checked before lower priority patterns (Shell). This prevents false positives where shell prompts might appear in REPL sessions.

### Case Insensitivity
All patterns are compiled with `re.IGNORECASE` for robust matching.

### Multiline Support
Patterns use `re.MULTILINE` to match across line boundaries.

### Default Behavior
- If no patterns match, `detect_type()` returns `InstanceType.UNKNOWN`
- `detect_from_session()` defaults to `InstanceType.SHELL` when no match found
- On error, returns `InstanceType.UNKNOWN`

## Testing

Comprehensive test suite in `tests/unit/test_instance_detector.py`:

```bash
# Run tests
pytest tests/unit/test_instance_detector.py -v

# Run with coverage
pytest tests/unit/test_instance_detector.py --cov=src/terminator/services/instance_detector
```

## Example

See `examples/detect_instance_type.py` for a complete working example:

```bash
python3 examples/detect_instance_type.py
```

## Performance Considerations

1. **Regex Compilation**: Patterns are compiled once during initialization
2. **Screen Capture**: Default 100 lines for better detection accuracy
3. **Early Exit**: First matching pattern returns immediately
4. **Caching**: Results can be cached in `UnifiedSession.instance_type`

## Future Enhancements

Potential future additions:
- Ruby REPL (irb, pry)
- R console
- Database shells (psql, mysql, sqlite3)
- Elixir/Erlang shells
- Language server prompts
- Custom AI assistants
