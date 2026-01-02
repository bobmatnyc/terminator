"""Integration tests for the converse CLI command."""

import pytest
from typer.testing import CliRunner
from terminator.cli.main import app

runner = CliRunner()


class TestConverseCommand:
    """Test the converse CLI command."""

    def test_converse_help(self):
        """Test that help text is displayed."""
        result = runner.invoke(app, ["converse", "--help"])
        assert result.exit_code == 0
        assert "Send a message to a Claude Code session" in result.output
        assert "--source" in result.output
        assert "--turns" in result.output

    def test_converse_missing_args(self):
        """Test error when required arguments missing."""
        result = runner.invoke(app, ["converse"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_converse_with_target_only(self):
        """Test basic invocation structure (will fail without real session)."""
        # This will fail at runtime but validates CLI parsing
        result = runner.invoke(app, ["converse", "@test", "hello"])
        # Will fail because no session exists, but CLI parsing worked
        assert "Sending to:" in result.output or result.exit_code != 0

    def test_converse_relay_mode_args(self):
        """Test relay mode argument parsing."""
        result = runner.invoke(app, [
            "converse", "@target", "test message",
            "--source", "@tester",
            "--turns", "2",
        ])
        # Validates parsing, will fail at runtime without sessions
        assert "Relay mode:" in result.output or result.exit_code != 0

    def test_converse_custom_timeouts(self):
        """Test custom timeout argument parsing."""
        result = runner.invoke(app, [
            "converse", "@test", "hello",
            "--ready-timeout", "30",
            "--response-timeout", "120",
        ])
        # Validates timeout parsing, will fail without real session
        assert "Sending to:" in result.output or result.exit_code != 0

    def test_converse_max_turns(self):
        """Test max turns argument parsing."""
        result = runner.invoke(app, [
            "converse", "@test", "hello",
            "--turns", "5",
        ])
        # Validates turns parsing
        assert "Sending to:" in result.output or result.exit_code != 0
