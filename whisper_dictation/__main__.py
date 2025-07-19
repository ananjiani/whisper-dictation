"""Main entry point for whisper_dictation."""

import sys

from .cli import app


def main() -> int:
    """Main function for whisper_dictation CLI."""
    try:
        app()
        return 0
    except SystemExit as e:
        # SystemExit.code can be None, int, or str - ensure we return int
        if e.code is None:
            return 0
        if isinstance(e.code, int):
            return e.code
        # If code is a string or other type, treat it as an error
        return 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
