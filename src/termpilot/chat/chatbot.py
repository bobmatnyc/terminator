"""Terminal chatbot with LLM integration."""

import json

from ..services.llm import LLMMessage, LLMService, ToolCall
from ..services.terminal import TerminalService
from .tools import SYSTEM_PROMPT, TERMINAL_TOOLS


class TerminalChatbot:
    """LLM-powered terminal control chatbot.

    Orchestrates interactions between user, LLM, and terminal sessions.
    Supports tool calling for terminal operations.
    """

    def __init__(self, llm_service: LLMService, terminal_service: TerminalService):
        """Initialize chatbot.

        Args:
            llm_service: LLM service for chat completions
            terminal_service: Terminal service for session operations
        """
        self.llm = llm_service
        self.terminal = terminal_service
        self.messages: list[LLMMessage] = [
            LLMMessage(role="system", content=SYSTEM_PROMPT)
        ]

    async def execute_tool(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return the result.

        Args:
            tool_call: Tool call from LLM

        Returns:
            JSON-encoded result
        """
        name = tool_call.name
        args = tool_call.arguments

        try:
            if name == "list_sessions":
                sessions = await self.terminal.list_all_sessions()
                result = []
                for s in sessions:
                    result.append(
                        {
                            "id": s.id,
                            "name": s.name,
                            "type": s.terminal_type.value,
                            "cwd": s.cwd,
                        }
                    )
                return json.dumps({"sessions": result, "count": len(result)})

            elif name == "get_session_state":
                session_id = args["session_id"]
                state = await self.terminal.detect_state(session_id)
                output = await self.terminal.get_session_output(session_id, lines=20)
                return json.dumps(
                    {
                        "session_id": session_id,
                        "state": state.value,
                        "recent_output": output[-1000:] if len(output) > 1000 else output,
                    }
                )

            elif name == "get_session_status":
                session_id = args["session_id"]
                status = await self.terminal.get_session_status(session_id)
                return json.dumps(
                    {
                        "session_id": session_id,
                        "is_working": status["is_working"],
                        "status": status["status"],
                        "screen_summary": status["screen_summary"],
                        "last_lines": status["last_lines"],
                        "indicators": status["indicators"],
                        "session_name": status.get("session_name", ""),
                        "session_type": status.get("session_type", ""),
                        "cwd": status.get("cwd", ""),
                    }
                )

            elif name == "send_command":
                session_id = args["session_id"]
                command = args["command"]
                wait = args.get("wait_for_completion", True)

                result = await self.terminal.send_command(
                    session_id, command, wait_for_completion=wait, timeout=30.0
                )

                return json.dumps(
                    {
                        "success": result.success,
                        "output": result.output[-2000:]
                        if len(result.output) > 2000
                        else result.output,
                        "state_after": result.state_after.value,
                        "execution_time": round(result.execution_time, 2),
                    }
                )

            elif name == "get_session_output":
                session_id = args["session_id"]
                lines = args.get("lines", 50)
                output = await self.terminal.get_session_output(session_id, lines)
                return json.dumps(
                    {
                        "session_id": session_id,
                        "output": output[-3000:] if len(output) > 3000 else output,
                        "lines_requested": lines,
                    }
                )

            else:
                return json.dumps({"error": f"Unknown tool: {name}"})

        except Exception as e:
            return json.dumps({"error": str(e)})

    async def chat(self, user_input: str) -> str:
        """Process user input and return response.

        Args:
            user_input: User's message

        Returns:
            Assistant's response

        Design:
            Implements an agentic loop where the LLM can make multiple tool calls
            until it produces a final text response. Supports tool calling with
            proper OpenAI format for assistant messages and tool results.
        """
        # Add user message
        self.messages.append(LLMMessage(role="user", content=user_input))

        # Keep conversation going until we get a final response
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Call LLM
            response_text, tool_calls = await self.llm.chat(
                self.messages, tools=TERMINAL_TOOLS, temperature=0.7
            )

            # If no tool calls, we have our final response
            if not tool_calls:
                if response_text:
                    self.messages.append(
                        LLMMessage(role="assistant", content=response_text)
                    )
                return response_text

            # Process tool calls
            # Add assistant message with tool calls (OpenAI format)
            self.messages.append(
                LLMMessage(
                    role="assistant",
                    content=response_text or "",  # Empty string valid in OpenAI format
                    tool_calls=[
                        {
                            "id": tc.id,
                            "type": "function",  # Required by OpenAI API
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in tool_calls
                    ],
                )
            )

            # Execute each tool and add results
            for tc in tool_calls:
                result = await self.execute_tool(tc)
                self.messages.append(
                    LLMMessage(role="tool", content=result, tool_call_id=tc.id)
                )

        return "I apologize, but I wasn't able to complete the request after multiple attempts."

    def reset_conversation(self) -> None:
        """Reset conversation history, keeping only system prompt."""
        self.messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]
