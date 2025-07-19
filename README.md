# whisper-dictation

Minimal voice dictation tool using faster-whisper - a reimplementation of nerd-dictation using Whisper instead of VOSK.

## Features

- Simple voice dictation using faster-whisper
- PipeWire audio recording (pw-record)
- Universal text input via ydotool (works on X11/Wayland)
- Minimal dependencies and single-file implementation

## Requirements

- Python 3.11+
- PipeWire (for `pw-record`)
- ydotool (for typing text)
- faster-whisper (installed automatically)

## Installation

### Using Nix (recommended)

```bash
# Enter development shell with all dependencies
nix develop

# Install Python dependencies
uv sync
```

### Manual installation

```bash
# Install system dependencies
# On Arch: sudo pacman -S pipewire ydotool
# On Ubuntu: sudo apt install pipewire ydotool

# Install Python dependency
pip install faster-whisper
```

## Usage

```bash
# Start recording
./whisper_dictation.py begin

# Stop recording and type the transcribed text
./whisper_dictation.py end
```

## How it works

1. `begin` starts a `pw-record` process to record audio to a temporary WAV file
2. `end` stops the recording, transcribes the audio using faster-whisper (tiny model), and types the result using ydotool
3. Temporary files are cleaned up automatically

## Configuration

Currently uses sensible defaults:
- Model: `tiny` (fast, ~39MB)
- Audio: 16kHz mono (optimal for speech)
- No configuration files needed

## Troubleshooting

### ydotool not working

Make sure ydotool daemon is running:
```bash
sudo systemctl start ydotoold
# or
ydotoold &
```

You may need to be in the `input` group:
```bash
sudo usermod -a -G input $USER
```

## License

MIT
