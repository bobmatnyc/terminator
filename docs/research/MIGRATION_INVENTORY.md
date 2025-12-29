# TermPilot POC Migration Inventory

**Complete list of all classes, functions, enums, and data structures to migrate from POC to production.**

---

## File: `scripts/poc/terminal_chatbot.py` (983 LOC)

### Enums
```python
class TerminalType(Enum):
    ITERM2 = "iterm2"
    TMUX = "tmux"

class SessionState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    UNKNOWN = "unknown"
```

### Data Classes
```python
@dataclass
class UnifiedSession:
    id: str
    name: str
    terminal_type: TerminalType
    state: SessionState = SessionState.UNKNOWN
    last_output: str = ""
    cwd: str = ""
    window_index: int = 0
    pane_index: int = 0

@dataclass
class CommandResult:
    success: bool
    output: str
    state_after: SessionState
    execution_time: float

@dataclass
class LLMMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list = field(default_factory=list)
    tool_call_id: Optional[str] = None

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
```

### Classes

#### `OpenRouterClient` (lines 112-202, ~90 LOC)
**Status:** Ready to migrate - self-contained HTTP client

**Methods:**
- `__init__(api_key: str, model: str)`
- `async chat(messages: list[LLMMessage], tools: list[dict] = None, temperature: float) -> tuple[str, list[ToolCall]]`

**Responsibilities:**
- HTTP communication with OpenRouter API
- Message formatting (OpenAI spec compliant)
- Tool call parsing
- Error handling

**Migration Target:** `/server/llm/openrouter.py`
**Dependencies to Inject:**
- api_key (from Settings.openrouter_api_key)
- model (from Settings.openrouter_model)
- settings (Configuration)

---

#### `UnifiedTerminalManager` (lines 209-588, ~380 LOC)
**Status:** Migrate with refactoring - complex logic, excellent patterns

**Methods:**
- `async connect() -> dict[str, bool]` - Connect to backends
- `async list_sessions() -> list[UnifiedSession]` - List all sessions
- `async get_session_output(session_id: str, lines: int = 50) -> str` - Get output
- `async send_command(session_id, command, wait_for_completion, timeout) -> CommandResult` - Execute command
- `async _wait_for_completion(session_id, timeout) -> str` - Wait for output stability
- `def _looks_like_prompt(output: str) -> bool` - Prompt detection heuristic
- `async detect_state(session_id: str) -> SessionState` - Detect idle/running
- `def _analyze_session_status(output: str) -> dict` - Analyze output (50+ LOC)
- `def _generate_screen_summary(lines, status, indicators) -> str` - Summarize screen
- `async get_session_status(session_id: str) -> dict` - Get comprehensive status

**Data Members:**
- `self.tmux: Optional[TmuxController]`
- `self.iterm2: Optional[ITerm2Controller]`
- `self._iterm2_connection: Optional[iterm2.Connection]`
- `self._sessions_cache: dict[str, UnifiedSession]`

**Responsibilities:**
- Backend coordination (tmux + iTerm2)
- Session discovery and caching
- State detection (idle/running/waiting)
- Output analysis and heuristics
- Command execution with timeout handling

**Migration Target:**
- `/server/adapters/unified.py` (UnifiedAdapter) - orchestration
- `/server/core/analysis.py` (AnalysisService) - analysis methods
- `/server/core/terminal.py` (TerminalService) - high-level API

**Dependencies to Inject:**
- iterm2_adapter (ITerm2Adapter)
- tmux_adapter (TmuxAdapter)
- analysis_service (AnalysisService)
- settings (Configuration)

---

#### `TerminalChatbot` (lines 725-864, ~140 LOC)
**Status:** Ready to migrate - needs tool extraction

**Methods:**
- `async execute_tool(tool_call: ToolCall) -> str` - Tool dispatcher (handles 5 tools)
- `async chat(user_input: str) -> str` - Main conversation loop with tool calling

**Data Members:**
- `self.llm: OpenRouterClient`
- `self.terminal: UnifiedTerminalManager`
- `self.messages: list[LLMMessage]` - Conversation history

**Responsibilities:**
- Stateful conversation management
- Tool call execution
- Message history tracking
- Tool result integration

**Migration Target:** `/server/services/chatbot.py`
**Dependencies to Inject:**
- llm_client (ILLMClient)
- terminal_service (TerminalService)
- tool_executor (ToolExecutor)
- settings (Configuration)

### Tool Definitions
```python
TERMINAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_sessions",
            "description": "List all available terminal sessions",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_state",
            "description": "Get the current state of a terminal session",
            "parameters": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_status",
            "description": "Get a status digest of a terminal session",
            "parameters": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_command",
            "description": "Send text/message to a terminal session",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "command": {"type": "string"},
                    "wait_for_completion": {"type": "boolean", "default": True}
                },
                "required": ["session_id", "command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_output",
            "description": "Get the recent output/content from a terminal session",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "lines": {"type": "integer", "default": 50}
                },
                "required": ["session_id"]
            }
        }
    }
]
```

**Migration Target:** `/server/llm/tools.py`

### System Prompt
```python
SYSTEM_PROMPT = """You are TermPilot, an AI assistant that helps users..."""
```

**Migration Target:** `/server/services/chatbot.py` or `/server/llm/prompts.py`

### Main Entry Point
```python
async def run_chatbot(provider: str = "openrouter"):
    # Complete chatbot initialization and REPL loop (lines 871-965)

def main(*args):
    # Entry point for POC runner (lines 967-979)
```

**Migration Target:** Becomes /server/main.py initialization logic

---

## File: `scripts/poc/iterm2_control.py` (560 LOC)

### Enums
```python
class SessionState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    UNKNOWN = "unknown"
```
**Note:** Different from terminal_chatbot.SessionState - should consolidate

### Data Classes
```python
@dataclass
class SessionInfo:
    session_id: str
    name: str
    tab_id: str
    window_id: str
    columns: int
    rows: int
```

### Classes

#### `ITerm2Controller` (lines 54-300+, ~300 LOC)
**Status:** Ready to migrate - minimal changes, already async

**Methods:**
- `async get_app() -> iterm2.App` - Get cached app instance
- `async list_sessions() -> list[SessionInfo]` - List all sessions
- `async create_window(profile=None) -> tuple[str, str]` - Create window
- `async create_tab(window_id=None, profile=None) -> tuple[str, str]` - Create tab
- `async split_pane(session_id, vertical=True, profile=None) -> str` - Split pane
- `async send_text(session_id, text, newline=True, line_ending="\r") -> bool` - Send text
- `async get_screen_contents(session_id, lines=50) -> str` - Get output
- `async get_screen_streamed(session_id, callback, duration=5.0)` - Stream updates
- `async close_session(session_id, force=False) -> bool` - Close session
- `async set_session_name(session_id, name) -> bool` - Rename session

**Data Members:**
- `self.connection: iterm2.Connection`
- `self._app: Optional[iterm2.App]`

**Responsibilities:**
- Direct iterm2 API wrapper
- Session management (create/close)
- Text I/O (send/receive)
- Screen capture and streaming

**Migration Target:** `/server/adapters/iterm2.py`
**Implements:** `ITerminalAdapter` protocol
**Dependencies to Inject:**
- connection (iterm2.Connection - can be created in connect())
- settings (Configuration for options)

---

## File: `scripts/poc/tmux_control.py` (728 LOC)

### Enums
```python
class PaneState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    UNKNOWN = "unknown"
```

### Data Classes
```python
@dataclass
class TmuxSessionInfo:
    session_id: str
    session_name: str
    window_count: int
    created: str
    attached: bool

@dataclass
class TmuxWindowInfo:
    window_id: str
    window_name: str
    window_index: int
    pane_count: int
    active: bool

@dataclass
class TmuxPaneInfo:
    pane_id: str
    pane_index: int
    width: int
    height: int
    current_path: str
    active: bool
```

### Classes

#### `TmuxController` (lines 74-300+, ~250 LOC)
**Status:** Ready to migrate - needs async wrapping

**Methods (Sync → Must become Async):**
- `def connect() -> bool` → `async def connect()`
- `def list_sessions() -> list[TmuxSessionInfo]` → `async def list_sessions()`
- `def create_session(name, working_dir=None, attach=False) -> tuple[str, str, str]` → `async def create_session()`
- `def kill_session(session_name) -> bool` → `async def kill_session()`
- `def get_session(session_name) -> Optional[libtmux.Session]` → `async def get_session()`
- `def list_windows(session_name) -> list[TmuxWindowInfo]` → `async def list_windows()`
- `def create_window(session_name, window_name, working_dir=None) -> tuple[str, str]` → `async def create_window()`
- `def list_panes(session_name, window_index=0) -> list[TmuxPaneInfo]` → `async def list_panes()`
- `def split_pane(session_name, window_index=0, vertical=True, working_dir=None) -> str` → `async def split_pane()`
- `def send_keys(session_name, keys, window_index=0, pane_index=0, enter=True) -> bool` → `async def send_keys()`
- `def capture_pane(session_name, window_index, pane_index, lines) -> str` (not shown in excerpt)
- `def detect_pane_state(session_name, window_index, pane_index) -> PaneState` (not shown)

**Data Members:**
- `self.server: Optional[libtmux.Server]`

**Responsibilities:**
- Direct libtmux API wrapper
- Session/window/pane management
- Text I/O (send/capture)
- State detection

**Migration Target:** `/server/adapters/tmux.py`
**Implements:** `ITerminalAdapter` protocol
**Dependencies to Inject:**
- settings (Configuration)
**Special Handling:**
- Wrap all sync libtmux calls with `asyncio.to_thread()`
- Consider thread pool executor

---

## Summary: Component Migration Map

| Source | LOC | Target | Type | Priority |
|--------|-----|--------|------|----------|
| iterm2_control.py | 300 | `adapters/iterm2.py` | Adapter | P0 |
| tmux_control.py | 250 | `adapters/tmux.py` | Adapter | P0 |
| terminal_chatbot.py (Manager) | 380 | `adapters/unified.py` + `core/analysis.py` | Adapter + Service | P0 |
| terminal_chatbot.py (LLMClient) | 90 | `llm/openrouter.py` | LLM Client | P1 |
| terminal_chatbot.py (Tools) | 100 | `llm/tools.py` | Tool Definitions | P1 |
| terminal_chatbot.py (Chatbot) | 140 | `services/chatbot.py` | Service | P2 |
| terminal_chatbot.py (Types) | 40 | `adapters/base.py` + `adapters/models.py` | Types | P0 |

---

## Classes to Create (New)

These don't exist in POC but are needed for production:

1. **`ILLMClient` Protocol** → `/server/llm/client.py`
   - Abstract interface for LLM providers
   - Protocol with `async def chat()` method

2. **`AnalysisService`** → `/server/core/analysis.py`
   - Extract analysis methods from UnifiedTerminalManager
   - Pure logic service (no state)
   - Methods:
     - `analyze_session_status(output: str) -> AnalysisResult`
     - `generate_screen_summary(...) -> str`
     - Pattern detection methods

3. **`TerminalService`** → `/server/core/terminal.py`
   - High-level terminal operations
   - Wraps UnifiedAdapter
   - Methods:
     - `async get_all_sessions() -> list[SessionInfo]`
     - `async execute_command(...) -> CommandResult`
     - `async get_session_output(...) -> str`
     - `async get_session_status(...) -> dict`

4. **`ToolRegistry`** → `/server/llm/tools.py`
   - Tool definition storage
   - Tool handler registry
   - Methods:
     - `get_all_tools() -> list[dict]`
     - `get_tool_handler(name) -> Callable`

5. **`ToolExecutor`** → `/server/llm/executor.py`
   - Executes tool calls from LLM
   - Coordinates with TerminalService
   - Methods:
     - `async execute(tool_call: ToolCall) -> str`
     - `get_all_tools() -> list[dict]`

6. **`LLMEngine`** → `/server/llm/engine.py` (expand stub)
   - Routes to appropriate LLM provider
   - Configuration-based selection
   - Methods:
     - `async generate(...) -> LLMResponse`

---

## Data Classes to Consolidate

**Problem:** Multiple Enum definitions with same purpose

**Current State:**
- `terminal_chatbot.SessionState` (IDLE, RUNNING, WAITING_INPUT, UNKNOWN)
- `iterm2_control.SessionState` (IDLE, RUNNING, UNKNOWN)
- `tmux_control.PaneState` (IDLE, RUNNING, UNKNOWN)
- `server/adapters/base.py.TerminalState` (already exists!)

**Solution:** Use single `TerminalState` from `/server/adapters/base.py`

---

## Import Structure After Migration

```python
# Adapters
from server.adapters.iterm2 import ITerm2Adapter
from server.adapters.tmux import TmuxAdapter
from server.adapters.unified import UnifiedAdapter
from server.adapters.models import UnifiedSession, CommandResult, TerminalType

# Core Services
from server.core.terminal import TerminalService
from server.core.analysis import AnalysisService

# LLM
from server.llm.client import ILLMClient, LLMMessage, ToolCall
from server.llm.openrouter import OpenRouterClient
from server.llm.tools import ToolRegistry
from server.llm.executor import ToolExecutor
from server.llm.engine import LLMEngine

# Application
from server.services.chatbot import TerminalChatbot

# Configuration
from server.config import Settings
from server.container import Container

# API
from server.api.routes import router
from server.api.schemas import ChatRequest, ChatResponse
```

---

## No Changes Needed (Already Production-Ready)

These files/components already exist and are usable:

- `/server/adapters/base.py` - ITerminalAdapter protocol ✓
- `/server/config.py` - Settings (will be extended) ✓
- `/server/container.py` - DI container (will be filled) ✓
- `/server/api/routes.py` - FastAPI routes (will be implemented) ✓
- `/server/api/dependencies.py` - FastAPI deps (will be updated) ✓
- `/pyproject.toml` - Dependencies (all present) ✓

---

## Code Patterns to Preserve

1. **Async/Await throughout** - POC uses async correctly
2. **Type Hints on all methods** - Maintain full type safety
3. **Docstrings** - Module and class docstrings with context
4. **Error Handling** - Try/except with meaningful messages
5. **Heuristics for Prompt Detection** - Excellent implementation to keep
6. **Output Analysis Logic** - Sophisticated analysis of terminal output
7. **Tool Definition Schema** - OpenAI-compatible format

---

## Testing Considerations

### Test Doubles to Create

1. **Mock iterm2.Connection** - Fixture for iTerm2 API
2. **Mock libtmux.Server** - Fixture for tmux API
3. **Mock httpx.AsyncClient** - Fixture for HTTP calls
4. **Mock UnifiedAdapter** - For TerminalService tests
5. **Mock ILLMClient** - For ToolExecutor tests

### Test Coverage Goals

- Adapters: >85% coverage
- Services: >80% coverage
- LLM Layer: >85% coverage
- API Routes: >80% coverage

---

**Inventory Status:** Complete
**Total LOC to Migrate:** ~1,300
**New LOC to Create:** ~500-700
**Modified Files:** ~12
**New Files:** ~18

