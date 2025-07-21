#!/usr/bin/env python3
"""Minimal whisper dictation script using pw-record, faster-whisper, and ydotool."""

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

# File paths
RECORDING_FILE = "/tmp/whisper_recording.wav"
PID_FILE = "/tmp/whisper_dictation.pid"


def begin_recording():
    """Start recording audio using pw-record."""
    # Check if already recording
    if Path(PID_FILE).exists():
        try:
            with Path(PID_FILE).open() as f:
                pid = int(f.read().strip())
            # Check if process is running
            os.kill(pid, 0)
            print("Recording is already in progress.")
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            # Process not running, clean up PID file
            Path(PID_FILE).unlink(missing_ok=True)

    # Start recording
    cmd = ["pw-record", "--format=s16", "--rate=16000", "--channels=1", RECORDING_FILE]
    process = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    # Save PID
    with Path(PID_FILE).open("w") as f:
        f.write(str(process.pid))

    print(f"Recording started (PID: {process.pid})")
    print("Run 'whisper_dictation.py end' to stop and transcribe.")


def end_recording():
    """Stop recording, transcribe, and type the result."""
    # Check if recording
    if not Path(PID_FILE).exists():
        print("No recording in progress.")
        sys.exit(1)

    try:
        # Read PID and stop recording
        with Path(PID_FILE).open() as f:
            pid = int(f.read().strip())

        try:
            os.kill(pid, signal.SIGTERM)
            print("Stopping recording...", file=sys.stderr)
        except ProcessLookupError:
            print("Recording process not found.", file=sys.stderr)

        # Clean up PID file
        Path(PID_FILE).unlink(missing_ok=True)

        # Check if recording file exists
        if not Path(RECORDING_FILE).exists():
            print("Recording file not found.")
            sys.exit(1)

        # Transcribe audio
        print("Transcribing audio...", file=sys.stderr)
        try:
            from faster_whisper import WhisperModel

            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, info = model.transcribe(RECORDING_FILE, beam_size=5)

            # Collect transcription
            transcription = " ".join(segment.text.strip() for segment in segments)

            if not transcription:
                print("No speech detected.", file=sys.stderr)
            else:
                # Output transcription to stdout for piping
                print(transcription)

        except Exception as e:
            print(f"Error during transcription: {e}")
            sys.exit(1)

        finally:
            # Clean up recording file
            Path(RECORDING_FILE).unlink(missing_ok=True)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Simple whisper dictation tool", prog="whisper_dictation.py"
    )
    parser.add_argument("command", choices=["begin", "end"], help="Command to execute")

    args = parser.parse_args()

    if args.command == "begin":
        begin_recording()
    elif args.command == "end":
        end_recording()


if __name__ == "__main__":
    main()
