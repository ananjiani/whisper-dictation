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
            print("Stopping recording...")
        except ProcessLookupError:
            print("Recording process not found.")

        # Clean up PID file
        Path(PID_FILE).unlink(missing_ok=True)

        # Check if recording file exists
        if not Path(RECORDING_FILE).exists():
            print("Recording file not found.")
            sys.exit(1)

        # Transcribe audio
        print("Transcribing audio...")
        try:
            from faster_whisper import WhisperModel

            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, info = model.transcribe(RECORDING_FILE, beam_size=5)

            # Collect transcription
            transcription = " ".join(segment.text.strip() for segment in segments)

            if not transcription:
                print("No speech detected.")
            else:
                print(f"Transcription: {transcription}")

                # Paste the transcription using clipboard + ydotool
                print("Pasting transcription...")
                try:
                    # Copy to clipboard
                    subprocess.run(
                        ["wl-copy"], input=transcription, text=True, check=True
                    )
                    # Simulate Ctrl+V paste
                    subprocess.run(
                        ["ydotool", "key", "ctrl+v"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    print("Done!")
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr if e.stderr else str(e)
                    if "wl-copy" in str(e.cmd):
                        print("⚠️  Could not copy to clipboard using wl-copy")
                        print("Possible solutions:")
                        print("1. Check if you're running in a Wayland session:")
                        print("   echo $XDG_SESSION_TYPE")
                        print("2. If on X11, try using xclip instead:")
                        print("   echo '<transcription>' | xclip -selection clipboard")
                        print("📋 Your transcription (ready to copy manually):")
                        print(f"{transcription}")
                    elif (
                        "ydotoold" in error_msg
                        or "socket" in error_msg
                        or "Connection refused" in error_msg
                    ):
                        print("⚠️  Could not connect to ydotool daemon for pasting")

                        # Check if user is in ydotool group
                        import grp

                        try:
                            grp.getgrnam("ydotool")
                            user_groups = [
                                g.gr_name
                                for g in grp.getgrall()
                                if os.getlogin() in g.gr_mem
                            ]
                            if "ydotool" not in user_groups:
                                print("❌ You are NOT in the 'ydotool' group!")
                                print("   Run: sudo usermod -a -G ydotool $USER")
                                print("   Then logout and login again.")
                        except KeyError:
                            pass

                        print("Possible solutions:")
                        print("1. Check if ydotoold is running:")
                        print("   systemctl status ydotoold")
                        print("2. You might need to be in the 'input' group:")
                        print("   sudo usermod -a -G input $USER")
                        print("   # Then logout and login again")
                        print("3. Try running ydotoold in user mode:")
                        print("   systemctl --user start ydotoold")
                        print(
                            "4. Text is already in clipboard, manually press Ctrl+V to paste"
                        )
                        print("📋 Your transcription is in clipboard:")
                        print(f"{transcription}")
                    else:
                        print(f"Error during paste operation: {error_msg}")
                        print(f"📋 Transcription: {transcription}")

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
