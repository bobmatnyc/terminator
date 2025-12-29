# TermPilot POC Architecture Analysis

**Analysis Date:** December 8, 2025
**Focus:** Migration from POC scripts to production application with SOA/DI patterns

## Executive Summary

The TermPilot POC consists of three main Python modules (total 2,271 LOC) that demonstrate LLM-powered terminal control across iTerm2 and tmux backends. The architecture is well-structured with clear separation of concerns:

1. **Terminal Controllers** - Low-level abstractions for iTerm2 (async) and tmux (sync)
2. **Unified Manager** - Cross-platform abstraction layer with session state detection
3. **LLM Client** - OpenRouter API integration with tool/function calling
4. **Chatbot** - Stateful conversation handler with tool execution loop

The existing production structure in `/server/` already provides the SOA/DI foundation. Migration requires adapting POC components to use dependency injection while maintaining existing patterns.

---

## File Structure & Metrics

```
scripts/poc/
├── terminal_chatbot.py      (983 LOC) - Main chatbot + LLM client + unified manager
├── iterm2_control.py        (560 LOC) - iTerm2 adapter wrapper
├── tmux_control.py          (728 LOC) - tmux adapter wrapper
└── __init__.py

Production Structure:
server/
├── adapters/
│   ├── base.py              (57 LOC)  - ITerminalAdapter protocol
│   ├── iterm2.py            (stub)
│   └── tmux.py              (stub)
├── core/
│   ├── session.py           (stub)    - SessionManager
│   ├── events.py            (stub)    - Event types
│   └── security.py          (stub)    - Security/validation
├── llm/
│   ├── engine.py            (26 LOC)  - LLMEngine (stub)
│   └── __init__.py
├── config.py                (23 LOC)  - Settings + Pydantic
└── container.py             (21 LOC)  - Dependency Injection
```

---

## Classes & Functions to Migrate

### 1. Terminal Controllers

#### `iTerm2Controller` (iterm2_control.py)
**Type:** Async wrapper for iterm2 Python API
**Status:** Ready to migrate - minimal changes needed
**Lines:** ~300 (of 560 total in file)

**Key Methods:**
- `__init__(connection: iterm2.Connection)` - Initialize with active connection
- `async get_app() -> iterm2.App` - Get/cache app instance
- `async list_sessions() -> list[SessionInfo]` - List all open sessions
- `async create_window(profile=None) -> tuple[str, str]` - Create new window
- `async create_tab(window_id=None, profile=None) -> tuple[str, str]` - Create new tab
- `async split_pane(session_id, vertical=True) -> str` - Split pane
- `async send_text(session_id, text, newline=True, line_ending="\r") -> bool` - Send text
- `async get_screen_contents(session_id, lines=50) -> str` - Capture output
- `async get_screen_streamed(session_id, callback, duration=5.0)` - Stream updates
- `async close_session(session_id, force=False) -> bool` - Close session
- `async set_session_name(session_id, name)` - Rename session

**Data Classes:**
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

#### `TmuxController` (tmux_control.py)
**Type:** Sync wrapper for libtmux
**Status:** Ready to migrate - needs async adaptation
**Lines:** ~250 (of 728 total in file)

**Key Methods:**
- `__init__()` - Initialize (creates server lazily)
- `connect() -> bool` - Connect to tmux server
- `list_sessions() -> list[TmuxSessionInfo]` - List sessions
- `create_session(name, working_dir=None, attach=False) -> tuple[str, str, str]`
- `kill_session(session_name) -> bool` - Kill session
- `get_session(session_name) -> Optional[libtmux.Session]` - Get session object
- `list_windows(session_name) -> list[TmuxWindowInfo]` - List windows
- `create_window(session_name, window_name, working_dir=None) -> tuple[str, str]`
- `list_panes(session_name, window_index=0) -> list[TmuxPaneInfo]` - List panes
- `split_pane(session_name, window_index=0, vertical=True) -> str`
- `send_keys(session_name, keys, window_index=0, pane_index=0, enter=True) -> bool`
- `capture_pane(session_name, window_index, pane_index, lines) -> str` - Get output
- `detect_pane_state(session_name, window_index, pane_index) -> PaneState`

**Data Classes:**
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

### 2. Unified Terminal Manager

#### `UnifiedTerminalManager` (terminal_chatbot.py: lines 209-588)
**Type:** Cross-platform session abstraction
**Status:** Migrate with heavy refactoring - complex logic, good patterns
**Lines:** ~380

**Key Responsibilities:**
- Backend connection management (tmux + iTerm2)
- Unified session discovery and caching
- Session state detection (idle/running/waiting_input)
- Command execution with timeout handling
- Screen output analysis and status digesting

**Key Methods:**
```python
async def connect() -> dict[str, bool]
async def list_sessions() -> list[UnifiedSession]
async def get_session_output(session_id: str, lines: int) -> str
async def send_command(session_id, command, wait_for_completion, timeout) -> CommandResult
async def detect_state(session_id: str) -> SessionState
async def get_session_status(session_id: str) -> dict  # Comprehensive status
def _analyze_session_status(output: str) -> dict  # Output analysis
def _generate_screen_summary(lines, status, indicators) -> str  # Summarization
```

**Data Classes:**
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

class TerminalType(Enum):
    ITERM2 = "iterm2"
    TMUX = "tmux"

class SessionState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    UNKNOWN = "unknown"
```

**Analysis Logic Patterns:**
- Spinner/progress detection (animation characters)
- Prompt pattern recognition (shell indicators: $, #, >, etc.)
- Working keyword detection (running, building, compiling, etc.)
- Input waiting detection (password:, y/n, continue?, etc.)
- Screen content summarization

### 3. LLM Integration

#### `OpenRouterClient` (terminal_chatbot.py: lines 112-202)
**Type:** Async HTTP client for OpenRouter API
**Status:** Ready to migrate - clean, self-contained
**Lines:** ~90

**Key Methods:**
```python
async def chat(
    messages: list[LLMMessage],
    tools: list[dict] = None,
    temperature: float = 0.7
) -> tuple[str, list[ToolCall]]
```

**Data Classes:**
```python
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

**OpenAI Spec Handling:**
- Tool result message format (role="tool" with tool_call_id)
- Assistant message with tool calls
- Proper tool_choice auto handling
- Argument parsing (string→dict)

### 4. Terminal Chatbot

#### `TerminalChatbot` (terminal_chatbot.py: lines 725-864)
**Type:** Stateful conversation handler
**Status:** Migrate with refactoring - extract tool definitions
**Lines:** ~140

**Key Methods:**
```python
async def execute_tool(tool_call: ToolCall) -> str  # Tool dispatch
async def chat(user_input: str) -> str  # Main conversation loop
```

**Tool Definitions (inline - should extract):**
```
- list_sessions: List all terminal sessions
- get_session_state: Get idle/running state + output
- get_session_status: Status digest with analysis
- send_command: Execute command in session
- get_session_output: Get recent output
```

**System Prompt:** Comprehensive instruction set for natural communication

---

## Enums & Types to Migrate

```python
# From terminal_chatbot.py
class TerminalType(Enum): ITERM2, TMUX
class SessionState(Enum): IDLE, RUNNING, WAITING_INPUT, UNKNOWN

# From iterm2_control.py
class SessionState(Enum): IDLE, RUNNING, UNKNOWN

# From tmux_control.py
class PaneState(Enum): IDLE, RUNNING, UNKNOWN

# Should consolidate to server/adapters/base.py
class TerminalState(Enum): IDLE, RUNNING, WAITING_INPUT, UNKNOWN
```

---

## External Dependencies

### Direct Dependencies (in POC)
```
httpx>=0.25.0              # Async HTTP client
iterm2>=2.7                # iTerm2 Python API
libtmux>=0.28.0            # tmux wrapper
rich>=13.7.0               # Terminal UI/formatting
python-dotenv>=1.0.0       # Environment loading
```

### Existing Server Dependencies
```
fastapi>=0.104.0           # Web framework
uvicorn[standard]>=0.24.0  # ASGI server
pydantic>=2.5.0            # Data validation
pydantic-settings>=2.1.0   # Configuration
dependency-injector>=4.41.0 # Dependency injection
```

### No new dependencies needed for migration ✓

---

## Architecture Patterns in POC

### 1. Dependency Injection (Informal)
```python
# Current POC
def __init__(self, llm: OpenRouterClient, terminal_manager: UnifiedTerminalManager):
    self.llm = llm
    self.terminal = terminal_manager

# Target: Use dependency-injector framework
```

### 2. Protocol-Based Abstraction
```python
# Already exists in server/adapters/base.py
class ITerminalAdapter(Protocol):
    async def create_session(...) -> SessionInfo
    async def send_text(...) -> bool
    async def get_output(...) -> str
```

### 3. Async/Await Pattern
- iTerm2Controller: Fully async (iterm2 API is async)
- TmuxController: Sync (libtmux is sync)
- UnifiedTerminalManager: Async wrapper around both
- Chatbot: Async conversation loop

### 4. Stateful Conversation
```python
# TerminalChatbot maintains message history for context
self.messages: list[LLMMessage] = [
    LLMMessage(role="system", content=SYSTEM_PROMPT)
]
# Append user/assistant/tool messages for multi-turn dialogue
```

### 5. Tool Calling Pattern
```python
# LLM returns tool calls
response_text, tool_calls = await llm.chat(messages, tools=TERMINAL_TOOLS)

# Execute each tool
for tool_call in tool_calls:
    result = await execute_tool(tool_call)
    messages.append(LLMMessage(role="tool", content=result, ...))

# Continue until final response (no more tool calls)
```

### 6. Output Analysis & Heuristics
- Prompt pattern recognition (shell indicators)
- Progress/working indicator detection
- Waiting-for-input pattern matching
- Screen content summarization
- Completion keyword detection

---

## Component Dependencies Graph

```
TerminalChatbot
├─ OpenRouterClient
│  └─ httpx.AsyncClient
└─ UnifiedTerminalManager
   ├─ TmuxController (sync)
   │  └─ libtmux.Server
   └─ iTerm2Controller (async)
      ├─ iterm2.Connection
      └─ iterm2.App

Data Flow (chat request):
  User Input
    → TerminalChatbot.chat()
    → OpenRouterClient.chat()
    → Tool Call Loop:
        → TerminalChatbot.execute_tool()
        → UnifiedTerminalManager.{list_sessions,send_command,get_session_status}()
        → TmuxController OR iTerm2Controller
        → Result → LLMMessage(role="tool")
    → Final Response
```

---

## Recommended Production Architecture (SOA/DI)

### 1. **Adapter Layer** (Implement existing protocol)
```
server/adapters/
├── base.py           # ITerminalAdapter protocol ✓ (exists)
├── iterm2.py         # ITerm2Adapter(ITerminalAdapter)
│   └── wraps iTerm2Controller
├── tmux.py           # TmuxAdapter(ITerminalAdapter)
│   └── wraps TmuxController (async-wrapped)
└── unified.py        # NEW: UnifiedAdapter orchestrates both
```

### 2. **Core Services Layer**
```
server/core/
├── session.py        # SessionManager (coordinates adapters)
├── terminal.py       # NEW: TerminalService (high-level ops)
├── events.py         # ✓ (exists, for pub/sub)
└── security.py       # ✓ (exists, for validation)
```

### 3. **LLM Layer** (Extend existing)
```
server/llm/
├── engine.py         # LLMEngine (routing)
├── openrouter.py     # NEW: OpenRouterClient implementation
├── client.py         # NEW: Abstract LLMClient protocol
└── tools.py          # NEW: Tool definitions + execution
```

### 4. **API Layer** (Integrate services)
```
server/api/
├── routes.py         # ✓ (exists, FastAPI routes)
├── dependencies.py   # ✓ (exists, dependency injection)
├── schemas.py        # NEW: Request/response DTOs
└── handlers.py       # NEW: Route handlers using services
```

### 5. **Container Configuration**
```
server/container.py
# Add:
- OpenRouterClient provider
- LLMEngine provider
- TerminalChatbot provider
- Tool registry
```

---

## Migration Strategy

### Phase 1: Extract Adapters (Implement Protocols)
1. Implement `ITerm2Adapter` from `ITerm2Controller`
2. Implement `TmuxAdapter` from `TmuxController` (with async wrapping)
3. Create `UnifiedAdapter` from `UnifiedTerminalManager` logic

### Phase 2: Extract Services
1. Implement `TerminalService` with core logic
2. Create `LLMToolRegistry` for tool definitions
3. Implement `TerminalChatbot` as orchestration service

### Phase 3: Create API Layer
1. Define DTOs in `api/schemas.py`
2. Implement route handlers in `api/routes.py`
3. Wire dependencies in `api/dependencies.py`

### Phase 4: Wire DI Container
1. Register all providers in `container.py`
2. Update `main.py` to initialize container
3. Inject dependencies into route handlers

---

## Key Implementation Notes

### Async/Sync Compatibility
- iTerm2 is async-only → Use as-is
- tmux (libtmux) is sync → Wrap with `asyncio.to_thread()` or dedicated executor
- Option: Use thread pool for tmux operations

### Session ID Format
- **Current POC:** `"tmux:session:window:pane"` or `"iterm2:uuid"`
- **Recommendation:** Keep format, add validation in SessionInfo

### State Detection Heuristics
- Prompt patterns: $, #, >, >>>, ❯, ➜, %
- Spinner chars: ⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏|/-\\
- Progress patterns: [====, ===>, loading, %], etc.
- Completion keywords: done, complete, finished, success
- Keep all detection logic in TerminalService

### Tool Definition Organization
- Current: Defined inline in `TERMINAL_TOOLS` constant
- Recommended: Move to `server/llm/tools.py` with schema generators

### Configuration Integration
- Settings already supports env vars with `TERMPILOT_` prefix
- Add LLM provider selection logic to Settings
- Validate API keys at startup

---

## Testing Implications

### Unit Tests (New)
- `test_adapters/test_iterm2.py` - Mock iterm2 API
- `test_adapters/test_tmux.py` - Mock libtmux
- `test_adapters/test_unified.py` - Mock both adapters
- `test_services/test_terminal.py` - Service logic
- `test_llm/test_openrouter.py` - Mock HTTP client

### Integration Tests (New)
- `test_integration/test_session_flow.py` - Create/send/read cycle
- `test_integration/test_chatbot.py` - Full conversation flow

### Existing POC
- Can remain in `scripts/poc/` as reference
- Or convert to integration tests
- `hello_world.py` demonstrates basic usage

---

## Code Quality Standards to Maintain

1. **Type Hints:** All public methods have full type annotations ✓
2. **Docstrings:** Module and class docstrings for context
3. **Error Handling:** Try/except with meaningful messages
4. **Logging:** Use Python logging module (not prints)
5. **Validation:** Use Pydantic for data classes
6. **Configuration:** Environment-based settings via Pydantic
7. **Async/Await:** Proper async context managers, no blocking

---

## Summary Table

| Component | LOC | Status | Target Package | Notes |
|-----------|-----|--------|-----------------|-------|
| iTerm2Controller | 300 | Ready | `adapters/iterm2.py` | Minimal changes |
| TmuxController | 250 | Ready | `adapters/tmux.py` | Needs async wrapping |
| UnifiedTerminalManager | 380 | Refactor | `core/terminal.py` | Extract analysis logic |
| OpenRouterClient | 90 | Ready | `llm/openrouter.py` | Self-contained |
| TerminalChatbot | 140 | Refactor | `services/chatbot.py` | Extract tools |
| Tool Definitions | 100 | Extract | `llm/tools.py` | Schema definitions |
| Enums/Types | 40 | Consolidate | `adapters/base.py` | Already has protocol |
| **Total POC** | **2,271** | | | ~1,300 LOC migrating |

---

## Next Steps

1. **Create migration TODO list** with component ordering
2. **Set up test structure** for new packages
3. **Implement adapters first** (they're dependencies)
4. **Then services** (they use adapters)
5. **Then LLM layer** (uses tools and adapters)
6. **Finally API routes** (wire it all together)
7. **Update container** and main entry point
8. **Remove POC scripts** or archive as reference

---

**Document Status:** Analysis complete, ready for implementation planning
**Confidence Level:** High - POC is well-structured and POC patterns align with target architecture
