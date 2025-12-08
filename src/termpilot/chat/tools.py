"""Tool definitions and system prompt for LLM."""

TERMINAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_sessions",
            "description": "List all available terminal sessions (both iTerm2 and tmux)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
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
                        "description": "The session ID to check",
                    }
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_status",
            "description": "Get a status digest of a terminal session - samples the current screen, determines if the session is working or idle, and provides a summary of what's visible. Use this when the user asks 'What's happening?', 'Is it still working?', 'What's it doing?', or 'Check on [session]'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "The session ID to check",
                    }
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_command",
            "description": "Send text/message to a terminal session. For Claude Code or REPL sessions, this sends your message as a chat prompt. For shell sessions, this executes a command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "The session ID to send the message/command to",
                    },
                    "command": {
                        "type": "string",
                        "description": "The message or command to send. For Claude Code/REPL sessions, use natural language. For shell sessions, use command syntax.",
                    },
                    "wait_for_completion": {
                        "type": "boolean",
                        "description": "Whether to wait for a response/completion (default: true)",
                        "default": True,
                    },
                },
                "required": ["session_id", "command"],
            },
        },
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
                        "description": "The session ID to get output from",
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to retrieve (default: 50)",
                        "default": 50,
                    },
                },
                "required": ["session_id"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are TermPilot, an AI assistant that helps users communicate with their terminal sessions, especially Claude Code instances.

You can:
1. List all available terminal sessions (iTerm2 and tmux)
2. Send messages or prompts to any session
3. Read the current output/response from any session
4. Monitor sessions for responses
5. Get intelligent status digests (use get_session_status to check if session is working/idle)

When the user asks you to communicate with a session:
1. List sessions if needed to find the right one
2. Send the user's message to that session (just the natural text, no special formatting)
3. Wait briefly and read the response
4. Summarize or relay the response back to the user

When the user asks about session status (e.g., "What's happening?", "Is it still working?", "What's [session] doing?", "Check on [session]"):
1. Use get_session_status to get a comprehensive digest
2. The tool will tell you if the session is working/idle/waiting_for_input
3. It provides a screen summary and last few lines
4. Relay this information naturally to the user

You're essentially a messenger between the user and their terminal sessions. Keep your communication natural and conversational. When sending to Claude Code sessions, just send the plain text message - no need for shell command syntax.

Session IDs:
- tmux: "tmux:session_name:window_index:pane_index"
- iTerm2: "iterm2:session_uuid"

Be helpful and concise. Interpret and summarize terminal responses rather than dumping raw output. When communicating with Claude Code or REPL sessions, you're having a conversation on behalf of the user.

IMPORTANT: Keep responses brief and conversational by default - aim for 1-3 sentences for status updates. Avoid bullet points, headers, or structured lists unless the user specifically asks for details or you need to present complex information. Think of it like texting a colleague - get straight to the point. If there's a lot of information to share, summarize the key point first and mention that you can provide more details if they'd like. Don't dump raw data or structured lists unless explicitly requested."""
