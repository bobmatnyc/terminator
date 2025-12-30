"""Interactive chat TUI with split-pane layout for conversational session control."""

import asyncio
from dataclasses import dataclass, field
from typing import Literal

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
    WindowAlign,
)
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.styles import Style
from rich.console import Console

from ...chat.chatbot import TerminalChatbot
from ...services.terminal import TerminalService


@dataclass
class ChatMessage:
    """Represents a single chat message in the history."""

    role: Literal["user", "assistant", "tool"]
    content: str
    tool_name: str | None = None
    metadata: dict = field(default_factory=dict)


class ChatInterface:
    """Interactive TUI for conversational terminal session control.

    Features:
    - Split-pane layout: chat history (top) + input (bottom)
    - Session focus indicator
    - Tool execution feedback
    - Command history (up/down arrows)
    - Special commands (/sessions, /focus, /clear, /quit)
    """

    def __init__(
        self, chatbot: TerminalChatbot, terminal_service: TerminalService
    ) -> None:
        """Initialize chat interface.

        Args:
            chatbot: The terminal chatbot instance
            terminal_service: Terminal service for session operations
        """
        self.chatbot = chatbot
        self.terminal = terminal_service
        self.console = Console()

        # Chat state
        self.chat_history: list[ChatMessage] = []
        self.focused_session: str | None = None
        self.focused_session_name: str | None = None

        # UI state
        self.app: Application | None = None
        self._running = False

        # Input buffer for command history
        self.input_buffer = Buffer(multiline=False, enable_history_search=True)

    def _format_chat_history(self) -> list[tuple[str, str]]:
        """Format chat history for display in scrollable pane.

        Returns:
            List of (style, text) tuples for prompt_toolkit FormattedTextControl
        """
        if not self.chat_history:
            return [("", "\nNo messages yet. Start chatting below!\n")]

        result: list[tuple[str, str]] = []
        for msg in self.chat_history:
            if msg.role == "user":
                result.append(("", "\n"))
                result.append(("bold fg:ansiblue", "You: "))
                result.append(("", msg.content))
            elif msg.role == "assistant":
                result.append(("", "\n"))
                result.append(("bold fg:ansigreen", "Terminator: "))
                result.append(("", msg.content))
            elif msg.role == "tool":
                tool_display = msg.tool_name or "tool"
                status = msg.metadata.get("status", "executed")
                result.append(("", "\n"))
                if status == "success":
                    result.append(("fg:ansigreen", f"✓ {tool_display}"))
                    # Show content for successful tool messages
                    if msg.content:
                        result.append(("", "\n"))
                        result.append(("", msg.content))
                elif status == "error":
                    result.append(("fg:ansired", f"✗ {tool_display}: {msg.content}"))
                else:
                    result.append(("fg:ansiyellow", f"⟳ {tool_display}..."))

        # Add newline at end for spacing
        result.append(("", "\n"))
        return result

    def _build_layout(self) -> Layout:
        """Build the TUI layout with split panes.

        Layout:
        ╭─────────────────── Terminator Chat ──────────────────╮
        │ Focused: @project (instance_type)                    │
        ├──────────────────────────────────────────────────────┤
        │                                                       │
        │ [Chat history - scrollable]                          │
        │                                                       │
        ├──────────────────────────────────────────────────────┤
        │ > [input field with history]                         │
        ╰──────────────────────────────────────────────────────╯
        """
        # Header: show focused session
        header_text = self._get_header_text()
        header = Window(
            content=FormattedTextControl(text=header_text),
            height=Dimension.exact(1),
            style="bg:#1e1e1e fg:#ffffff",
        )

        # Chat history pane (scrollable)
        self.history_control = FormattedTextControl(
            text=lambda: self._format_chat_history(), focusable=False
        )
        history_window = Window(
            content=self.history_control,
            wrap_lines=True,
            scroll_offsets=None,  # Allow scrolling
        )

        # Input pane with prompt
        input_prompt = Window(
            content=FormattedTextControl(text="> "),
            width=Dimension.exact(2),
            dont_extend_width=True,
        )

        input_field = Window(
            content=BufferControl(buffer=self.input_buffer),
            height=Dimension.exact(1),
        )

        input_container = VSplit([input_prompt, input_field])

        # Footer with help text
        footer = Window(
            content=FormattedTextControl(
                text="Ctrl+C: quit | Ctrl+L: clear | /sessions /focus @project"
            ),
            height=Dimension.exact(1),
            style="bg:#1e1e1e fg:#888888",
            align=WindowAlign.LEFT,
        )

        # Combine all sections
        root_container = HSplit(
            [
                header,
                Window(height=Dimension.exact(1), char="─"),  # Separator line
                history_window,
                Window(height=Dimension.exact(1), char="─"),  # Separator line
                input_container,
                footer,
            ]
        )

        return Layout(root_container)

    def _get_header_text(self) -> str:
        """Get header text showing focused session."""
        if self.focused_session_name:
            return f" Terminator Chat | Focused: {self.focused_session_name}"
        return " Terminator Chat | No session focused"

    def _refresh_display(self) -> None:
        """Refresh the display with updated chat history."""
        if self.app:
            # Trigger a full redraw (history_control uses lambda, so it auto-updates)
            self.app.invalidate()

    async def _handle_input(self, user_input: str) -> None:
        """Process user input and update chat history.

        Args:
            user_input: Raw user input from prompt
        """
        if not user_input.strip():
            return

        # Handle special commands
        if user_input.startswith("/"):
            await self._handle_command(user_input)
            return

        # Add user message to history
        self.chat_history.append(ChatMessage(role="user", content=user_input))
        self._refresh_display()

        # Show "thinking" indicator
        thinking_msg = ChatMessage(
            role="tool", content="Processing...", metadata={"status": "processing"}
        )
        self.chat_history.append(thinking_msg)
        self._refresh_display()

        try:
            # Get chatbot response (handles tool calls internally)
            response = await self.chatbot.chat(user_input)

            # Remove thinking indicator
            self.chat_history.remove(thinking_msg)

            # Add assistant response
            self.chat_history.append(ChatMessage(role="assistant", content=response))
            self._refresh_display()

        except Exception as e:
            # Remove thinking indicator
            if thinking_msg in self.chat_history:
                self.chat_history.remove(thinking_msg)

            # Show error
            error_msg = ChatMessage(
                role="tool",
                content=f"Error: {e}",
                metadata={"status": "error"},
            )
            self.chat_history.append(error_msg)
            self._refresh_display()

    async def _handle_command(self, command: str) -> None:
        """Handle special slash commands.

        Commands:
            /sessions - List all sessions
            /focus @project - Focus on specific session
            /clear - Clear chat history
            /quit or /exit - Exit TUI
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()

        if cmd in ("/quit", "/exit"):
            self._running = False
            if self.app:
                self.app.exit()

        elif cmd == "/clear":
            self.chat_history.clear()
            self.chatbot.reset_conversation()
            self._refresh_display()

        elif cmd == "/sessions":
            # List sessions inline
            try:
                sessions = await self.terminal.list_all_sessions()
                if not sessions:
                    msg = "No sessions found."
                else:
                    # Build project address map
                    project_registry = self.terminal.project_registry
                    projects = await project_registry.list_projects()
                    session_to_address: dict[str, str] = {}
                    for project_name, project_sessions in projects.items():
                        for ps in project_sessions:
                            session_to_address[ps.session_id] = ps.address

                    session_lines = ["Available sessions:"]
                    for s in sessions[:10]:
                        address = session_to_address.get(s.id, s.id[:20] + "...")
                        instance = (
                            s.instance_type.value if s.instance_type else "unknown"
                        )
                        session_lines.append(f"  • {address} ({instance})")

                    if len(sessions) > 10:
                        session_lines.append(f"  ... and {len(sessions) - 10} more")

                    msg = "\n".join(session_lines)

                self.chat_history.append(
                    ChatMessage(
                        role="tool", content=msg, metadata={"status": "success"}
                    )
                )
            except Exception as e:
                self.chat_history.append(
                    ChatMessage(
                        role="tool",
                        content=f"Error listing sessions: {e}",
                        metadata={"status": "error"},
                    )
                )
            self._refresh_display()

        elif cmd == "/focus":
            if len(parts) < 2:
                self.chat_history.append(
                    ChatMessage(
                        role="tool",
                        content="Usage: /focus @project",
                        metadata={"status": "error"},
                    )
                )
            else:
                session_ref = parts[1]
                # Store focus (chatbot will use @project addressing automatically)
                self.focused_session = session_ref
                self.focused_session_name = session_ref
                self.chat_history.append(
                    ChatMessage(
                        role="tool",
                        content=f"Focused on {session_ref}",
                        metadata={"status": "success"},
                    )
                )
            self._refresh_display()

        else:
            self.chat_history.append(
                ChatMessage(
                    role="tool",
                    content=f"Unknown command: {cmd}",
                    metadata={"status": "error"},
                )
            )
            self._refresh_display()

    def _create_keybindings(self) -> KeyBindings:
        """Create key bindings for the TUI.

        Returns:
            KeyBindings instance with custom handlers
        """
        kb = KeyBindings()

        @kb.add("c-c")  # Ctrl+C
        def _quit(event) -> None:
            """Exit the application."""
            self._running = False
            event.app.exit()

        @kb.add("c-l")  # Ctrl+L
        def _clear(event) -> None:
            """Clear chat history."""
            self.chat_history.clear()
            self.chatbot.reset_conversation()
            self._refresh_display()

        @kb.add("enter")
        def _submit(event) -> None:
            """Submit user input."""
            user_input = self.input_buffer.text

            # Clear input buffer
            self.input_buffer.reset(append_to_history=True)

            # Process input asynchronously
            if user_input.strip():
                # Schedule async handler
                asyncio.create_task(self._handle_input(user_input))

        return kb

    async def run(self, initial_focus: str | None = None) -> None:
        """Run the interactive chat TUI.

        Args:
            initial_focus: Optional session to focus on startup (e.g., "@mcp-ticketer")
        """
        self._running = True

        # Set initial focus if provided
        if initial_focus:
            self.focused_session = initial_focus
            self.focused_session_name = initial_focus
            self.chat_history.append(
                ChatMessage(
                    role="tool",
                    content=f"Starting chat focused on {initial_focus}",
                    metadata={"status": "success"},
                )
            )

        # Build layout and create application
        layout = self._build_layout()
        kb = self._create_keybindings()

        style = Style.from_dict(
            {
                "": "bg:#1e1e1e fg:#d4d4d4",  # Default
                "header": "bg:#1e1e1e fg:#ffffff bold",
                "footer": "bg:#1e1e1e fg:#888888",
            }
        )

        self.app = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=True,
            mouse_support=True,
        )

        # Run the application
        await self.app.run_async()


async def run_chat_tui(
    chatbot: TerminalChatbot,
    terminal_service: TerminalService,
    initial_focus: str | None = None,
) -> None:
    """Helper function to run the chat TUI.

    Args:
        chatbot: Terminal chatbot instance
        terminal_service: Terminal service instance
        initial_focus: Optional session to focus (e.g., "@mcp-ticketer")
    """
    interface = ChatInterface(chatbot, terminal_service)
    await interface.run(initial_focus=initial_focus)
