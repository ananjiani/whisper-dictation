# whisper-dictation

A minimal voice dictation tool using OpenAI's Whisper for Linux. Press a hotkey to start recording, speak, then press another hotkey to transcribe and type the text automatically.

## Features

- 🎤 Simple voice recording with PipeWire
- 🤖 Accurate transcription using OpenAI's Whisper (via faster-whisper)
- ⌨️ Instant text pasting using clipboard + ydotool (Wayland only)
- 🚀 Minimal, single-file implementation
- 🐧 NixOS-ready with included flake

## Requirements

- Python 3.11+
- Wayland compositor (required for wl-clipboard)
- PipeWire (for audio recording)
- wl-clipboard (for clipboard operations)
- ydotool (for paste simulation)
- faster-whisper (Python package)

## Installation

### Using Nix (recommended)

```bash
# Clone the repository
git clone https://github.com/ananjiani/whisper-dictation.git
cd whisper-dictation

# Enter development shell with all dependencies
nix develop

# The script is ready to use!
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
2. `end` stops the recording, transcribes the audio using faster-whisper (tiny model), copies text to clipboard, and pastes it using ydotool
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
