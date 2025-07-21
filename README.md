# whisper-dictation

A minimal voice dictation tool using OpenAI's Whisper for Linux. Record audio, transcribe it using AI, and output the text to stdout for flexible piping and processing.

## Features

- 🎤 Simple voice recording with PipeWire
- 🤖 Accurate transcription using OpenAI's Whisper (via faster-whisper)
- 📤 Outputs transcription to stdout for flexible piping
- 🚀 Minimal, single-file implementation
- 🐧 NixOS-ready with included flake

## Requirements

- Python 3.11+
- PipeWire (for audio recording)
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

### Basic transcription
```bash
# Start recording
./whisper_dictation.py begin

# Stop recording and output transcription to stdout
./whisper_dictation.py end
```

### Piping examples
```bash
# Copy to clipboard (Wayland)
./whisper_dictation.py end | wl-copy

# Copy to clipboard (X11)
./whisper_dictation.py end | xclip -selection clipboard

# Save to file
./whisper_dictation.py end > transcription.txt

# Process with custom script
./whisper_dictation.py end | your-custom-processor
```

## How it works

1. `begin` starts a `pw-record` process to record audio to a temporary WAV file
2. `end` stops the recording, transcribes the audio using faster-whisper (tiny model), and outputs the text to stdout
3. Temporary files are cleaned up automatically

## Configuration

Currently uses sensible defaults:
- Model: `tiny` (fast, ~39MB)
- Audio: 16kHz mono (optimal for speech)
- No configuration files needed

## Troubleshooting

### No audio recording
Make sure PipeWire is running:
```bash
systemctl --user status pipewire
```

### Transcription not working
Check if faster-whisper is properly installed:
```bash
python -c "from faster_whisper import WhisperModel; print('OK')"
```

## License

MIT
