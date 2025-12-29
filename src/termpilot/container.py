"""Dependency injection container.

Simple factory-based DI without using dependency-injector library.
This approach is more lightweight and easier to understand for this use case.
"""

from typing import Optional

from .adapters.iterm2 import ITerm2Adapter
from .adapters.tmux import TmuxAdapter
from .chat.chatbot import TerminalChatbot
from .config import Settings, get_settings
from .services.instance_detector import InstanceDetector
from .services.llm import LLMService
from .services.terminal import TerminalService
from .services.project_registry import ProjectRegistry


class Container:
    """Dependency injection container.

    Provides factory methods for creating service instances with proper
    dependency injection. Uses lazy initialization and caching for singletons.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize container.

        Args:
            settings: Application settings (creates new if None)
        """
        self._settings = settings or get_settings()
        self._iterm2_adapter: Optional[ITerm2Adapter] = None
        self._tmux_adapter: Optional[TmuxAdapter] = None
        self._terminal_service: Optional[TerminalService] = None
        self._llm_service: Optional[LLMService] = None
        self._chatbot: Optional[TerminalChatbot] = None
        self._project_registry: Optional[ProjectRegistry] = None
        self._instance_detector: Optional[InstanceDetector] = None

    @property
    def settings(self) -> Settings:
        """Get application settings."""
        return self._settings

    def get_iterm2_adapter(self) -> ITerm2Adapter:
        """Get or create iTerm2 adapter.

        Returns:
            ITerm2Adapter instance (singleton)
        """
        if self._iterm2_adapter is None:
            self._iterm2_adapter = ITerm2Adapter()
        return self._iterm2_adapter

    def get_tmux_adapter(self) -> TmuxAdapter:
        """Get or create tmux adapter.

        Returns:
            TmuxAdapter instance (singleton)
        """
        if self._tmux_adapter is None:
            self._tmux_adapter = TmuxAdapter()
        return self._tmux_adapter

    def get_terminal_service(self) -> TerminalService:
        """Get or create terminal service.

        Returns:
            TerminalService instance (singleton)
        """
        if self._terminal_service is None:
            self._terminal_service = TerminalService(
                iterm2_adapter=self.get_iterm2_adapter(),
                tmux_adapter=self.get_tmux_adapter(),
            )
        return self._terminal_service

    def get_llm_service(self) -> LLMService:
        """Get or create LLM service.

        Returns:
            LLMService instance (singleton)
        """
        if self._llm_service is None:
            self._llm_service = LLMService(
                api_key=self._settings.openrouter_api_key,
                model=self._settings.openrouter_model,
            )
        return self._llm_service

    def get_chatbot(self) -> TerminalChatbot:
        """Get or create terminal chatbot.

        Returns:
            TerminalChatbot instance (singleton)
        """
        if self._chatbot is None:
            self._chatbot = TerminalChatbot(
                llm_service=self.get_llm_service(),
                terminal_service=self.get_terminal_service(),
            )
        return self._chatbot

    def get_project_registry(self) -> ProjectRegistry:
        """Get or create project registry.

        Returns:
            ProjectRegistry instance (singleton)
        """
        if self._project_registry is None:
            self._project_registry = ProjectRegistry()
        return self._project_registry

    def get_instance_detector(self) -> InstanceDetector:
        """Get or create instance detector.

        Returns:
            InstanceDetector instance (singleton)
        """
        if self._instance_detector is None:
            self._instance_detector = InstanceDetector()
        return self._instance_detector

    def reset(self) -> None:
        """Reset all cached instances.

        Useful for testing or when configuration changes.
        """
        self._iterm2_adapter = None
        self._tmux_adapter = None
        self._terminal_service = None
        self._llm_service = None
        self._chatbot = None
        self._project_registry = None
        self._instance_detector = None


# Global container instance for CLI usage
_container: Optional[Container] = None


def get_container() -> Container:
    """Get or create global container instance.

    Returns:
        Container singleton
    """
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Reset global container.

    Useful for testing or configuration changes.
    """
    global _container
    if _container is not None:
        _container.reset()
    _container = None
