# TermPilot POC → Production Migration Checklist

## Quick Reference

**Source Code Base:** 2,271 LOC across 3 files
**Estimated Production Code:** ~1,800 LOC after refactoring
**Integration Points:** 4 major (adapters, services, LLM, API)
**Dependency Injection:** Via `dependency-injector` framework (already in project)

---

## Phase 1: Foundation Layer (Adapters)

### 1.1 Implement iTerm2Adapter
- [ ] Create `/server/adapters/iterm2.py`
- [ ] Copy `ITerm2Controller` from POC as starting point
- [ ] Implement `ITerminalAdapter` protocol
- [ ] Convert `SessionInfo` dataclass to match protocol
- [ ] Update method signatures to match protocol
- [ ] Add proper async context handling for iterm2.Connection
- [ ] Add error handling and logging
- [ ] Write unit tests (mock iterm2 API)
- [ ] **Expected LOC:** ~280 (vs 300 in POC)

### 1.2 Implement TmuxAdapter
- [ ] Create `/server/adapters/tmux.py`
- [ ] Copy `TmuxController` from POC as starting point
- [ ] Implement `ITerminalAdapter` protocol
- [ ] **Async Conversion:** Wrap all sync libtmux calls:
  - [ ] `def connect()` → `async def connect()`
  - [ ] `def list_sessions()` → `async def list_sessions()`
  - [ ] All other methods similarly
  - [ ] Use `asyncio.to_thread()` for sync libtmux calls
  - [ ] Or: Create thread pool executor in container
- [ ] Consolidate TmuxSessionInfo/WindowInfo/PaneInfo to match protocol
- [ ] Add error handling and logging
- [ ] Write unit tests (mock libtmux)
- [ ] **Expected LOC:** ~320 (vs 250 in POC + async overhead)

### 1.3 Create UnifiedAdapter
- [ ] Create `/server/adapters/unified.py`
- [ ] Extract orchestration logic from `UnifiedTerminalManager`
- [ ] Implement adapter coordination logic:
  - [ ] `async def connect()` - manages both adapters
  - [ ] `async def list_sessions()` - aggregates from both
  - [ ] `async def send_command()` - routes by session type
  - [ ] `async def detect_state()` - unified state detection
  - [ ] `async def get_session_status()` - comprehensive analysis
- [ ] Extract analysis methods:
  - [ ] `_analyze_session_status()` - output analysis
  - [ ] `_generate_screen_summary()` - content summarization
  - [ ] Prompt detection heuristics
  - [ ] Working/progress detection
  - [ ] Waiting-for-input detection
- [ ] Session cache management
- [ ] Add logging
- [ ] Write unit tests
- [ ] **Expected LOC:** ~350

### 1.4 Type Consolidation
- [ ] Update `/server/adapters/base.py`:
  - [ ] Verify `TerminalState` enum matches POC usage:
    ```python
    class TerminalState(Enum):
        IDLE = "idle"
        RUNNING = "running"
        WAITING_INPUT = "waiting_input"
        UNKNOWN = "unknown"
    ```
  - [ ] Update `SessionInfo` dataclass to include POC fields
  - [ ] Add type hints to protocol methods
- [ ] Create `/server/adapters/models.py` for shared data classes:
  - [ ] `UnifiedSession` - cross-adapter session representation
  - [ ] `CommandResult` - command execution result
  - [ ] `TerminalType` enum (ITERM2, TMUX)
  - [ ] `AnalysisResult` dataclass
- [ ] Update imports across adapter modules
- [ ] **Expected LOC:** ~80

**Checklist Subtotal Phase 1:**
- [ ] 4 new adapter files created
- [ ] All POC controller logic migrated and wrapped
- [ ] All adapters implement protocol
- [ ] Type system consolidated
- [ ] Async/sync compatibility resolved
- [ ] ~1,030 LOC in adapters layer

---

## Phase 2: Core Services Layer

### 2.1 Create TerminalService
- [ ] Create `/server/core/terminal.py` (or rename session.py)
- [ ] Extract from `UnifiedTerminalManager`:
  - [ ] Main orchestration methods
  - [ ] Session state detection
  - [ ] Command execution with timeout
  - [ ] Output fetching
- [ ] Interface methods:
  - [ ] `async def get_all_sessions()` - list from all backends
  - [ ] `async def execute_command()` - send command + wait
  - [ ] `async def get_session_output()` - fetch recent output
  - [ ] `async def get_session_status()` - comprehensive analysis
  - [ ] `async def monitor_session()` - streaming output
- [ ] Dependency injection:
  - [ ] Inject `UnifiedAdapter` (not hardcoded)
  - [ ] Inject `Logger`
- [ ] Error handling and validation
- [ ] Unit tests
- [ ] **Expected LOC:** ~250

### 2.2 Create Analysis Service (Optional but Recommended)
- [ ] Create `/server/core/analysis.py`
- [ ] Extract analysis logic from UnifiedManager:
  - [ ] `analyze_session_status(output: str) -> AnalysisResult`
  - [ ] `generate_screen_summary(lines, status, indicators) -> str`
  - [ ] `detect_prompt_indicators(output: str) -> bool`
  - [ ] `detect_working_indicators(output: str) -> bool`
  - [ ] `detect_waiting_indicators(output: str) -> bool`
- [ ] Make heuristics configurable/overrideable
- [ ] Write focused unit tests for patterns
- [ ] **Expected LOC:** ~200

### 2.3 Update SessionManager (stub → implementation)
- [ ] Update `/server/core/session.py`:
  - [ ] Remove or refactor stub
  - [ ] May become facade or can be merged into TerminalService
  - [ ] Or: Keep as higher-level coordination layer
- [ ] Decide: Merge with TerminalService or separate?
- [ ] **Expected LOC:** 0-100 (depends on decision)

**Checklist Subtotal Phase 2:**
- [ ] 2-3 service files created/updated
- [ ] Analysis logic extracted and testable
- [ ] Dependency injection ready
- [ ] ~450 LOC in services layer

---

## Phase 3: LLM Integration Layer

### 3.1 Create LLMClient Protocol
- [ ] Create `/server/llm/client.py`
- [ ] Define abstract `ILLMClient` protocol:
  ```python
  class ILLMClient(Protocol):
      async def chat(
          messages: list[LLMMessage],
          tools: list[dict] = None,
          **kwargs
      ) -> tuple[str, list[ToolCall]]: ...
  ```
- [ ] Define shared data classes:
  - [ ] `LLMMessage` (from POC)
  - [ ] `ToolCall` (from POC)
  - [ ] `LLMConfig` (provider, model, params)
- [ ] **Expected LOC:** ~80

### 3.2 Implement OpenRouterClient
- [ ] Create `/server/llm/openrouter.py`
- [ ] Copy `OpenRouterClient` from POC
- [ ] Adapt to implement `ILLMClient` protocol
- [ ] Update configuration:
  - [ ] Load API key from Settings
  - [ ] Support configurable model
  - [ ] Add timeout configuration
  - [ ] Add retry logic
- [ ] Add proper logging
- [ ] Error handling and validation
- [ ] Unit tests (mock httpx)
- [ ] **Expected LOC:** ~120

### 3.3 Create ToolRegistry
- [ ] Create `/server/llm/tools.py`
- [ ] Extract tool definitions from POC:
  - [ ] `list_sessions` tool schema
  - [ ] `get_session_state` tool schema
  - [ ] `get_session_status` tool schema
  - [ ] `send_command` tool schema
  - [ ] `get_session_output` tool schema
- [ ] Tool schema builders (DRY):
  ```python
  def build_tool_schema(name, description, parameters) -> dict
  ```
- [ ] Tool registry/loader:
  ```python
  class ToolRegistry:
      def get_all_tools() -> list[dict]
      def get_tool_handler(name) -> Callable
  ```
- [ ] **Expected LOC:** ~150

### 3.4 Implement LLMEngine (Full)
- [ ] Update `/server/llm/engine.py`:
  - [ ] Remove stub implementation
  - [ ] Implement provider routing (local vs openrouter)
  - [ ] Request/response conversion
  - [ ] Error handling and fallbacks
  - [ ] Logging
- [ ] Support multiple providers (stub for local)
- [ ] Configuration-based provider selection
- [ ] **Expected LOC:** ~100

### 3.5 Create ToolExecutor Service
- [ ] Create `/server/llm/executor.py`
- [ ] Extract from `TerminalChatbot.execute_tool()`:
  - [ ] Tool call dispatcher
  - [ ] Result serialization (JSON)
  - [ ] Error handling
  - [ ] Timeout management
- [ ] Dependency injection:
  - [ ] Inject `TerminalService`
  - [ ] Inject `ToolRegistry`
- [ ] Unit tests
- [ ] **Expected LOC:** ~120

**Checklist Subtotal Phase 3:**
- [ ] 5 LLM-related files created/updated
- [ ] Tool system abstracted and extensible
- [ ] Multiple provider support structure
- [ ] ~570 LOC in LLM layer

---

## Phase 4: Application Services

### 4.1 Create TerminalChatbot Service
- [ ] Create `/server/services/chatbot.py` (new)
- [ ] Adapt `TerminalChatbot` from POC:
  - [ ] Conversation state management
  - [ ] Message history tracking
  - [ ] Tool execution loop
  - [ ] Response generation
- [ ] System prompt management:
  - [ ] Keep existing prompt strategy
  - [ ] Make prompt configurable
  - [ ] Support multiple system prompts
- [ ] Dependency injection:
  - [ ] Inject `ILLMClient` (not OpenRouterClient directly)
  - [ ] Inject `ToolExecutor`
  - [ ] Inject `TerminalService`
  - [ ] Inject configuration
- [ ] Error handling and logging
- [ ] Unit tests (mock dependencies)
- [ ] **Expected LOC:** ~180

### 4.2 Create or Update SessionManager (if still needed)
- [ ] Decide: Is SessionManager a coordinator or service?
- [ ] Options:
  1. Rename TerminalService to SessionManager
  2. Keep SessionManager as facade over TerminalService + TerminalChatbot
  3. Remove SessionManager (if TerminalService is sufficient)
- [ ] **Expected LOC:** 0-50

**Checklist Subtotal Phase 4:**
- [ ] 1-2 service files created
- [ ] Chatbot fully extracted and injectable
- [ ] ~180-230 LOC in services layer

---

## Phase 5: API Layer Integration

### 5.1 Create Request/Response Schemas
- [ ] Create `/server/api/schemas.py`:
  - [ ] `SendCommandRequest` / `SendCommandResponse`
  - [ ] `ListSessionsResponse`
  - [ ] `GetSessionStatusRequest` / `GetSessionStatusResponse`
  - [ ] `ChatRequest` / `ChatResponse`
  - [ ] Error schemas
- [ ] Use Pydantic for validation
- [ ] **Expected LOC:** ~150

### 5.2 Create Route Handlers
- [ ] Create `/server/api/handlers.py` (optional, for organization):
  - [ ] Session endpoints
  - [ ] Chatbot endpoints
  - [ ] Status endpoints
- [ ] Or: Add to existing `routes.py`
- [ ] Handlers use dependency injection:
  - [ ] Inject `TerminalService`
  - [ ] Inject `TerminalChatbot`
- [ ] **Expected LOC:** ~200-300

### 5.3 Update routes.py
- [ ] Update `/server/api/routes.py`:
  - [ ] Add new endpoints:
    - [ ] `GET /api/sessions` - list all sessions
    - [ ] `GET /api/sessions/{id}/status` - get status
    - [ ] `POST /api/sessions/{id}/command` - execute command
    - [ ] `POST /api/chat` - chatbot endpoint
    - [ ] `WebSocket /api/chat/stream` - (optional streaming)
  - [ ] Proper error handling (400, 404, 500)
  - [ ] Request validation
  - [ ] Response formatting
- [ ] **Expected LOC:** ~200

### 5.4 Update dependencies.py
- [ ] Update `/server/api/dependencies.py`:
  - [ ] Add dependency functions for injected services
  - [ ] Example:
    ```python
    async def get_terminal_service(
        container: Container = Depends(get_container)
    ) -> TerminalService:
        return container.terminal_service()
    ```
  - [ ] May already have patterns for this
- [ ] **Expected LOC:** ~50

**Checklist Subtotal Phase 5:**
- [ ] 1-3 API files created/updated
- [ ] Full REST endpoint coverage
- [ ] Proper schema validation
- [ ] ~600 LOC in API layer

---

## Phase 6: Dependency Injection Configuration

### 6.1 Update Container
- [ ] Update `/server/container.py`:
  - [ ] Add Adapter providers:
    - [ ] `iterm2_adapter = providers.Factory(ITerm2Adapter)`
    - [ ] `tmux_adapter = providers.Factory(TmuxAdapter)`
    - [ ] `unified_adapter = providers.Singleton(UnifiedAdapter, ...)`
  - [ ] Add Service providers:
    - [ ] `terminal_service = providers.Singleton(TerminalService, ...)`
    - [ ] `analysis_service = providers.Factory(AnalysisService)`
  - [ ] Add LLM providers:
    - [ ] `llm_client = providers.Factory(...)` (based on config)
    - [ ] `tool_executor = providers.Factory(ToolExecutor, ...)`
    - [ ] `tool_registry = providers.Singleton(ToolRegistry)`
  - [ ] Add Application providers:
    - [ ] `chatbot = providers.Factory(TerminalChatbot, ...)`
- [ ] Wire dependencies correctly (factory vs singleton)
- [ ] **Expected LOC:** ~50-80

### 6.2 Update main.py
- [ ] Update `/server/main.py`:
  - [ ] Initialize container at startup
  - [ ] Connect adapters during app startup
  - [ ] Cleanup on shutdown
  - [ ] Example:
    ```python
    container = Container()
    app = FastAPI()

    @app.on_event("startup")
    async def startup():
        await container.unified_adapter().connect()

    @app.on_event("shutdown")
    async def shutdown():
        await container.unified_adapter().close()
    ```
- [ ] **Expected LOC:** ~30-50

**Checklist Subtotal Phase 6:**
- [ ] 2 files updated (container + main)
- [ ] All dependencies wired
- [ ] ~80-130 LOC changes

---

## Phase 7: Configuration & Startup

### 7.1 Update Settings (server/config.py)
- [ ] Add LLM configuration:
  - [ ] `llm_provider: str = "openrouter"` (or "local")
  - [ ] `openrouter_api_key: Optional[str]`
  - [ ] `openrouter_model: str = "anthropic/claude-sonnet-4"`
  - [ ] `llm_temperature: float = 0.7`
  - [ ] `llm_timeout: float = 60.0`
- [ ] Add Terminal configuration:
  - [ ] `terminal_backends: list[str] = ["tmux", "iterm2"]`
  - [ ] `session_cache_ttl: int = 300` (seconds)
  - [ ] `command_timeout: float = 30.0`
- [ ] Add Analysis configuration:
  - [ ] `analysis_output_lines: int = 100`
  - [ ] `status_summary_enabled: bool = True`
- [ ] Validate critical settings at startup
- [ ] **Expected LOC:** ~30

### 7.2 Create Startup Sequence
- [ ] Document initialization order in main.py docstring
- [ ] Verify all dependencies resolve correctly
- [ ] Add health check endpoint:
  - [ ] `/api/health` returns adapter status
  - [ ] Checks iTerm2 and tmux availability
- [ ] **Expected LOC:** ~50

**Checklist Subtotal Phase 7:**
- [ ] Settings fully configured
- [ ] Startup sequence documented
- [ ] ~80 LOC total

---

## Phase 8: Testing Setup

### 8.1 Create Test Structure
- [ ] `/tests/unit/adapters/` - adapter unit tests
- [ ] `/tests/unit/services/` - service unit tests
- [ ] `/tests/unit/llm/` - LLM unit tests
- [ ] `/tests/integration/` - integration tests
- [ ] `/tests/fixtures/` - shared test fixtures
- [ ] Update `/tests/conftest.py` for pytest configuration

### 8.2 Adapter Tests
- [ ] `test_iterm2_adapter.py` - Mock iterm2 API
- [ ] `test_tmux_adapter.py` - Mock libtmux
- [ ] `test_unified_adapter.py` - Mock both adapters
- [ ] Coverage target: >85%

### 8.3 Service Tests
- [ ] `test_terminal_service.py` - Mock adapters
- [ ] `test_analysis_service.py` - Pattern detection tests
- [ ] `test_chatbot_service.py` - Mock LLM and executor
- [ ] Coverage target: >80%

### 8.4 LLM Tests
- [ ] `test_openrouter_client.py` - Mock HTTP client
- [ ] `test_tool_executor.py` - Tool execution logic
- [ ] `test_tool_registry.py` - Tool registration
- [ ] Coverage target: >85%

### 8.5 API Tests
- [ ] `test_api_endpoints.py` - Mock services
- [ ] Integration test: End-to-end request flow
- [ ] Coverage target: >80%

### 8.6 Running Tests
- [ ] Update CI/CD pipeline (if exists)
- [ ] Document: `pytest tests/ --cov=server`
- [ ] Pre-commit hooks for type checking

**Checklist Subtotal Phase 8:**
- [ ] 5+ test modules created
- [ ] >80% coverage target
- [ ] Integration tests covering full flow

---

## Phase 9: Cleanup & Documentation

### 9.1 Archive POC Scripts
- [ ] Move POC scripts to `/docs/archive/poc/`:
  - [ ] `scripts/poc/terminal_chatbot.py` → archive
  - [ ] `scripts/poc/iterm2_control.py` → archive
  - [ ] `scripts/poc/tmux_control.py` → archive
  - [ ] Keep `hello_world.py` as basic demo (or update)
- [ ] Keep POC analysis docs for reference
- [ ] Update README to point to production code

### 9.2 Update Documentation
- [ ] Update `/README.md`:
  - [ ] Point to production API docs
  - [ ] Remove POC references
  - [ ] Add API usage examples
  - [ ] Add chatbot usage examples
- [ ] Create `/docs/API.md`:
  - [ ] Endpoint reference
  - [ ] Example requests/responses
  - [ ] Error codes
  - [ ] Rate limiting (if applicable)
- [ ] Create `/docs/ARCHITECTURE.md`:
  - [ ] Layer descriptions
  - [ ] Component responsibilities
  - [ ] Data flow diagrams
  - [ ] Dependency injection config
- [ ] Create `/docs/DEVELOPMENT.md`:
  - [ ] Setup instructions
  - [ ] Running tests
  - [ ] Adding new terminals (extending adapters)
  - [ ] Adding new tools

### 9.3 Code Review & Cleanup
- [ ] Remove commented-out code
- [ ] Ensure all type hints are present
- [ ] Run linting: `ruff check server`
- [ ] Run type checking: `mypy server`
- [ ] Ensure docstrings on all public APIs
- [ ] Check for TODO/FIXME comments

**Checklist Subtotal Phase 9:**
- [ ] POC archived
- [ ] Documentation updated
- [ ] Code quality verified

---

## Phase 10: Final Integration & Testing

### 10.1 End-to-End Testing
- [ ] Manual test: Start server with actual tmux session
- [ ] Manual test: Start server with actual iTerm2 session
- [ ] Test chatbot interaction:
  - [ ] List sessions
  - [ ] Send command to session
  - [ ] Receive and parse response
  - [ ] LLM processes tool call
  - [ ] Result returned to user
- [ ] Test error cases:
  - [ ] No sessions available
  - [ ] Invalid session ID
  - [ ] Command timeout
  - [ ] LLM API error
  - [ ] Network interruption

### 10.2 Performance Testing (Optional)
- [ ] Load test: Many concurrent requests
- [ ] Benchmark: Command execution latency
- [ ] Monitor: Memory usage for session caching

### 10.3 Security Review
- [ ] Validate API key handling (not logged/exposed)
- [ ] Input validation on all endpoints
- [ ] Rate limiting (if needed)
- [ ] CORS configuration (if needed)
- [ ] Auth token validation (from Settings)

**Checklist Subtotal Phase 10:**
- [ ] Manual testing complete
- [ ] All endpoints functional
- [ ] Error cases handled
- [ ] Performance acceptable

---

## Dependency Summary

### Adapters depend on:
```
ITerm2Adapter:
  - iterm2.Connection (external)
  - TerminalState, SessionInfo (base.py)

TmuxAdapter:
  - libtmux.Server (external)
  - asyncio.to_thread() (stdlib)
  - TerminalState, SessionInfo (base.py)

UnifiedAdapter:
  - ITerm2Adapter, TmuxAdapter (siblings)
  - models.py (UnifiedSession, AnalysisResult)
```

### Services depend on:
```
TerminalService:
  - UnifiedAdapter (from adapters)
  - AnalysisService (if separate)

AnalysisService:
  - models.py (AnalysisResult)
```

### LLM Layer depends on:
```
OpenRouterClient:
  - httpx.AsyncClient (external)
  - Settings (config.py)

ToolExecutor:
  - TerminalService (from services)
  - ToolRegistry
  - models.py

TerminalChatbot:
  - ILLMClient protocol
  - ToolExecutor
  - TerminalService
```

### API Layer depends on:
```
Routes:
  - TerminalService (injected)
  - TerminalChatbot (injected)
  - schemas.py (DTOs)
```

### Container ties it all together:
```
Container -> Initializes all providers -> Injects into routes
```

---

## Implementation Order (Critical!)

1. **First:** Adapters (they're leaves - no dependencies)
   - iterm2_adapter.py
   - tmux_adapter.py
   - models.py
   - base.py (update)

2. **Second:** Core Services (depends on adapters)
   - terminal.py (TerminalService)
   - analysis.py (optional but recommended)

3. **Third:** LLM Layer (depends on services + new abstract clients)
   - client.py (ILLMClient protocol)
   - openrouter.py
   - tools.py
   - executor.py
   - engine.py (update)

4. **Fourth:** Application Services (depends on LLM + Terminal)
   - chatbot.py (TerminalChatbot service)

5. **Fifth:** API Layer (depends on all above)
   - schemas.py
   - handlers.py (or expand routes.py)
   - routes.py (update)
   - dependencies.py (update)

6. **Sixth:** DI Configuration (wires everything)
   - container.py (update)
   - main.py (update)
   - config.py (update)

7. **Seventh:** Testing (can be done in parallel)
   - unit tests for each layer
   - integration tests

8. **Eighth:** Documentation & Cleanup
   - Archive POC
   - Update docs
   - Code review

---

## Definition of Done (per phase)

**Phase 1 Complete When:**
- [ ] All 4 adapter files exist
- [ ] All implement ITerminalAdapter protocol
- [ ] iTerm2Adapter passes unit tests
- [ ] TmuxAdapter passes unit tests (async wrapping works)
- [ ] UnifiedAdapter passes unit tests

**Phase 2 Complete When:**
- [ ] TerminalService fully implements orchestration logic
- [ ] AnalysisService (if created) has testable analysis methods
- [ ] All methods have proper error handling
- [ ] Service tests pass

**Phase 3 Complete When:**
- [ ] ILLMClient protocol defined
- [ ] OpenRouterClient implements protocol
- [ ] ToolRegistry has all terminal tools
- [ ] ToolExecutor handles tool calls
- [ ] All LLM tests pass

**Phase 4 Complete When:**
- [ ] TerminalChatbot service created
- [ ] Conversation loop works correctly
- [ ] Tool execution integrated
- [ ] Service tests pass

**Phase 5 Complete When:**
- [ ] All endpoints implemented
- [ ] Schemas defined with validation
- [ ] Error handling consistent
- [ ] API tests pass

**Phase 6 Complete When:**
- [ ] Container fully configured
- [ ] All dependencies resolve
- [ ] main.py initializes container
- [ ] No hardcoded dependencies

**Phase 7 Complete When:**
- [ ] Settings has all required config
- [ ] Startup sequence documented
- [ ] Health check working
- [ ] Configuration validated

**Phase 8 Complete When:**
- [ ] Test structure in place
- [ ] >80% code coverage
- [ ] All unit tests passing
- [ ] Integration tests passing

**Phase 9 Complete When:**
- [ ] POC archived
- [ ] All documentation updated
- [ ] Code linting/type checking passing
- [ ] No TODO/FIXME comments

**Phase 10 Complete When:**
- [ ] Manual end-to-end testing done
- [ ] Error cases handled
- [ ] Performance acceptable
- [ ] Ready for deployment

---

## Quick Wins (High Priority)

Start with these to show progress quickly:

1. **Week 1:**
   - [ ] Create adapter files from POC (copy/refactor)
   - [ ] Update base.py and models.py
   - [ ] Wire adapters in container

2. **Week 2:**
   - [ ] Create TerminalService from UnifiedManager
   - [ ] Extract AnalysisService
   - [ ] Create tests for adapters/services

3. **Week 3:**
   - [ ] Create LLM layer (client protocol + OpenRouterClient)
   - [ ] Extract tool definitions and registry
   - [ ] Create ToolExecutor

4. **Week 4:**
   - [ ] Create TerminalChatbot service
   - [ ] Update API routes
   - [ ] Wire everything in container
   - [ ] Manual testing

---

## Risk Areas & Mitigations

| Risk | Mitigation |
|------|-----------|
| Async/sync mismatch in tmux adapter | Create thread pool, test thoroughly |
| Session ID parsing is fragile | Add validation, consider UUID approach |
| iTerm2 API missing session | Add null checks, graceful degradation |
| LLM API rate limits | Add retry logic, caching |
| Tool execution timeout | Make configurable, add logging |
| Prompt detection heuristics fail | Keep existing patterns, add config |
| Breaking POC scripts | Keep in archive, don't delete |

---

## Success Criteria

- [ ] All POC logic migrated to production code
- [ ] Zero hardcoded dependencies (all injected)
- [ ] 100% of endpoints working
- [ ] >80% code coverage
- [ ] All type hints present
- [ ] Async/sync properly handled
- [ ] Configuration externalized
- [ ] Documentation updated
- [ ] End-to-end test successful

---

**Estimated Total Time:** 3-4 weeks (with one developer)
**Estimated New LOC:** ~1,800-2,000
**Estimated Modified Files:** 10-12
**Estimated New Files:** 15-20
