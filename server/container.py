from dependency_injector import containers, providers
from server.config import Settings
from server.adapters.tmux import TmuxAdapter
from server.adapters.iterm2 import ITerm2Adapter
from server.core.session import SessionManager

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    settings = providers.Singleton(Settings)

    # Adapters
    tmux_adapter = providers.Factory(TmuxAdapter)
    iterm2_adapter = providers.Factory(ITerm2Adapter)

    # Core services
    session_manager = providers.Singleton(
        SessionManager,
        tmux_adapter=tmux_adapter,
        iterm2_adapter=iterm2_adapter,
    )
