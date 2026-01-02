# Conversation Orchestrator

**Status**: ✅ Implemented (Phase 1 Complete)
**Issue**: #1 - Two-Way Meta-Communication POC
**Date**: 2026-01-01

## Overview

The Conversation Orchestrator enables automated conversations between Claude Code sessions, supporting the two-way meta-communication use case where one Claude instance can test and interact with another.

## Architecture

### Core Components

```
ConversationOrchestrator
├── ClaudeCodeDetector (dependency)
├── send_command_fn (from TerminalService)
└── get_output_fn (from TerminalService)
```

### Key Classes

#### `ConversationOrchestrator`
Main orchestrator for managing conversations between Claude Code sessions.

**Methods**:
- `wait_for_session_ready(session_id)` - Wait for a session to be ready for input
- `send_and_wait_for_response(session_id, message)` - Send message and wait for complete response
- `run_conversation(session_id, initial_message, max_turns)` - Run conversation with single session
- `relay_between_sessions(source, target, message, max_turns)` - Relay messages between two sessions

#### `ConversationResult`
Result of a conversation operation.

**Fields**:
- `turns: list[ConversationTurn]` - All conversation turns
- `success: bool` - Whether conversation completed successfully
- `error: str | None` - Error message if failed
- `total_time: float` - Total elapsed time in seconds

#### `ConversationTurn`
A single turn in the conversation.

**Fields**:
- `speaker: str` - Session ID/address of the speaker
- `message: str` - Message sent
- `response: str` - Response received
- `response_time: float` - Time to receive response in seconds

## Usage

### Get Orchestrator from Container

```python
from terminator.container import get_container

container = get_container()
orchestrator = container.get_conversation_orchestrator()
```

### Single Session Conversation

```python
result = await orchestrator.run_conversation(
    session_id="tmux:session-1",
    initial_message="What is 2+2?",
    max_turns=1,
)

if result.success:
    print(f"Response: {result.turns[0].response}")
    print(f"Took: {result.turns[0].response_time:.1f}s")
else:
    print(f"Failed: {result.error}")
```

### Two-Way Relay (Meta-Communication)

```python
result = await orchestrator.relay_between_sessions(
    source_session="tmux:tester",
    target_session="tmux:target",
    initial_message="Test the start command",
    max_turns=3,
)

if result.success:
    for turn in result.turns:
        print(f"{turn.speaker}: {turn.message[:100]}...")
        print(f"Response time: {turn.response_time:.1f}s")
else:
    print(f"Relay failed: {result.error}")
```

## Configuration

The orchestrator accepts timeout configuration:

```python
orchestrator = ConversationOrchestrator(
    detector=detector,
    send_command_fn=send_command_fn,
    get_output_fn=get_output_fn,
    ready_timeout=60.0,      # Seconds to wait for Claude to be ready
    response_timeout=300.0,  # Seconds to wait for response completion
)
```

Default timeouts:
- **Ready timeout**: 60 seconds (wait for session to become ready)
- **Response timeout**: 300 seconds (5 minutes, wait for response to complete)

## Error Handling

The orchestrator handles three types of failures:

### 1. Ready Timeout
Session doesn't become ready within `ready_timeout`.

```python
result = await orchestrator.wait_for_session_ready("tmux:session-1")
# Raises TimeoutError if session not ready
```

### 2. Response Timeout
Response doesn't complete within `response_timeout`.

```python
response, time = await orchestrator.send_and_wait_for_response(
    "tmux:session-1",
    "Long task..."
)
# Raises TimeoutError if response incomplete
```

### 3. General Exceptions
Any unexpected error during conversation.

All methods return `ConversationResult` with:
- `success=False`
- `error` containing error message
- `turns` containing completed turns (if any)

## Testing

### Unit Tests
Location: `tests/unit/test_conversation_orchestrator.py`

**Coverage**: 93% (87 statements, 6 missed)

Test categories:
- `TestWaitForSessionReady` - Session ready detection
- `TestSendAndWaitForResponse` - Message sending and response waiting
- `TestRunConversation` - Single-session conversations
- `TestRelayBetweenSessions` - Two-way relay conversations
- Dataclass tests for `ConversationResult` and `ConversationTurn`

### Container Tests
Location: `tests/unit/test_container_orchestrator.py`

Tests:
- ✅ Container creates orchestrator correctly
- ✅ Orchestrator is a singleton
- ✅ Dependencies injected correctly
- ✅ Reset clears orchestrator instance

### Run Tests

```bash
# All orchestrator tests
uv run pytest tests/unit/test_conversation_orchestrator.py -v

# Container integration
uv run pytest tests/unit/test_container_orchestrator.py -v

# With coverage
uv run pytest tests/unit/test_conversation_orchestrator.py \
    --cov=terminator.services.conversation_orchestrator \
    --cov-report=term-missing
```

## Dependencies

### Direct Dependencies
- `ClaudeCodeDetector` - Detects Claude Code states from terminal output
- `TerminalService` - Provides command sending and output retrieval

### Transitive Dependencies
- `TmuxAdapter` / `ITerm2Adapter` - Terminal backend adapters
- `asyncio` - Async execution

## Implementation Notes

### Message Truncation
For `relay_between_sessions`, long responses are truncated to prevent token overflow:
- **Response to target**: Last 2000 characters included in relay message
- **Relay message in turn history**: Truncated to 500 chars + "..." if longer

### Conversation Flow

**Single Conversation**:
1. Wait for session to be ready
2. Send message
3. Wait for response to complete
4. Return result with turn history

**Relay Between Sessions**:
1. Wait for both sessions to be ready (parallel)
2. Send initial message to target session
3. Wait for target response
4. Format response and relay to source session
5. Wait for source response
6. Repeat for `max_turns` cycles
7. Return result with all turns

### Future Enhancements

Potential improvements for future phases:
- [ ] Multi-turn conversation parsing (extract follow-up questions from responses)
- [ ] Conversation history persistence
- [ ] Stream responses instead of batch retrieval
- [ ] Parallel relay to multiple targets
- [ ] Conversation transcripts with timestamps
- [ ] Custom state detection patterns per session type

## Files

### Created
- `src/terminator/services/conversation_orchestrator.py` (274 lines)
- `tests/unit/test_conversation_orchestrator.py` (389 lines)
- `tests/unit/test_container_orchestrator.py` (43 lines)

### Modified
- `src/terminator/container.py` - Added `get_conversation_orchestrator()` factory

### Total Impact
- **Lines Added**: ~706 lines (implementation + tests)
- **Test Coverage**: 93%
- **Type Safety**: 100% (mypy strict compliant)
- **Tests**: 19 passing

## Next Steps

**Phase 2**: CLI Integration
- Add `terminator converse` command
- Interactive relay mode with TUI
- Conversation transcripts and logging

**Phase 3**: Advanced Features
- Multi-turn conversation parsing
- Conversation templates
- Performance metrics and analytics

## Related Documentation

- [Claude Code Detector](./claude-code-detector.md)
- [Project Addressing](../project_registry_integration.md)
- [Two-Way Meta-Communication POC](../research/cli-poc-two-way-metacomm-2026-01-01.md)
