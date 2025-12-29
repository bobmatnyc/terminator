# Terminator

Remote terminal control system with AI assistance.

## Overview

Terminator provides remote terminal control capabilities through:
- **Terminal Adapters**: Support for tmux and iTerm2
- **REST API**: FastAPI-based control interface
- **LLM Integration**: Local and cloud LLM support for intelligent assistance
- **Security**: Risk classification and command approval

## Quick Start

### Prerequisites

- Python 3.11+
- tmux (for tmux adapter)
- iTerm2 (for iTerm2 adapter, macOS only)

### Installation

```bash
# Clone and enter project
cd terminator

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

### Verify Installation

```bash
# Run the hello world verification script
python -m scripts.runner poc.hello_world
```

## Project Structure

```
terminator/
├── src/terminator/  # Main application
│   ├── adapters/    # Terminal adapters (tmux, iTerm2)
│   ├── core/        # Core business logic
│   ├── api/         # REST API layer
│   └── llm/         # LLM integration
├── scripts/         # POC and utility scripts
├── tests/           # Test suite
└── docs/            # Documentation
```

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=server

# Type checking
mypy src

# Linting
ruff check src
```

## License

MIT
