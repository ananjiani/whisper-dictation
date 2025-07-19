"""Example tests for whisper_dictation."""

import pytest

from whisper_dictation.__main__ import main


@pytest.mark.unit
def test_main_returns_zero():
    """Test that main function returns 0."""
    assert main() == 0


@pytest.mark.unit
def test_version():
    """Test that version is accessible."""
    from whisper_dictation import __version__

    assert __version__ == "0.1.0"
