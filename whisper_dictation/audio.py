"""Audio recording functionality for whisper_dictation."""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AudioDevice:
    """Represents an audio input device."""

    id: str
    name: str
    description: str
    is_default: bool = False

    def __str__(self) -> str:
        """String representation of the device."""
        return f"{self.name} ({self.id})"

    def __eq__(self, other: object) -> bool:
        """Check equality based on device id."""
        if not isinstance(other, AudioDevice):
            return False
        return self.id == other.id


class AudioBackend(ABC):
    """Abstract base class for audio recording backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the backend."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this backend is available on the system."""
        pass

    @abstractmethod
    async def list_devices(self) -> list[AudioDevice]:
        """List available audio input devices."""
        pass

    @abstractmethod
    async def get_default_device(self) -> AudioDevice:
        """Get the default audio input device."""
        pass

    @abstractmethod
    async def start_recording(
        self,
        device: AudioDevice,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> "AudioStream":
        """Start recording from the specified device."""
        pass


class AudioStream:
    """Represents an audio recording stream."""

    def __init__(
        self, process: asyncio.subprocess.Process, chunk_size: int = 1024
    ) -> None:
        """Initialize the audio stream."""
        self.process = process
        self.chunk_size = chunk_size

    async def read(self, size: int | None = None) -> bytes:
        """Read audio data from the stream."""
        if size is None:
            size = self.chunk_size

        if self.process.stdout is None:
            raise RuntimeError("Process stdout is not available")

        return await self.process.stdout.read(size)

    async def close(self) -> None:
        """Close the audio stream."""
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception:
                # Process might already be terminated
                pass

    async def __aenter__(self) -> "AudioStream":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Async iterator support."""
        return self

    async def __anext__(self) -> bytes:
        """Get next chunk of audio data."""
        data = await self.read()
        if not data:
            raise StopAsyncIteration
        return data


class ParecBackend(AudioBackend):
    """PulseAudio recording backend using parec."""

    @property
    def name(self) -> str:
        """Name of the backend."""
        return "parec"

    async def is_available(self) -> bool:
        """Check if parec is available."""
        try:
            process = await asyncio.create_subprocess_exec(
                "which",
                "parec",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.wait()
            return process.returncode == 0
        except (FileNotFoundError, OSError):
            return False

    async def list_devices(self) -> list[AudioDevice]:
        """List PulseAudio input devices using pactl."""
        try:
            process = await asyncio.create_subprocess_exec(
                "pactl",
                "list",
                "short",
                "sources",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if process.stdout is None:
                return []
            stdout = await process.stdout.read()
            await process.wait()

            if process.returncode != 0:
                return []

            devices = []
            output = stdout.decode().strip()

            for line in output.split("\n"):
                if not line.strip():
                    continue

                parts = line.split("\t")
                if len(parts) >= 6:
                    device_id = parts[1]
                    device_name = parts[5] if len(parts) > 5 else device_id

                    device = AudioDevice(
                        id=device_id,
                        name=device_name,
                        description=device_name,
                        is_default=False,
                    )
                    devices.append(device)

            return devices

        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Failed to list PulseAudio devices: {e}")
            return []

    async def get_default_device(self) -> AudioDevice:
        """Get the default PulseAudio input device."""
        try:
            process = await asyncio.create_subprocess_exec(
                "pactl",
                "get-default-source",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if process.stdout is None:
                raise RuntimeError("Failed to get default device: no stdout")
            stdout = await process.stdout.read()
            await process.wait()

            if process.returncode == 0:
                device_id = stdout.decode().strip()
                return AudioDevice(
                    id=device_id,
                    name="Default Device",
                    description="Default PulseAudio Input Device",
                    is_default=True,
                )
            else:
                # Fallback to a generic default
                return AudioDevice(
                    id="default",
                    name="Default Device",
                    description="Default Audio Input Device",
                    is_default=True,
                )

        except (FileNotFoundError, OSError):
            return AudioDevice(
                id="default",
                name="Default Device",
                description="Default Audio Input Device",
                is_default=True,
            )

    async def start_recording(
        self,
        device: AudioDevice,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> AudioStream:
        """Start recording using parec."""
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
        if channels <= 0:
            raise ValueError("Channels must be positive")

        try:
            process = await asyncio.create_subprocess_exec(
                "parec",
                f"--device={device.id}",
                "--format=s16le",
                f"--rate={sample_rate}",
                f"--channels={channels}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Check if process started successfully
            if process.returncode is not None and process.returncode != 0:
                if process.stderr:
                    stderr = await process.stderr.read()
                    error_msg = (
                        stderr.decode() if isinstance(stderr, bytes) else str(stderr)
                    )
                else:
                    error_msg = "Process failed to start"
                raise RuntimeError(f"Failed to start recording: {error_msg}")

            return AudioStream(process)

        except (FileNotFoundError, OSError) as e:
            raise RuntimeError(f"Failed to start parec recording: {e}") from e


class SoxBackend(AudioBackend):
    """SoX audio recording backend."""

    @property
    def name(self) -> str:
        """Name of the backend."""
        return "sox"

    async def is_available(self) -> bool:
        """Check if sox is available."""
        try:
            process = await asyncio.create_subprocess_exec(
                "which",
                "sox",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.wait()
            return process.returncode == 0
        except (FileNotFoundError, OSError):
            return False

    async def list_devices(self) -> list[AudioDevice]:
        """List ALSA devices for SoX."""
        # SoX doesn't have a direct device listing command
        # Return common ALSA device patterns
        devices = [
            AudioDevice(
                id="default",
                name="Default ALSA Device",
                description="System Default Audio Device",
                is_default=True,
            ),
            AudioDevice(
                id="hw:0,0",
                name="Hardware Device 0,0",
                description="Hardware Audio Device 0,0",
                is_default=False,
            ),
            AudioDevice(
                id="hw:1,0",
                name="Hardware Device 1,0",
                description="Hardware Audio Device 1,0",
                is_default=False,
            ),
        ]
        return devices

    async def get_default_device(self) -> AudioDevice:
        """Get the default device for SoX."""
        return AudioDevice(
            id="default",
            name="Default ALSA Device",
            description="System Default Audio Device",
            is_default=True,
        )

    async def start_recording(
        self,
        device: AudioDevice,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> AudioStream:
        """Start recording using SoX."""
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
        if channels <= 0:
            raise ValueError("Channels must be positive")

        try:
            process = await asyncio.create_subprocess_exec(
                "sox",
                "-t",
                "alsa",
                device.id,
                "-t",
                "raw",
                "-r",
                str(sample_rate),
                "-c",
                str(channels),
                "-b",
                "16",
                "-e",
                "signed-integer",
                "-",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Check if process started successfully
            if process.returncode is not None and process.returncode != 0:
                if process.stderr:
                    stderr = await process.stderr.read()
                    error_msg = (
                        stderr.decode() if isinstance(stderr, bytes) else str(stderr)
                    )
                else:
                    error_msg = "Process failed to start"
                raise RuntimeError(f"Failed to start recording: {error_msg}")

            return AudioStream(process)

        except (FileNotFoundError, OSError) as e:
            raise RuntimeError(f"Failed to start SoX recording: {e}") from e


class PwCatBackend(AudioBackend):
    """PipeWire recording backend using pw-cat."""

    @property
    def name(self) -> str:
        """Name of the backend."""
        return "pw-cat"

    async def is_available(self) -> bool:
        """Check if pw-cat is available."""
        try:
            process = await asyncio.create_subprocess_exec(
                "which",
                "pw-cat",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.wait()
            return process.returncode == 0
        except (FileNotFoundError, OSError):
            return False

    async def list_devices(self) -> list[AudioDevice]:
        """List PipeWire devices using pw-dump."""
        try:
            process = await asyncio.create_subprocess_exec(
                "pw-dump",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if process.stdout is None:
                return []
            stdout = await process.stdout.read()
            await process.wait()

            if process.returncode != 0:
                return []

            devices = []
            try:
                pw_data = json.loads(stdout.decode())

                for node in pw_data:
                    if node.get("type") == "PipeWire:Interface:Node" and node.get(
                        "info", {}
                    ).get("props", {}).get("node.name"):
                        props = node["info"]["props"]
                        node_name = props.get("node.name", "")
                        description = props.get("device.description", node_name)

                        # Only include input/source devices
                        if (
                            "source" in node_name.lower()
                            or "input" in node_name.lower()
                        ):
                            device = AudioDevice(
                                id=node_name,
                                name=description,
                                description=description,
                                is_default=False,
                            )
                            devices.append(device)

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse PipeWire device data: {e}")

            return devices

        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Failed to list PipeWire devices: {e}")
            return []

    async def get_default_device(self) -> AudioDevice:
        """Get the default PipeWire input device."""
        return AudioDevice(
            id="default",
            name="Default PipeWire Device",
            description="Default PipeWire Input Device",
            is_default=True,
        )

    async def start_recording(
        self,
        device: AudioDevice,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> AudioStream:
        """Start recording using pw-cat."""
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
        if channels <= 0:
            raise ValueError("Channels must be positive")

        try:
            process = await asyncio.create_subprocess_exec(
                "pw-cat",
                "--record",
                f"--target={device.id}",
                "--format=s16",
                f"--rate={sample_rate}",
                f"--channels={channels}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Check if process started successfully
            if process.returncode is not None and process.returncode != 0:
                if process.stderr:
                    stderr = await process.stderr.read()
                    error_msg = (
                        stderr.decode() if isinstance(stderr, bytes) else str(stderr)
                    )
                else:
                    error_msg = "Process failed to start"
                raise RuntimeError(f"Failed to start recording: {error_msg}")

            return AudioStream(process)

        except (FileNotFoundError, OSError) as e:
            raise RuntimeError(f"Failed to start pw-cat recording: {e}") from e


class AudioRecorder:
    """Main audio recorder class that manages multiple backends."""

    def __init__(self, backends: list[AudioBackend] | None = None) -> None:
        """Initialize the audio recorder."""
        if backends is None:
            # Default backends in order of preference
            self.backends = [
                ParecBackend(),
                PwCatBackend(),
                SoxBackend(),
            ]
        else:
            self.backends = backends

    async def get_available_backends(self) -> list[AudioBackend]:
        """Get list of available backends."""
        available = []
        for backend in self.backends:
            if await backend.is_available():
                available.append(backend)
        return available

    async def _get_first_available_backend(self) -> AudioBackend:
        """Get the first available backend."""
        available = await self.get_available_backends()
        if not available:
            raise RuntimeError("No audio backends available")
        return available[0]

    async def list_devices(self) -> list[AudioDevice]:
        """List available audio devices using the first available backend."""
        backend = await self._get_first_available_backend()
        return await backend.list_devices()

    async def get_default_device(self) -> AudioDevice:
        """Get the default audio device using the first available backend."""
        backend = await self._get_first_available_backend()
        return await backend.get_default_device()

    async def start_recording(
        self,
        device: AudioDevice,
        sample_rate: int = 16000,
        channels: int = 1,
        backend_name: str | None = None,
    ) -> AudioStream:
        """Start recording from the specified device."""
        if backend_name:
            # Use specific backend
            for backend in self.backends:
                if backend.name == backend_name and await backend.is_available():
                    return await backend.start_recording(
                        device, sample_rate=sample_rate, channels=channels
                    )
            raise RuntimeError(f"Backend '{backend_name}' not available")
        else:
            # Use first available backend
            backend = await self._get_first_available_backend()
            return await backend.start_recording(
                device, sample_rate=sample_rate, channels=channels
            )


# Module-level convenience functions


async def detect_audio_system() -> str:
    """Detect the current audio system (PulseAudio, PipeWire, or ALSA)."""
    # Check for PulseAudio
    try:
        process = await asyncio.create_subprocess_exec(
            "pgrep",
            "pulseaudio",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.wait()
        if process.returncode == 0:
            return "pulseaudio"
    except (FileNotFoundError, OSError):
        pass

    # Check for PipeWire
    try:
        process = await asyncio.create_subprocess_exec(
            "pgrep",
            "pipewire",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.wait()
        if process.returncode == 0:
            return "pipewire"
    except (FileNotFoundError, OSError):
        pass

    # Default to ALSA
    return "alsa"


async def list_audio_devices() -> list[AudioDevice]:
    """List available audio devices using default recorder."""
    recorder = AudioRecorder()
    return await recorder.list_devices()


async def get_default_device() -> AudioDevice:
    """Get the default audio device using default recorder."""
    recorder = AudioRecorder()
    return await recorder.get_default_device()
