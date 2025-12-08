"""
Terminal Chatbot POC - LLM-powered terminal control assistant.

This script demonstrates:
a) Listing open iTerm2 and/or tmux sessions
b) Determining terminal state (idle/running)
c) Sending commands to sessions
d) Interpreting results and detecting command completion
e) Explaining results to the user

Requirements:
- OpenRouter API key in .env.local or .env
- iTerm2 running (for iTerm2 sessions)
- tmux installed (for tmux sessions)

Usage:
    python -m scripts.runner poc.terminal_chatbot
    python -m scripts.runner poc.terminal_chatbot --provider openrouter
    python -m scripts.runner poc.terminal_chatbot --provider local
"""
import os
import sys
import json
import time
import asyncio
from typing import Optional, Literal
from dataclasses import dataclass, field
from enum import Enum

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner
from dotenv import load_dotenv

# Import our POC controllers
from scripts.poc.iterm2_control import ITerm2Controller, SessionInfo as ITermSessionInfo
from scripts.poc.tmux_control import TmuxController, TmuxSessionInfo, TmuxPaneInfo

console = Console()

# Load environment
load_dotenv(".env.local")
load_dotenv(".env")


class TerminalType(Enum):
    """Terminal backend type."""
    ITERM2 = "iterm2"
    TMUX = "tmux"


class SessionState(Enum):
    """Terminal session state."""
    IDLE = "idle"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    UNKNOWN = "unknown"


@dataclass
class UnifiedSession:
    """Unified session representation across terminal types."""
    id: str
    name: str
    terminal_type: TerminalType
    state: SessionState = SessionState.UNKNOWN
    last_output: str = ""
    cwd: str = ""
    # For tmux: window_index and pane_index
    window_index: int = 0
    pane_index: int = 0


@dataclass
class CommandResult:
    """Result of executing a command in a session."""
    success: bool
    output: str
    state_after: SessionState
    execution_time: float


# =============================================================================
# LLM Client
# =============================================================================

@dataclass
class LLMMessage:
    """Chat message."""
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list = field(default_factory=list)
    tool_call_id: Optional[str] = None


@dataclass
class ToolCall:
    """Tool call from LLM."""
    id: str
    name: str
    arguments: dict


class OpenRouterClient:
    """Client for OpenRouter API with tool support."""

    def __init__(self, api_key: str, model: str = "anthropic/claude-sonnet-4"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict] = None,
        temperature: float = 0.7
    ) -> tuple[str, list[ToolCall]]:
        """
        Send chat completion request.

        Returns:
            Tuple of (response_text, tool_calls)
        """
        async with httpx.AsyncClient() as client:
            # Format messages according to OpenRouter/OpenAI API requirements
            formatted_messages = []
            for m in messages:
                if m.role == "tool":
                    # Tool result message (OpenAI format)
                    # Note: name field is optional but can help with debugging
                    formatted_messages.append({
                        "role": "tool",
                        "content": m.content,
                        "tool_call_id": m.tool_call_id
                    })
                elif m.role == "assistant" and m.tool_calls:
                    # Assistant message with tool calls (OpenAI format)
                    # Per OpenAI spec, content can be empty string when tool_calls present
                    formatted_messages.append({
                        "role": "assistant",
                        "content": m.content or "",  # Empty string is valid
                        "tool_calls": m.tool_calls
                    })
                else:
                    # Regular user/system/assistant message
                    formatted_messages.append({
                        "role": m.role,
                        "content": m.content
                    })

            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": temperature,
            }

            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/bobmatnyc/termpilot",
                    "X-Title": "TermPilot"
                },
                json=payload,
                timeout=60.0
            )

            if response.status_code != 200:
                raise Exception(f"OpenRouter error: {response.status_code} - {response.text}")

            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]

            # Extract tool calls if present
            tool_calls = []
            if "tool_calls" in message and message["tool_calls"]:
                for tc in message["tool_calls"]:
                    # Handle both string and dict arguments
                    args = tc["function"].get("arguments", "{}")
                    if isinstance(args, str):
                        args = json.loads(args) if args else {}
                    tool_calls.append(ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=args
                    ))

            return message.get("content", ""), tool_calls


# =============================================================================
# Unified Terminal Manager
# =============================================================================

class UnifiedTerminalManager:
    """
    Manages both iTerm2 and tmux sessions through a unified interface.
    """

    def __init__(self):
        self.tmux: Optional[TmuxController] = None
        self.iterm2: Optional[ITerm2Controller] = None
        self._iterm2_connection = None
        self._sessions_cache: dict[str, UnifiedSession] = {}

    async def connect(self) -> dict[str, bool]:
        """Connect to available terminal backends."""
        status = {"tmux": False, "iterm2": False}

        # Try tmux
        try:
            self.tmux = TmuxController()
            if self.tmux.connect():
                status["tmux"] = True
            else:
                self.tmux = None
        except Exception as e:
            console.print(f"[dim]tmux not available: {e}[/dim]")
            self.tmux = None

        # Try iTerm2
        try:
            import iterm2
            self._iterm2_connection = await iterm2.Connection.async_create()
            self.iterm2 = ITerm2Controller(self._iterm2_connection)
            status["iterm2"] = True
        except Exception as e:
            console.print(f"[dim]iTerm2 not available: {e}[/dim]")
            self.iterm2 = None

        return status

    async def list_sessions(self) -> list[UnifiedSession]:
        """List all sessions from all backends."""
        sessions = []

        # Get tmux sessions
        if self.tmux:
            for ts in self.tmux.list_sessions():
                # Get panes for each session
                windows = self.tmux.list_windows(ts.session_name)
                for window in windows:
                    panes = self.tmux.list_panes(ts.session_name, window.window_index)
                    for pane in panes:
                        session_id = f"tmux:{ts.session_name}:{window.window_index}:{pane.pane_index}"
                        session = UnifiedSession(
                            id=session_id,
                            name=f"{ts.session_name}/{window.window_name}[{pane.pane_index}]",
                            terminal_type=TerminalType.TMUX,
                            cwd=pane.current_path,
                            window_index=window.window_index,
                            pane_index=pane.pane_index,
                        )
                        sessions.append(session)
                        self._sessions_cache[session_id] = session

        # Get iTerm2 sessions
        if self.iterm2:
            for its in await self.iterm2.list_sessions():
                session_id = f"iterm2:{its.session_id}"
                session = UnifiedSession(
                    id=session_id,
                    name=its.name,
                    terminal_type=TerminalType.ITERM2,
                )
                sessions.append(session)
                self._sessions_cache[session_id] = session

        return sessions

    async def get_session_output(self, session_id: str, lines: int = 50) -> str:
        """Get recent output from a session."""
        session = self._sessions_cache.get(session_id)
        if not session:
            return "Session not found"

        if session.terminal_type == TerminalType.TMUX and self.tmux:
            parts = session_id.split(":")
            session_name = parts[1]
            window_idx = int(parts[2])
            pane_idx = int(parts[3])
            return self.tmux.capture_pane(session_name, window_idx, pane_idx, lines)

        elif session.terminal_type == TerminalType.ITERM2 and self.iterm2:
            iterm_session_id = session_id.replace("iterm2:", "")
            return await self.iterm2.get_screen_contents(iterm_session_id, lines)

        return "Backend not available"

    async def send_command(
        self,
        session_id: str,
        command: str,
        wait_for_completion: bool = True,
        timeout: float = 30.0
    ) -> CommandResult:
        """
        Send a command to a session and optionally wait for completion.

        Args:
            session_id: Target session
            command: Command to execute
            wait_for_completion: Whether to wait for command to finish
            timeout: Maximum wait time in seconds

        Returns:
            CommandResult with output and state
        """
        session = self._sessions_cache.get(session_id)
        if not session:
            return CommandResult(False, "Session not found", SessionState.UNKNOWN, 0)

        start_time = time.time()

        # Get output before command
        output_before = await self.get_session_output(session_id, lines=5)

        # Send command
        if session.terminal_type == TerminalType.TMUX and self.tmux:
            parts = session_id.split(":")
            session_name = parts[1]
            window_idx = int(parts[2])
            pane_idx = int(parts[3])
            self.tmux.send_keys(session_name, command, window_idx, pane_idx, enter=True)

        elif session.terminal_type == TerminalType.ITERM2 and self.iterm2:
            iterm_session_id = session_id.replace("iterm2:", "")
            await self.iterm2.send_text(iterm_session_id, command, newline=True)

        else:
            return CommandResult(False, "Backend not available", SessionState.UNKNOWN, 0)

        # Wait for completion if requested
        if wait_for_completion:
            output = await self._wait_for_completion(session_id, timeout)
        else:
            await asyncio.sleep(0.5)
            output = await self.get_session_output(session_id)

        # Detect state
        state = await self.detect_state(session_id)

        execution_time = time.time() - start_time
        return CommandResult(True, output, state, execution_time)

    async def _wait_for_completion(self, session_id: str, timeout: float) -> str:
        """Wait for a command to complete by monitoring output stability."""
        start_time = time.time()
        last_output = ""
        stable_count = 0
        required_stable = 3  # Output must be stable for 3 checks

        while (time.time() - start_time) < timeout:
            await asyncio.sleep(0.3)
            current_output = await self.get_session_output(session_id)

            if current_output == last_output:
                stable_count += 1
                if stable_count >= required_stable:
                    # Check if we're back at a prompt
                    if self._looks_like_prompt(current_output):
                        return current_output
            else:
                stable_count = 0
                last_output = current_output

        return last_output

    def _looks_like_prompt(self, output: str) -> bool:
        """Heuristic to detect if output ends at a shell prompt."""
        if not output:
            return False

        lines = output.strip().split("\n")
        if not lines:
            return False

        last_line = lines[-1].strip()

        # Common prompt patterns
        prompt_indicators = ["$", "#", ">", ">>>", "❯", "➜", "%"]
        for indicator in prompt_indicators:
            if last_line.endswith(indicator):
                return True
            if indicator in last_line and last_line.index(indicator) > len(last_line) // 2:
                return True

        return False

    async def detect_state(self, session_id: str) -> SessionState:
        """Detect whether a session is idle or running a command."""
        output = await self.get_session_output(session_id, lines=10)

        if self._looks_like_prompt(output):
            return SessionState.IDLE
        else:
            return SessionState.RUNNING


# =============================================================================
# Terminal Chatbot
# =============================================================================

# Define tools for the LLM
TERMINAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_sessions",
            "description": "List all available terminal sessions (both iTerm2 and tmux)",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_state",
            "description": "Get the current state of a terminal session (idle or running) and its recent output",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "The session ID to check"
                    }
                },
                "required": ["session_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_command",
            "description": "Send a command to a terminal session and get the result",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "The session ID to send the command to"
                    },
                    "command": {
                        "type": "string",
                        "description": "The command to execute"
                    },
                    "wait_for_completion": {
                        "type": "boolean",
                        "description": "Whether to wait for the command to complete (default: true)",
                        "default": True
                    }
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
                    "session_id": {
                        "type": "string",
                        "description": "The session ID to get output from"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to retrieve (default: 50)",
                        "default": 50
                    }
                },
                "required": ["session_id"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are TermPilot, an AI assistant that helps users manage and interact with their terminal sessions.

You have access to both iTerm2 and tmux terminal sessions. You can:
1. List all available terminal sessions
2. Check the state of any session (idle vs running a command)
3. Send commands to sessions and see the results
4. Read the output/content from any session

When the user asks you to do something in a terminal:
1. First list available sessions if you don't know what's available
2. Identify the appropriate session based on its name or let the user choose
3. Check the session state before sending commands
4. Send the command and wait for completion
5. Interpret the results and explain them clearly to the user

Session IDs follow these formats:
- tmux: "tmux:session_name:window_index:pane_index" (e.g., "tmux:main:0:0")
- iTerm2: "iterm2:session_uuid" (e.g., "iterm2:ABC123-DEF456...")

Be helpful, concise, and proactive. If a command fails or produces an error, explain what went wrong and suggest solutions.

Important: Always interpret terminal output for the user - don't just dump raw output, explain what it means."""


class TerminalChatbot:
    """LLM-powered terminal control chatbot."""

    def __init__(self, llm: OpenRouterClient, terminal_manager: UnifiedTerminalManager):
        self.llm = llm
        self.terminal = terminal_manager
        self.messages: list[LLMMessage] = [
            LLMMessage(role="system", content=SYSTEM_PROMPT)
        ]

    async def execute_tool(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return the result."""
        name = tool_call.name
        args = tool_call.arguments

        try:
            if name == "list_sessions":
                sessions = await self.terminal.list_sessions()
                result = []
                for s in sessions:
                    result.append({
                        "id": s.id,
                        "name": s.name,
                        "type": s.terminal_type.value,
                        "cwd": s.cwd
                    })
                return json.dumps({"sessions": result, "count": len(result)})

            elif name == "get_session_state":
                session_id = args["session_id"]
                state = await self.terminal.detect_state(session_id)
                output = await self.terminal.get_session_output(session_id, lines=20)
                return json.dumps({
                    "session_id": session_id,
                    "state": state.value,
                    "recent_output": output[-1000:] if len(output) > 1000 else output
                })

            elif name == "send_command":
                session_id = args["session_id"]
                command = args["command"]
                wait = args.get("wait_for_completion", True)

                result = await self.terminal.send_command(
                    session_id, command,
                    wait_for_completion=wait,
                    timeout=30.0
                )

                return json.dumps({
                    "success": result.success,
                    "output": result.output[-2000:] if len(result.output) > 2000 else result.output,
                    "state_after": result.state_after.value,
                    "execution_time": round(result.execution_time, 2)
                })

            elif name == "get_session_output":
                session_id = args["session_id"]
                lines = args.get("lines", 50)
                output = await self.terminal.get_session_output(session_id, lines)
                return json.dumps({
                    "session_id": session_id,
                    "output": output[-3000:] if len(output) > 3000 else output,
                    "lines_requested": lines
                })

            else:
                return json.dumps({"error": f"Unknown tool: {name}"})

        except Exception as e:
            return json.dumps({"error": str(e)})

    async def chat(self, user_input: str) -> str:
        """Process user input and return response."""
        # Add user message
        self.messages.append(LLMMessage(role="user", content=user_input))

        # Keep conversation going until we get a final response
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Call LLM
            response_text, tool_calls = await self.llm.chat(
                self.messages,
                tools=TERMINAL_TOOLS,
                temperature=0.7
            )

            # If no tool calls, we have our final response
            if not tool_calls:
                if response_text:
                    self.messages.append(LLMMessage(role="assistant", content=response_text))
                return response_text

            # Process tool calls
            # Add assistant message with tool calls
            # Per OpenAI spec, content can be empty string when tool_calls present
            self.messages.append(LLMMessage(
                role="assistant",
                content=response_text or "",  # Empty string is valid in OpenAI format
                tool_calls=[{
                    "id": tc.id,
                    "type": "function",  # Required by OpenAI API spec
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments)
                    }
                } for tc in tool_calls]
            ))

            # Execute each tool and add results
            for tc in tool_calls:
                console.print(f"[dim]  → Calling {tc.name}...[/dim]")
                result = await self.execute_tool(tc)
                self.messages.append(LLMMessage(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id
                ))

        return "I apologize, but I wasn't able to complete the request after multiple attempts."


# =============================================================================
# Main Entry Point
# =============================================================================

async def run_chatbot(provider: str = "openrouter"):
    """Run the terminal chatbot."""
    console.print(Panel.fit(
        "[bold green]TermPilot - Terminal Chatbot POC[/bold green]\n"
        "[dim]LLM-powered terminal control assistant[/dim]",
        title="TermPilot"
    ))

    # Initialize LLM
    api_key = os.getenv("TERMPILOT_OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]Error: TERMPILOT_OPENROUTER_API_KEY not set[/red]")
        console.print("Please set it in .env.local or .env")
        return

    llm = OpenRouterClient(api_key)
    console.print(f"[green]✓[/green] LLM initialized (OpenRouter: {llm.model})")

    # Initialize terminal manager
    terminal = UnifiedTerminalManager()
    console.print("[blue]Connecting to terminals...[/blue]")

    status = await terminal.connect()
    for backend, connected in status.items():
        if connected:
            console.print(f"[green]✓[/green] {backend} connected")
        else:
            console.print(f"[yellow]○[/yellow] {backend} not available")

    if not any(status.values()):
        console.print("[red]No terminal backends available![/red]")
        return

    # Create chatbot
    chatbot = TerminalChatbot(llm, terminal)

    # Show available sessions
    sessions = await terminal.list_sessions()
    if sessions:
        table = Table(title="Available Sessions")
        table.add_column("ID", style="cyan", no_wrap=True, max_width=40)
        table.add_column("Name", style="green")
        table.add_column("Type", style="yellow")

        for s in sessions[:10]:  # Show first 10
            table.add_row(
                s.id[:40] + "..." if len(s.id) > 40 else s.id,
                s.name,
                s.terminal_type.value
            )

        if len(sessions) > 10:
            table.add_row("...", f"({len(sessions) - 10} more)", "...")

        console.print(table)
    else:
        console.print("[yellow]No sessions found[/yellow]")

    # Chat loop
    console.print("\n[bold]Chat with TermPilot[/bold]")
    console.print("[dim]Type 'quit' to exit, 'clear' to reset conversation[/dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]")
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input.strip():
            continue

        if user_input.lower() == "quit":
            break

        if user_input.lower() == "clear":
            chatbot.messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]
            console.print("[dim]Conversation cleared[/dim]")
            continue

        # Get response
        console.print("[dim]Thinking...[/dim]")
        try:
            response = await chatbot.chat(user_input)
            console.print()
            console.print(Panel(
                Markdown(response) if response else "[dim]No response[/dim]",
                title="[bold green]TermPilot[/bold green]",
                border_style="green"
            ))
            console.print()
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    console.print("[green]Goodbye![/green]")


def main(*args):
    """Entry point for the POC runner."""
    provider = "openrouter"

    if "--provider" in args:
        idx = args.index("--provider")
        if idx + 1 < len(args):
            provider = args[idx + 1]

    if "--local" in args:
        provider = "local"

    asyncio.run(run_chatbot(provider))


if __name__ == "__main__":
    main(*sys.argv[1:])
