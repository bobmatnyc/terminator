"""LLM routing engine for terminal assistance."""
from typing import Optional
from dataclasses import dataclass
from enum import Enum

class LLMProvider(Enum):
    LOCAL = "local"
    OPENROUTER = "openrouter"

@dataclass
class LLMResponse:
    content: str
    provider: LLMProvider
    model: str
    tokens_used: int

class LLMEngine:
    """Routes LLM requests to appropriate provider."""

    async def generate(
        self,
        prompt: str,
        prefer_local: bool = True
    ) -> LLMResponse:
        """Generate a response from an LLM."""
        raise NotImplementedError("LLMEngine.generate not yet implemented")
