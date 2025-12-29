"""LLM service for interacting with OpenRouter API."""

import json
from dataclasses import dataclass, field
from typing import Literal, Optional

import httpx


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


class LLMService:
    """Service for OpenRouter API with tool support.

    Handles chat completions with function calling capabilities.
    """

    def __init__(self, api_key: str, model: str = "anthropic/claude-sonnet-4"):
        """Initialize LLM service.

        Args:
            api_key: OpenRouter API key
            model: Model identifier (default: Claude Sonnet 4)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> tuple[str, list[ToolCall]]:
        """Send chat completion request.

        Args:
            messages: Conversation messages
            tools: Available tools for function calling
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, tool_calls)

        Raises:
            Exception: If API request fails
        """
        async with httpx.AsyncClient() as client:
            # Format messages according to OpenRouter/OpenAI API
            formatted_messages = []
            for m in messages:
                if m.role == "tool":
                    # Tool result message (OpenAI format)
                    formatted_messages.append(
                        {
                            "role": "tool",
                            "content": m.content,
                            "tool_call_id": m.tool_call_id,
                        }
                    )
                elif m.role == "assistant" and m.tool_calls:
                    # Assistant message with tool calls (OpenAI format)
                    formatted_messages.append(
                        {
                            "role": "assistant",
                            "content": m.content or "",  # Empty string valid
                            "tool_calls": m.tool_calls,
                        }
                    )
                else:
                    # Regular user/system/assistant message
                    formatted_messages.append({"role": m.role, "content": m.content})

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
                    "X-Title": "TermPilot",
                },
                json=payload,
                timeout=60.0,
            )

            if response.status_code != 200:
                raise Exception(
                    f"OpenRouter error: {response.status_code} - {response.text}"
                )

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
                    tool_calls.append(
                        ToolCall(
                            id=tc["id"], name=tc["function"]["name"], arguments=args
                        )
                    )

            return message.get("content", ""), tool_calls
