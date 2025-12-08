"""Terminal adapter implementations."""

from .protocols import ITerminalAdapter, UnifiedSession, CommandResult, SessionState
from .iterm2 import ITerm2Adapter
from .tmux import TmuxAdapter

__all__ = [
    "ITerminalAdapter",
    "UnifiedSession",
    "CommandResult",
    "SessionState",
    "ITerm2Adapter",
    "TmuxAdapter",
]
