# TermPilot Recommended Dependency Injection Structure

## Overview

This document outlines the recommended dependency injection (DI) structure for TermPilot production application using the `dependency-injector` framework (already in the project).

---

## Core DI Principles Applied

1. **Protocol-Based Abstraction:** Components depend on protocols/interfaces, not implementations
2. **Single Responsibility:** Each service handles one concern
3. **Constructor Injection:** Dependencies passed via __init__, never created internally
4. **Lazy Instantiation:** Providers create instances only when needed
5. **Singleton Services:** Expensive resources (adapters, LLM clients) instantiated once
6. **Factory Services:** Lightweight services created per-request (if needed)
7. **Configuration Injection:** Settings passed to services for flexibility

---

## Container Architecture

```python
# server/container.py

from dependency_injector import containers, providers
from server.config import Settings
from server.adapters.iterm2 import ITerm2Adapter
from server.adapters.tmux import TmuxAdapter
from server.adapters.unified import UnifiedAdapter
from server.core.terminal import TerminalService
from server.core.analysis import AnalysisService
from server.llm.openrouter import OpenRouterClient
from server.llm.executor import ToolExecutor
from server.llm.tools import ToolRegistry
from server.llm.engine import LLMEngine
from server.services.chatbot import TerminalChatbot


class Container(containers.DeclarativeContainer):
    """
    Dependency injection container for TermPilot.

    Manages all service instances and wires dependencies.
    """

    # ===== CONFIGURATION =====
    config = providers.Configuration()
    settings = providers.Singleton(Settings)

    # ===== ADAPTERS LAYER =====
    # Low-level terminal adapters - lightweight factories

    iterm2_adapter = providers.Factory(
        ITerm2Adapter,
        settings=settings,  # Pass settings for configuration
    )

    tmux_adapter = providers.Factory(
        TmuxAdapter,
        settings=settings,
    )

    # Unified adapter - coordinates both backends
    # Singleton because it manages connection state
    unified_adapter = providers.Singleton(
        UnifiedAdapter,
        iterm2_adapter=iterm2_adapter,
        tmux_adapter=tmux_adapter,
        settings=settings,
    )

    # ===== CORE SERVICES LAYER =====
    # Business logic services

    analysis_service = providers.Factory(
        AnalysisService,
        settings=settings,
    )

    terminal_service = providers.Singleton(
        TerminalService,
        adapter=unified_adapter,
        analysis_service=analysis_service,
        settings=settings,
    )

    # ===== LLM LAYER =====
    # Language model integration

    tool_registry = providers.Singleton(
        ToolRegistry,
        # No dependencies - just tool definitions
    )

    # OpenRouter client - singleton (expensive connection)
    llm_client = providers.Singleton(
        OpenRouterClient,
        api_key=settings.provided.openrouter_api_key,
        model=settings.provided.openrouter_model,
        settings=settings,
    )

    # Tool executor - coordinates tool calls
    tool_executor = providers.Factory(
        ToolExecutor,
        terminal_service=terminal_service,
        tool_registry=tool_registry,
        settings=settings,
    )

    # LLM engine - routes to provider
    llm_engine = providers.Singleton(
        LLMEngine,
        llm_client=llm_client,
        settings=settings,
    )

    # ===== APPLICATION SERVICES LAYER =====
    # High-level application logic

    chatbot = providers.Factory(
        TerminalChatbot,
        llm_client=llm_client,
        terminal_service=terminal_service,
        tool_executor=tool_executor,
        settings=settings,
    )


# ===== USAGE IN MAIN.PY =====

from fastapi import FastAPI
from server.container import Container

# Global container instance
container = Container()

app = FastAPI()


@app.on_event("startup")
async def startup():
    """Initialize adapters on server startup."""
    # Get unified adapter and connect
    adapter = container.unified_adapter()
    status = await adapter.connect()
    # Log connection status...


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on server shutdown."""
    adapter = container.unified_adapter()
    await adapter.close()
```

---

## Dependency Injection in API Routes

### Pattern 1: FastAPI Dependency Function (Recommended)

```python
# server/api/dependencies.py

from fastapi import Depends
from server.container import container
from server.core.terminal import TerminalService
from server.services.chatbot import TerminalChatbot


async def get_terminal_service() -> TerminalService:
    """FastAPI dependency that provides TerminalService."""
    return container.terminal_service()


async def get_chatbot() -> TerminalChatbot:
    """FastAPI dependency that provides TerminalChatbot."""
    return container.chatbot()


# ===== USAGE IN ROUTES =====

# server/api/routes.py

from fastapi import APIRouter, Depends
from server.api.dependencies import get_terminal_service, get_chatbot
from server.api.schemas import ListSessionsResponse, SendCommandRequest, SendCommandResponse


router = APIRouter(prefix="/api")


@router.get("/sessions")
async def list_sessions(
    terminal_service: TerminalService = Depends(get_terminal_service)
) -> ListSessionsResponse:
    """List all available terminal sessions."""
    sessions = await terminal_service.get_all_sessions()
    return ListSessionsResponse(sessions=sessions)


@router.post("/sessions/{session_id}/command")
async def send_command(
    session_id: str,
    request: SendCommandRequest,
    terminal_service: TerminalService = Depends(get_terminal_service)
) -> SendCommandResponse:
    """Send a command to a session."""
    result = await terminal_service.execute_command(
        session_id,
        request.command,
        wait_for_completion=request.wait_for_completion
    )
    return SendCommandResponse(
        success=result.success,
        output=result.output,
        execution_time=result.execution_time
    )


@router.post("/chat")
async def chat(
    request: ChatRequest,
    chatbot: TerminalChatbot = Depends(get_chatbot)
) -> ChatResponse:
    """Send a message to the chatbot."""
    response = await chatbot.chat(request.message)
    return ChatResponse(message=response)
```

### Pattern 2: Direct Container Access (Alternative)

```python
# If you prefer to pass container instead

async def chat(request: ChatRequest) -> ChatResponse:
    """Alternative: Access container directly."""
    # Less preferred because it couples to container,
    # but works if FastAPI dependency injection isn't desired
    chatbot = container.chatbot()
    response = await chatbot.chat(request.message)
    return ChatResponse(message=response)
```

**Recommendation:** Use Pattern 1 (FastAPI Depends) for better testability and clarity.

---

## Adapter Implementation with DI

### ITerm2Adapter Example

```python
# server/adapters/iterm2.py

from server.config import Settings
from server.adapters.base import ITerminalAdapter, SessionInfo, TerminalState


class ITerm2Adapter(ITerminalAdapter):
    """
    Adapter for iTerm2 terminal control.

    Injected dependencies:
    - settings: Configuration
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._connection: Optional[iterm2.Connection] = None
        self._app: Optional[iterm2.App] = None
        self._sessions_cache: dict[str, SessionInfo] = {}

    async def connect(self) -> bool:
        """Connect to iTerm2."""
        try:
            self._connection = await iterm2.Connection.async_create()
            self._app = await iterm2.async_get_app(self._connection)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to iTerm2: {e}")
            return False

    async def list_sessions(self) -> list[SessionInfo]:
        """List all iTerm2 sessions."""
        # Implementation...
        pass

    # ... other methods
```

### UnifiedAdapter Example

```python
# server/adapters/unified.py

from typing import Optional
from server.adapters.iterm2 import ITerm2Adapter
from server.adapters.tmux import TmuxAdapter
from server.adapters.base import ITerminalAdapter, SessionInfo, TerminalState
from server.adapters.models import UnifiedSession, AnalysisResult
from server.config import Settings


class UnifiedAdapter:
    """
    Unified adapter managing both iTerm2 and tmux.

    Injected dependencies:
    - iterm2_adapter: ITerm2Adapter factory provider
    - tmux_adapter: TmuxAdapter factory provider
    - settings: Configuration
    """

    def __init__(
        self,
        iterm2_adapter: ITerm2Adapter,
        tmux_adapter: TmuxAdapter,
        settings: Settings,
    ):
        # Dependencies injected by container
        self.iterm2 = iterm2_adapter
        self.tmux = tmux_adapter
        self.settings = settings
        self._sessions_cache: dict[str, UnifiedSession] = {}

    async def connect(self) -> dict[str, bool]:
        """Connect to available backends."""
        status = {
            "iterm2": await self.iterm2.connect(),
            "tmux": await self.tmux.connect(),
        }
        return status

    async def list_sessions(self) -> list[UnifiedSession]:
        """List all sessions from both backends."""
        # Implementation...
        pass

    # ... other methods
```

### TerminalService Example

```python
# server/core/terminal.py

from server.adapters.unified import UnifiedAdapter
from server.core.analysis import AnalysisService
from server.config import Settings


class TerminalService:
    """
    High-level terminal control service.

    Injected dependencies:
    - adapter: UnifiedAdapter (singleton) - manages terminal connections
    - analysis_service: AnalysisService - analyzes session output
    - settings: Configuration
    """

    def __init__(
        self,
        adapter: UnifiedAdapter,
        analysis_service: AnalysisService,
        settings: Settings,
    ):
        self.adapter = adapter
        self.analysis_service = analysis_service
        self.settings = settings

    async def get_all_sessions(self) -> list[SessionInfo]:
        """Get all sessions from all backends."""
        return await self.adapter.list_sessions()

    async def execute_command(
        self,
        session_id: str,
        command: str,
        wait_for_completion: bool = True,
    ) -> CommandResult:
        """Execute a command in a session."""
        return await self.adapter.send_command(
            session_id,
            command,
            wait_for_completion=wait_for_completion,
            timeout=self.settings.command_timeout,
        )

    async def get_session_status(self, session_id: str) -> dict:
        """Get comprehensive status of a session."""
        output = await self.adapter.get_session_output(session_id)
        analysis = self.analysis_service.analyze_output(output)
        return analysis

    # ... other methods
```

---

## LLM Layer with DI

### OpenRouterClient with Settings

```python
# server/llm/openrouter.py

from server.config import Settings
from server.llm.client import ILLMClient, LLMMessage, ToolCall


class OpenRouterClient(ILLMClient):
    """
    OpenRouter API client.

    Injected dependencies:
    - api_key: From Settings.openrouter_api_key
    - model: From Settings.openrouter_model
    - settings: Full Settings for config options
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        settings: Settings,
    ):
        self.api_key = api_key
        self.model = model
        self.settings = settings
        self.base_url = "https://openrouter.ai/api/v1"
        self.timeout = settings.llm_timeout

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict] = None,
        **kwargs
    ) -> tuple[str, list[ToolCall]]:
        """Send chat completion request."""
        # Implementation...
        pass
```

### ToolExecutor with DI

```python
# server/llm/executor.py

from server.core.terminal import TerminalService
from server.llm.tools import ToolRegistry
from server.config import Settings


class ToolExecutor:
    """
    Executes tool calls from LLM.

    Injected dependencies:
    - terminal_service: TerminalService - for terminal operations
    - tool_registry: ToolRegistry - for tool definitions
    - settings: Configuration
    """

    def __init__(
        self,
        terminal_service: TerminalService,
        tool_registry: ToolRegistry,
        settings: Settings,
    ):
        self.terminal = terminal_service
        self.registry = tool_registry
        self.settings = settings

    async def execute(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return result."""
        tool_name = tool_call.name

        if tool_name == "list_sessions":
            sessions = await self.terminal.get_all_sessions()
            return json.dumps({"sessions": sessions})

        elif tool_name == "send_command":
            result = await self.terminal.execute_command(
                tool_call.arguments["session_id"],
                tool_call.arguments["command"],
            )
            return json.dumps({"success": result.success, "output": result.output})

        # ... other tool handlers
```

### TerminalChatbot with DI

```python
# server/services/chatbot.py

from server.llm.client import ILLMClient
from server.llm.executor import ToolExecutor
from server.core.terminal import TerminalService
from server.config import Settings


class TerminalChatbot:
    """
    Stateful chatbot for terminal interaction.

    Injected dependencies:
    - llm_client: ILLMClient - LLM for responses
    - terminal_service: TerminalService - terminal operations
    - tool_executor: ToolExecutor - tool execution
    - settings: Configuration
    """

    def __init__(
        self,
        llm_client: ILLMClient,
        terminal_service: TerminalService,
        tool_executor: ToolExecutor,
        settings: Settings,
    ):
        self.llm = llm_client
        self.terminal = terminal_service
        self.executor = tool_executor
        self.settings = settings
        self.messages: list[LLMMessage] = [
            LLMMessage(role="system", content=SYSTEM_PROMPT)
        ]

    async def chat(self, user_input: str) -> str:
        """Process user input and return response."""
        self.messages.append(LLMMessage(role="user", content=user_input))

        max_iterations = 10
        for iteration in range(max_iterations):
            response_text, tool_calls = await self.llm.chat(
                self.messages,
                tools=self.executor.get_all_tools(),
                temperature=self.settings.llm_temperature,
            )

            if not tool_calls:
                if response_text:
                    self.messages.append(
                        LLMMessage(role="assistant", content=response_text)
                    )
                return response_text

            # Process tool calls...
            # ... (implementation details)

        return "Max iterations reached"
```

---

## Singleton vs Factory Decisions

```
SINGLETON (Created once, reused):
├─ Settings - Single configuration for entire app
├─ UnifiedAdapter - Manages persistent connections
├─ TerminalService - Central business logic service
├─ ToolRegistry - Static tool definitions
├─ OpenRouterClient - Connection to external API
└─ LLMEngine - Routing logic

FACTORY (Created per-request or per-use):
├─ ITerm2Adapter - Lightweight wrapper
├─ TmuxAdapter - Lightweight wrapper
├─ AnalysisService - Pure logic, no state
├─ ToolExecutor - Per-request executor
└─ TerminalChatbot - One per conversation
```

**Rationale:**
- **Singletons:** Expensive resources (connections, network clients, complex state)
- **Factories:** Lightweight, stateless utilities or per-request processors

---

## Configuration Management

### Settings Injection Pattern

```python
# server/config.py

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment."""

    # Server
    host: str = "127.0.0.1"
    port: int = 7777

    # Terminal adapters
    default_adapter: str = "tmux"
    terminal_backends: list[str] = ["tmux", "iterm2"]
    command_timeout: float = 30.0
    session_cache_ttl: int = 300

    # LLM Configuration
    llm_provider: str = "openrouter"  # or "local"
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "anthropic/claude-sonnet-4"
    llm_temperature: float = 0.7
    llm_timeout: float = 60.0

    # Local LLM
    local_llm_enabled: bool = True
    local_llm_model: str = "qwen2.5-coder:1.5b"

    # Analysis
    analysis_output_lines: int = 100
    status_summary_enabled: bool = True

    # Security
    auth_token: Optional[str] = None

    model_config = {
        "env_file": ".env",
        "env_prefix": "TERMPILOT_",
    }


# ===== USAGE IN CONTAINER =====

class Container(containers.DeclarativeContainer):
    settings = providers.Singleton(Settings)

    # Inject specific settings to clients
    llm_client = providers.Singleton(
        OpenRouterClient,
        api_key=settings.provided.openrouter_api_key,
        model=settings.provided.openrouter_model,
        settings=settings,
    )
```

**Key Pattern:** `settings.provided.field_name` allows lazy injection of specific fields.

---

## Testing with DI

### Mock Services in Tests

```python
# tests/unit/services/test_chatbot.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from server.services.chatbot import TerminalChatbot
from server.llm.client import ILLMClient
from server.core.terminal import TerminalService
from server.llm.executor import ToolExecutor


@pytest.fixture
def mock_llm_client():
    """Mocked LLM client."""
    client = AsyncMock(spec=ILLMClient)
    client.chat.return_value = ("Hello", [])
    return client


@pytest.fixture
def mock_terminal_service():
    """Mocked terminal service."""
    service = AsyncMock(spec=TerminalService)
    service.get_all_sessions.return_value = []
    return service


@pytest.fixture
def mock_tool_executor():
    """Mocked tool executor."""
    executor = AsyncMock(spec=ToolExecutor)
    executor.get_all_tools.return_value = []
    return executor


@pytest.fixture
def mock_settings():
    """Mocked settings."""
    settings = MagicMock()
    settings.llm_temperature = 0.7
    settings.command_timeout = 30.0
    return settings


@pytest.fixture
def chatbot(mock_llm_client, mock_terminal_service, mock_tool_executor, mock_settings):
    """Create chatbot with mocked dependencies."""
    return TerminalChatbot(
        llm_client=mock_llm_client,
        terminal_service=mock_terminal_service,
        tool_executor=mock_tool_executor,
        settings=mock_settings,
    )


@pytest.mark.asyncio
async def test_chat_without_tools(chatbot, mock_llm_client):
    """Test chatbot response without tool calls."""
    mock_llm_client.chat.return_value = ("Hello user", [])

    response = await chatbot.chat("Hello")

    assert response == "Hello user"
    mock_llm_client.chat.assert_called_once()
```

**Key Pattern:** Inject mocks to test service in isolation.

---

## Container Configuration File Recommendation

For larger projects, separate container definition:

```python
# server/container.py - Keep short, just imports

from server.container_config import Container

# Then import and use:
# from server.container import Container
```

Or create specialized containers:

```python
# server/containers/adapters.py
# server/containers/services.py
# server/containers/llm.py

# Then combine in main container:
class Container(containers.DeclarativeContainer):
    adapters = containers.DependsOn(AdapterContainer)
    services = containers.DependsOn(ServiceContainer)
    llm = containers.DependsOn(LLMContainer)
```

---

## Startup Sequence

### Recommended main.py Structure

```python
# server/main.py

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from server.container import Container
from server.api import routes

logger = logging.getLogger(__name__)

# Create container instance
container = Container()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    Handles startup and shutdown events.
    """
    # STARTUP
    logger.info("Starting TermPilot...")

    # Initialize adapters
    adapter = container.unified_adapter()
    status = await adapter.connect()

    logger.info(f"Adapter status: {status}")

    if not any(status.values()):
        logger.warning("No terminal adapters available!")

    logger.info("TermPilot started successfully")

    yield  # App runs here

    # SHUTDOWN
    logger.info("Shutting down TermPilot...")
    await adapter.close()
    logger.info("TermPilot shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title="TermPilot",
    description="AI-powered terminal control system",
    version="0.1.0",
    lifespan=lifespan,
)


# Include routes
app.include_router(routes.router, prefix="/api", tags=["terminal"])


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    adapter = container.unified_adapter()
    return {
        "status": "healthy",
        "adapters": {
            "iterm2": adapter.iterm2 is not None,
            "tmux": adapter.tmux is not None,
        }
    }


if __name__ == "__main__":
    import uvicorn

    settings = container.settings()

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
```

---

## Environment Configuration Example

```bash
# .env

# Server
TERMPILOT_HOST=127.0.0.1
TERMPILOT_PORT=7777

# LLM
TERMPILOT_LLM_PROVIDER=openrouter
TERMPILOT_OPENROUTER_API_KEY=sk-xxx-yyy-zzz
TERMPILOT_OPENROUTER_MODEL=anthropic/claude-sonnet-4
TERMPILOT_LLM_TEMPERATURE=0.7
TERMPILOT_LLM_TIMEOUT=60

# Terminal
TERMPILOT_COMMAND_TIMEOUT=30
TERMPILOT_SESSION_CACHE_TTL=300

# Analysis
TERMPILOT_ANALYSIS_OUTPUT_LINES=100

# Security
TERMPILOT_AUTH_TOKEN=optional-api-key
```

---

## Summary: Dependency Flow

```
User Request (HTTP)
    ↓
FastAPI Route Handler
    ↓
Dependency: get_terminal_service()
    ↓
Container.terminal_service() [Singleton]
    ↓
TerminalService.__init__()
    ├─ Depends on: UnifiedAdapter [Singleton]
    │   └─ UnifiedAdapter.__init__()
    │       ├─ Depends on: ITerm2Adapter [Factory]
    │       ├─ Depends on: TmuxAdapter [Factory]
    │       └─ Depends on: Settings [Singleton]
    ├─ Depends on: AnalysisService [Factory]
    └─ Depends on: Settings [Singleton]
    ↓
Handler uses terminal_service to process request
    ↓
Response returned to client
```

---

## Best Practices

1. ✅ **Always inject dependencies** - Never import and instantiate in methods
2. ✅ **Use protocols for abstraction** - ITerminalAdapter, ILLMClient
3. ✅ **Configure singletons carefully** - Only for expensive/stateful resources
4. ✅ **Pass settings to services** - For flexible configuration
5. ✅ **Test with mocks** - Inject test doubles easily
6. ✅ **Keep container simple** - Separate concerns in different layers
7. ✅ **Document dependencies** - Add docstrings showing what's injected
8. ❌ **Don't hardcode imports** - Use injection instead
9. ❌ **Don't create singletons from factories** - Order matters
10. ❌ **Don't inject container itself** - Use specific services

---

## Migration Path: POC → Production

```python
# POC CODE
def __init__(self, llm: OpenRouterClient, terminal: UnifiedTerminalManager):
    self.llm = llm
    self.terminal = terminal

# With hardcoded initialization somewhere:
llm = OpenRouterClient(api_key=os.getenv("KEY"))
terminal = UnifiedTerminalManager()
chatbot = TerminalChatbot(llm, terminal)

# ↓↓↓ REFACTOR TO ↓↓↓

# PRODUCTION CODE
def __init__(
    self,
    llm_client: ILLMClient,  # Inject interface, not implementation
    terminal_service: TerminalService,
    tool_executor: ToolExecutor,
    settings: Settings,
):
    self.llm = llm_client
    self.terminal = terminal_service
    self.executor = tool_executor
    self.settings = settings

# With container-based initialization:
container = Container()
chatbot = container.chatbot()  # All dependencies automatically wired!
```

---

**This structure ensures:**
- Clear dependency relationships
- Easy testing with mocks
- Configuration flexibility
- Zero global state
- Easy to extend (new adapters, new tools, new LLM providers)

