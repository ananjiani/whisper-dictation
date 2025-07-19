# List available commands
default:
    @just --list

# Run linter
lint:
    ruff check whisper_dictation.py

# Format code
format:
    ruff format whisper_dictation.py

# Run all checks
check: lint
    mypy whisper_dictation.py

# Test the begin command
test-begin:
    ./whisper_dictation.py begin

# Test the end command
test-end:
    ./whisper_dictation.py end

# Watch for changes and run linter
watch:
    watchexec -e py just lint

# Clean temporary files
clean:
    rm -f /tmp/whisper_dictation.pid /tmp/whisper_recording.wav
