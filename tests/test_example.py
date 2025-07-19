"""Example tests for whisper_dictation."""

from unittest.mock import patch

import pytest

from whisper_dictation.__main__ import main


def test_main_returns_zero():
    """Test that main function returns 0."""
    # Mock the app function where it's imported in __main__.py
    with patch("whisper_dictation.__main__.app") as mock_app:
        # Configure the mock to not raise SystemExit
        mock_app.return_value = None
        assert main() == 0


@pytest.mark.unit
def test_version():
    """Test that version is accessible."""
    from whisper_dictation import __version__

    assert __version__ == "0.1.0"
