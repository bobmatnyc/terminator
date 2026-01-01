"""Unit tests for tmux version detection and compatibility checking."""

import pytest

from terminator.adapters.tmux import TmuxAdapter


class TestTmuxVersionParsing:
    """Test suite for tmux version parsing logic."""

    @pytest.fixture
    def adapter(self) -> TmuxAdapter:
        """Create tmux adapter instance."""
        return TmuxAdapter()

    # Test version parsing
    def test_parse_version_with_letter_suffix(self, adapter: TmuxAdapter):
        """Parse tmux version with letter suffix (e.g., 3.6a)."""
        version = adapter._parse_version("tmux 3.6a")
        assert version == (3, 6, "a")

    def test_parse_version_without_suffix(self, adapter: TmuxAdapter):
        """Parse tmux version without letter suffix (e.g., 3.5)."""
        version = adapter._parse_version("tmux 3.5")
        assert version == (3, 5, "")

    def test_parse_version_different_major(self, adapter: TmuxAdapter):
        """Parse tmux version with different major version (e.g., 4.0)."""
        version = adapter._parse_version("tmux 4.0")
        assert version == (4, 0, "")

    def test_parse_version_with_whitespace(self, adapter: TmuxAdapter):
        """Parse tmux version with extra whitespace."""
        version = adapter._parse_version("  tmux 3.6a  \n")
        assert version == (3, 6, "a")

    def test_parse_version_invalid_format(self, adapter: TmuxAdapter):
        """Handle invalid version format gracefully."""
        version = adapter._parse_version("invalid")
        assert version == (0, 0, "")

    def test_parse_version_empty_string(self, adapter: TmuxAdapter):
        """Handle empty string gracefully."""
        version = adapter._parse_version("")
        assert version == (0, 0, "")

    # Test version compatibility
    def test_versions_compatible_exact_match(self, adapter: TmuxAdapter):
        """Compatible when versions match exactly."""
        client = (3, 6, "a")
        server = (3, 6, "a")
        assert adapter._versions_compatible(client, server) is True

    def test_versions_compatible_major_minor_match(self, adapter: TmuxAdapter):
        """Compatible when major.minor match but suffix differs."""
        client = (3, 6, "a")
        server = (3, 6, "b")
        assert adapter._versions_compatible(client, server) is True

    def test_versions_compatible_suffix_vs_no_suffix(self, adapter: TmuxAdapter):
        """Compatible when major.minor match, one has suffix and one doesn't."""
        client = (3, 6, "")
        server = (3, 6, "a")
        assert adapter._versions_compatible(client, server) is True

    def test_versions_incompatible_minor_mismatch(self, adapter: TmuxAdapter):
        """Incompatible when minor version differs."""
        client = (3, 6, "a")
        server = (3, 5, "a")
        assert adapter._versions_compatible(client, server) is False

    def test_versions_incompatible_major_mismatch(self, adapter: TmuxAdapter):
        """Incompatible when major version differs."""
        client = (4, 0, "")
        server = (3, 6, "a")
        assert adapter._versions_compatible(client, server) is False

    def test_versions_incompatible_both_differ(self, adapter: TmuxAdapter):
        """Incompatible when both major and minor differ."""
        client = (4, 1, "")
        server = (3, 5, "")
        assert adapter._versions_compatible(client, server) is False

    # Test version formatting
    def test_format_version_with_suffix(self, adapter: TmuxAdapter):
        """Format version with letter suffix."""
        formatted = adapter._format_version((3, 6, "a"))
        assert formatted == "3.6a"

    def test_format_version_without_suffix(self, adapter: TmuxAdapter):
        """Format version without letter suffix."""
        formatted = adapter._format_version((3, 5, ""))
        assert formatted == "3.5"

    def test_format_version_zero(self, adapter: TmuxAdapter):
        """Format zero version (used for invalid/unknown)."""
        formatted = adapter._format_version((0, 0, ""))
        assert formatted == "0.0"


class TestTmuxVersionErrorMessages:
    """Test error message patterns for version-related issues."""

    def test_not_a_terminal_error_pattern(self):
        """Verify error message detection for 'not a terminal' error."""
        error_messages = [
            "open terminal failed: not a terminal",
            "error: NOT A TERMINAL",
            "Error: Not a terminal device",
        ]
        for msg in error_messages:
            assert "not a terminal" in msg.lower()

    def test_version_mismatch_warning_format(self):
        """Verify version mismatch warning contains required info."""
        warning = (
            "Tmux version mismatch detected!\n"
            "  Client: 3.6a\n"
            "  Server: 3.5\n"
            "This may cause 'not a terminal' errors.\n"
            "Fix: Run 'tmux kill-server' to restart with matching version."
        )
        assert "version mismatch" in warning.lower()
        assert "client:" in warning.lower()
        assert "server:" in warning.lower()
        assert "tmux kill-server" in warning.lower()
