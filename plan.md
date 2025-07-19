# Whisper-Dictation Implementation Plan

## Project Overview
A voice dictation tool using faster-whisper for speech recognition, designed as a modern alternative to nerd-dictation with support for both X11 and Wayland.

## Project Structure
```
whisper-dictation/
├── flake.nix              # Nix flake for dev environment and packaging
├── flake.lock
├── pyproject.toml         # uv project configuration
├── uv.lock               # uv lock file
├── README.md
├── src/whisper_dictation/
│   ├── __init__.py
│   ├── __main__.py        # CLI entry point (Typer)
│   ├── daemon.py          # Background daemon service
│   ├── ipc.py            # IPC communication layer
│   ├── audio.py           # Audio recording (parec/sox/pw-cat)
│   ├── transcriber.py     # faster-whisper integration
│   ├── output.py          # Text output (xdotool/ydotool/stdout)
│   ├── config.py          # User configuration
│   ├── cli.py             # Typer CLI definition
│   └── models.py          # Type definitions and enums
└── tests/
```

## Phase 1: Core Features

### 1. Daemon Architecture
- Background service that keeps models loaded in memory
- IPC communication (Unix socket or D-Bus)
- Manages transcription state and sessions
- Handles suspend/resume without reloading models

### 2. Audio Recording
- Support parec (PulseAudio), sox, and pw-cat (PipeWire)
- Configurable audio device selection
- Real-time streaming to transcriber
- Handled by daemon for continuous operation

### 3. Transcription Engine
- Use faster-whisper for 4x speed improvement
- Support multiple model sizes (tiny to large-v3)
- Implement Voice Activity Detection (VAD) for efficiency
- Progressive transcription mode for long sessions
- Models stay loaded in daemon memory

### 4. Output Methods
- **Universal**: ydotool for simulating keystrokes (works on both X11 and Wayland)
- stdout for piping to other programs
- Optional clipboard integration

### 5. CLI Interface (Typer-based)
- Commands: start, stop, pause, resume, status
- Configuration management
- Model selection and download
- Device selection
- Clean type-safe interface with good help

### 6. Configuration
- Python-based config file for text manipulation
- Command-line arguments for runtime options
- Support for custom text processing functions
- ydotool works universally (no need to detect display server)

## Phase 2: Enhanced Features

### 1. Performance Optimizations
- Implement suspend/resume to keep model in memory
- Add batched processing for better throughput
- GPU acceleration support (CUDA/ROCm)

### 2. Advanced Features
- Number-to-digit conversion
- Basic punctuation from timing
- Custom wake word detection
- Multi-language support

### 3. Integration
- D-Bus service for system integration
- Optional GUI tray icon
- Hotkey support for start/stop
- Handle ydotool daemon management

## Nix Packaging Strategy

### 1. Use uv2nix for Python dependency management
- Create `pyproject.toml` with project metadata
- Generate `uv.lock` with `uv lock`
- Use uv2nix flake template

### 2. Development Shell
- Include uv, Python, and all dependencies
- Set up proper environment variables for uv

### 3. Package as NixOS module
- Include systemd service for ydotool daemon (Wayland)
- Support both standalone and home-manager installation
- Handle permissions for ydotool properly

## Technical Stack
- **Language**: Python 3.11+
- **Package Manager**: uv (fast Python package manager)
- **Transcription**: faster-whisper
- **Audio**: pyaudio/sounddevice
- **VAD**: Silero VAD or py-webrtcvad
- **Input Simulation**: ydotool (universal - works on X11, Wayland, and even console)
- **CLI**: Typer (type-safe CLI framework)
- **Testing**: pytest
- **Packaging**: uv + uv2nix + Nix flakes

## ydotool Considerations
- Set up ydotool systemd service properly (required for daemon mode)
- Handle permission requirements (uinput group membership)
- Provide fallback to stdout if ydotool unavailable
- Document ydotool limitations (ASCII only, no window control)
- Universal compatibility (X11, Wayland, console) is a major advantage

## Development Workflow
1. Initialize project with uv
2. Set up flake.nix with uv2nix
3. Implement daemon architecture with IPC
4. Implement core audio recording
5. Add faster-whisper transcription
6. Implement ydotool output method
7. Create Typer CLI interface
8. Add configuration system
9. Write tests
10. Package for NixOS with systemd services
11. Document installation and usage
