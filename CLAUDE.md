# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

This project uses `just` as a command runner. Run `just` to see all available commands:

- `just lint` - Run ruff linter with auto-fix
- `just format` - Format code with ruff
- `just check` - Run all checks (lint + mypy type checking)
- `just test-begin` - Test the recording start functionality
- `just test-end` - Test the recording end functionality
- `just watch` - Watch for file changes and auto-run linter
- `just clean` - Clean temporary files

For testing the actual dictation workflow:
- `./whisper_dictation.py begin` - Start audio recording
- `./whisper_dictation.py end` - Stop recording, transcribe, and output to stdout

## Code Architecture

This is a minimal single-file Python application (`whisper_dictation.py`) that implements voice dictation using:

1. **Audio Recording**: Uses PipeWire's `pw-record` to capture 16kHz mono audio to `/tmp/whisper_recording.wav`
2. **Process Management**: Tracks recording process via PID file at `/tmp/whisper_dictation.pid`
3. **Transcription**: Uses OpenAI's faster-whisper library with the "tiny" model for speed
4. **Text Output**: Outputs transcribed text to stdout for flexible piping and processing

The application has two main functions:
- `begin_recording()` - Spawns pw-record subprocess and saves PID
- `end_recording()` - Kills recording process, transcribes audio, outputs to stdout, cleans up

## Development Environment

Use `nix develop` to enter the development shell with all dependencies including:
- Python 3.13 with faster-whisper
- Development tools: ruff, mypy, just, watchexec
- Testing tools: pytest suite with coverage/async/mock/timeout/xdist/hypothesis

Pre-commit hooks are automatically installed and use the `just` commands for consistency.

## Dependencies

Runtime:
- PipeWire (pw-record command for audio recording)
- faster-whisper Python package (for AI transcription)

The application outputs transcribed text to stdout, allowing users to pipe the output to clipboard tools, files, or custom processing scripts as needed.
