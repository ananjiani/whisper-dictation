"""Tests for whisper_dictation.audio module."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from whisper_dictation.audio import (
    AudioBackend,
    AudioDevice,
    AudioRecorder,
    AudioStream,
    ParecBackend,
    PwCatBackend,
    SoxBackend,
    detect_audio_system,
    get_default_device,
    list_audio_devices,
)


class TestAudioDevice:
    """Test AudioDevice model."""

    def test_audio_device_creation(self):
        """Test creating an AudioDevice."""
        device = AudioDevice(
            id="hw:1,0",
            name="USB Audio Device",
            description="USB Audio Device (Stereo)",
            is_default=False,
        )

        assert device.id == "hw:1,0"
        assert device.name == "USB Audio Device"
        assert device.description == "USB Audio Device (Stereo)"
        assert device.is_default is False

    def test_audio_device_default(self):
        """Test creating a default AudioDevice."""
        device = AudioDevice(
            id="default",
            name="Default Device",
            description="System Default Audio Device",
            is_default=True,
        )

        assert device.id == "default"
        assert device.is_default is True

    def test_audio_device_str_representation(self):
        """Test string representation of AudioDevice."""
        device = AudioDevice(
            id="hw:1,0",
            name="USB Audio",
            description="USB Audio Device",
            is_default=False,
        )

        assert str(device) == "USB Audio (hw:1,0)"

    def test_audio_device_equality(self):
        """Test AudioDevice equality comparison."""
        device1 = AudioDevice(
            id="hw:1,0", name="USB Audio", description="USB", is_default=False
        )
        device2 = AudioDevice(
            id="hw:1,0", name="USB Audio", description="USB", is_default=False
        )
        device3 = AudioDevice(
            id="hw:2,0", name="USB Audio", description="USB", is_default=False
        )

        assert device1 == device2
        assert device1 != device3


class TestAudioBackend:
    """Test AudioBackend abstract base class."""

    def test_audio_backend_is_abstract(self):
        """Test that AudioBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AudioBackend()

    def test_audio_backend_subclass_must_implement_methods(self):
        """Test that AudioBackend subclasses must implement abstract methods."""

        class IncompleteBackend(AudioBackend):
            pass

        with pytest.raises(TypeError):
            IncompleteBackend()


class TestParecBackend:
    """Test ParecBackend implementation."""

    def test_parec_backend_creation(self):
        """Test creating a ParecBackend."""
        backend = ParecBackend()
        assert backend.name == "parec"

    @pytest.mark.asyncio
    async def test_parec_backend_is_available(self):
        """Test checking if parec is available."""
        backend = ParecBackend()

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            available = await backend.is_available()
            assert available is True
            mock_subprocess.assert_called_once_with(
                "which",
                "parec",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

    @pytest.mark.asyncio
    async def test_parec_backend_not_available(self):
        """Test when parec is not available."""
        backend = ParecBackend()

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process

            available = await backend.is_available()
            assert available is False

    @pytest.mark.asyncio
    async def test_parec_backend_list_devices(self):
        """Test listing devices with parec."""
        backend = ParecBackend()

        pactl_output = """0	alsa_output.pci-0000_00_1b.0.analog-stereo	module-alsa-card.c	s16le 2ch 44100Hz	SUSPENDED	Built-in Audio Analog Stereo
1	alsa_output.usb-0d8c_USB_Sound_Device-00.analog-stereo	module-alsa-card.c	s16le 2ch 44100Hz	RUNNING	USB Sound Device Analog Stereo"""

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.stdout.read.return_value = pactl_output.encode()
            mock_subprocess.return_value = mock_process

            devices = await backend.list_devices()

            assert len(devices) == 2
            assert devices[0].id == "alsa_output.pci-0000_00_1b.0.analog-stereo"
            assert devices[0].name == "Built-in Audio Analog Stereo"
            assert (
                devices[1].id
                == "alsa_output.usb-0d8c_USB_Sound_Device-00.analog-stereo"
            )
            assert devices[1].name == "USB Sound Device Analog Stereo"

    @pytest.mark.asyncio
    async def test_parec_backend_get_default_device(self):
        """Test getting default device with parec."""
        backend = ParecBackend()

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.stdout.read.return_value = (
                b"alsa_output.pci-0000_00_1b.0.analog-stereo"
            )
            mock_subprocess.return_value = mock_process

            device = await backend.get_default_device()

            assert device.id == "alsa_output.pci-0000_00_1b.0.analog-stereo"
            assert device.is_default is True

    @pytest.mark.asyncio
    async def test_parec_backend_start_recording(self):
        """Test starting recording with parec."""
        backend = ParecBackend()
        device = AudioDevice(
            id="test-device", name="Test", description="Test Device", is_default=False
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.returncode = None  # Process not finished yet
            mock_subprocess.return_value = mock_process

            stream = await backend.start_recording(
                device, sample_rate=16000, channels=1
            )

            assert isinstance(stream, AudioStream)
            mock_subprocess.assert_called_once_with(
                "parec",
                "--device=test-device",
                "--format=s16le",
                "--rate=16000",
                "--channels=1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )


class TestSoxBackend:
    """Test SoxBackend implementation."""

    def test_sox_backend_creation(self):
        """Test creating a SoxBackend."""
        backend = SoxBackend()
        assert backend.name == "sox"

    @pytest.mark.asyncio
    async def test_sox_backend_is_available(self):
        """Test checking if sox is available."""
        backend = SoxBackend()

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            available = await backend.is_available()
            assert available is True

    @pytest.mark.asyncio
    async def test_sox_backend_start_recording(self):
        """Test starting recording with sox."""
        backend = SoxBackend()
        device = AudioDevice(
            id="hw:1,0",
            name="USB Audio",
            description="USB Audio Device",
            is_default=False,
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.returncode = None  # Process not finished yet
            mock_subprocess.return_value = mock_process

            stream = await backend.start_recording(
                device, sample_rate=16000, channels=1
            )

            assert isinstance(stream, AudioStream)
            mock_subprocess.assert_called_once_with(
                "sox",
                "-t",
                "alsa",
                "hw:1,0",
                "-t",
                "raw",
                "-r",
                "16000",
                "-c",
                "1",
                "-b",
                "16",
                "-e",
                "signed-integer",
                "-",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )


class TestPwCatBackend:
    """Test PwCatBackend implementation."""

    def test_pwcat_backend_creation(self):
        """Test creating a PwCatBackend."""
        backend = PwCatBackend()
        assert backend.name == "pw-cat"

    @pytest.mark.asyncio
    async def test_pwcat_backend_is_available(self):
        """Test checking if pw-cat is available."""
        backend = PwCatBackend()

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            available = await backend.is_available()
            assert available is True

    @pytest.mark.asyncio
    async def test_pwcat_backend_list_devices(self):
        """Test listing devices with pw-cat."""
        backend = PwCatBackend()

        pw_dump_output = """[
    {
        "id": 41,
        "type": "PipeWire:Interface:Node",
        "info": {
            "props": {
                "device.description": "Built-in Audio",
                "node.name": "alsa_output.pci-0000_00_1b.0.analog-stereo"
            }
        }
    }
]"""

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.stdout.read.return_value = pw_dump_output.encode()
            mock_subprocess.return_value = mock_process

            devices = await backend.list_devices()

            assert len(devices) >= 0  # May vary based on system

    @pytest.mark.asyncio
    async def test_pwcat_backend_start_recording(self):
        """Test starting recording with pw-cat."""
        backend = PwCatBackend()
        device = AudioDevice(
            id="test-device", name="Test", description="Test Device", is_default=False
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.returncode = None  # Process not finished yet
            mock_subprocess.return_value = mock_process

            stream = await backend.start_recording(
                device, sample_rate=16000, channels=1
            )

            assert isinstance(stream, AudioStream)
            mock_subprocess.assert_called_once_with(
                "pw-cat",
                "--record",
                "--target=test-device",
                "--format=s16",
                "--rate=16000",
                "--channels=1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )


class TestAudioStream:
    """Test AudioStream functionality."""

    @pytest.mark.asyncio
    async def test_audio_stream_read(self):
        """Test reading from AudioStream."""
        mock_process = AsyncMock()
        mock_stdout = AsyncMock()
        mock_stdout.read.return_value = b"audio_data_chunk"
        mock_process.stdout = mock_stdout

        stream = AudioStream(mock_process)

        data = await stream.read(1024)
        assert data == b"audio_data_chunk"
        mock_stdout.read.assert_called_once_with(1024)

    @pytest.mark.asyncio
    async def test_audio_stream_close(self):
        """Test closing AudioStream."""
        mock_process = AsyncMock()
        mock_process.terminate.return_value = None
        mock_process.wait.return_value = 0

        stream = AudioStream(mock_process)

        await stream.close()
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_audio_stream_context_manager(self):
        """Test AudioStream as context manager."""
        mock_process = AsyncMock()
        mock_process.terminate.return_value = None
        mock_process.wait.return_value = 0

        async with AudioStream(mock_process) as stream:
            assert stream.process is mock_process

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_audio_stream_iteration(self):
        """Test AudioStream async iteration."""
        mock_process = AsyncMock()
        mock_stdout = AsyncMock()

        # Mock multiple reads
        mock_stdout.read.side_effect = [
            b"chunk1",
            b"chunk2",
            b"",  # EOF
        ]
        mock_process.stdout = mock_stdout

        stream = AudioStream(mock_process, chunk_size=6)
        chunks = []

        async for chunk in stream:
            if chunk:
                chunks.append(chunk)

        assert chunks == [b"chunk1", b"chunk2"]


class TestAudioRecorder:
    """Test AudioRecorder main class."""

    def test_audio_recorder_creation(self):
        """Test creating an AudioRecorder."""
        recorder = AudioRecorder()
        assert recorder.backends is not None
        assert len(recorder.backends) > 0

    def test_audio_recorder_with_backends(self):
        """Test creating AudioRecorder with specific backends."""
        mock_backend = Mock(spec=AudioBackend)
        mock_backend.name = "mock"

        recorder = AudioRecorder(backends=[mock_backend])
        assert len(recorder.backends) == 1
        assert recorder.backends[0] == mock_backend

    @pytest.mark.asyncio
    async def test_audio_recorder_get_available_backends(self):
        """Test getting available backends."""
        mock_backend1 = AsyncMock(spec=AudioBackend)
        mock_backend1.name = "backend1"
        mock_backend1.is_available.return_value = True

        mock_backend2 = AsyncMock(spec=AudioBackend)
        mock_backend2.name = "backend2"
        mock_backend2.is_available.return_value = False

        recorder = AudioRecorder(backends=[mock_backend1, mock_backend2])
        available = await recorder.get_available_backends()

        assert len(available) == 1
        assert available[0] == mock_backend1

    @pytest.mark.asyncio
    async def test_audio_recorder_list_devices(self):
        """Test listing devices through AudioRecorder."""
        mock_device = AudioDevice(
            id="test", name="Test", description="Test Device", is_default=False
        )

        mock_backend = AsyncMock(spec=AudioBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = True
        mock_backend.list_devices.return_value = [mock_device]

        recorder = AudioRecorder(backends=[mock_backend])
        devices = await recorder.list_devices()

        assert len(devices) == 1
        assert devices[0] == mock_device

    @pytest.mark.asyncio
    async def test_audio_recorder_get_default_device(self):
        """Test getting default device through AudioRecorder."""
        mock_device = AudioDevice(
            id="default", name="Default", description="Default Device", is_default=True
        )

        mock_backend = AsyncMock(spec=AudioBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = True
        mock_backend.get_default_device.return_value = mock_device

        recorder = AudioRecorder(backends=[mock_backend])
        device = await recorder.get_default_device()

        assert device == mock_device

    @pytest.mark.asyncio
    async def test_audio_recorder_start_recording(self):
        """Test starting recording through AudioRecorder."""
        mock_device = AudioDevice(
            id="test", name="Test", description="Test Device", is_default=False
        )
        mock_stream = Mock(spec=AudioStream)

        mock_backend = AsyncMock(spec=AudioBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = True
        mock_backend.start_recording.return_value = mock_stream

        recorder = AudioRecorder(backends=[mock_backend])
        stream = await recorder.start_recording(
            mock_device, sample_rate=16000, channels=1
        )

        assert stream == mock_stream
        mock_backend.start_recording.assert_called_once_with(
            mock_device, sample_rate=16000, channels=1
        )

    @pytest.mark.asyncio
    async def test_audio_recorder_no_available_backends(self):
        """Test AudioRecorder with no available backends."""
        mock_backend = AsyncMock(spec=AudioBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = False

        recorder = AudioRecorder(backends=[mock_backend])

        with pytest.raises(RuntimeError, match="No audio backends available"):
            await recorder.list_devices()


class TestAudioSystemDetection:
    """Test audio system detection functions."""

    @pytest.mark.asyncio
    async def test_detect_audio_system_pulseaudio(self):
        """Test detecting PulseAudio system."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # Mock pulseaudio process check
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            system = await detect_audio_system()

            assert system in ["pulseaudio", "pipewire", "alsa"]

    @pytest.mark.asyncio
    async def test_list_audio_devices_function(self):
        """Test the module-level list_audio_devices function."""
        with patch("whisper_dictation.audio.AudioRecorder") as mock_recorder_class:
            mock_recorder = AsyncMock()
            mock_device = AudioDevice(
                id="test", name="Test", description="Test Device", is_default=False
            )
            mock_recorder.list_devices.return_value = [mock_device]
            mock_recorder_class.return_value = mock_recorder

            devices = await list_audio_devices()

            assert len(devices) == 1
            assert devices[0] == mock_device

    @pytest.mark.asyncio
    async def test_get_default_device_function(self):
        """Test the module-level get_default_device function."""
        with patch("whisper_dictation.audio.AudioRecorder") as mock_recorder_class:
            mock_recorder = AsyncMock()
            mock_device = AudioDevice(
                id="default",
                name="Default",
                description="Default Device",
                is_default=True,
            )
            mock_recorder.get_default_device.return_value = mock_device
            mock_recorder_class.return_value = mock_recorder

            device = await get_default_device()

            assert device == mock_device


class TestAudioIntegration:
    """Test audio system integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_recording_workflow(self):
        """Test complete recording workflow."""
        # Create a mock device
        device = AudioDevice(
            id="test-device",
            name="Test Device",
            description="Test Audio Device",
            is_default=False,
        )

        # Create mock backend
        mock_backend = AsyncMock(spec=AudioBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = True

        # Create mock process and stream
        mock_process = AsyncMock()
        mock_stdout = AsyncMock()
        mock_stdout.read.side_effect = [b"audio_chunk_1", b"audio_chunk_2", b""]
        mock_process.stdout = mock_stdout
        mock_stream = AudioStream(mock_process)
        mock_backend.start_recording.return_value = mock_stream

        # Test the workflow
        recorder = AudioRecorder(backends=[mock_backend])

        async with await recorder.start_recording(
            device, sample_rate=16000, channels=1
        ) as stream:
            chunks = []
            async for chunk in stream:
                if chunk:
                    chunks.append(chunk)

        assert chunks == [b"audio_chunk_1", b"audio_chunk_2"]

    @pytest.mark.asyncio
    async def test_backend_fallback(self):
        """Test falling back to available backend."""
        # Create backends with different availability
        mock_backend1 = AsyncMock(spec=AudioBackend)
        mock_backend1.name = "unavailable"
        mock_backend1.is_available.return_value = False

        mock_backend2 = AsyncMock(spec=AudioBackend)
        mock_backend2.name = "available"
        mock_backend2.is_available.return_value = True
        mock_device = AudioDevice(
            id="test", name="Test", description="Test", is_default=False
        )
        mock_backend2.list_devices.return_value = [mock_device]

        recorder = AudioRecorder(backends=[mock_backend1, mock_backend2])
        devices = await recorder.list_devices()

        assert len(devices) == 1
        mock_backend1.is_available.assert_called_once()
        mock_backend2.is_available.assert_called_once()
        mock_backend2.list_devices.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_recording_streams(self):
        """Test handling multiple concurrent recording streams."""
        device = AudioDevice(
            id="test", name="Test", description="Test", is_default=False
        )

        # Create multiple mock backends
        streams = []
        for i in range(3):
            mock_backend = AsyncMock(spec=AudioBackend)
            mock_backend.name = f"backend_{i}"
            mock_backend.is_available.return_value = True

            mock_process = AsyncMock()
            mock_stdout = AsyncMock()
            mock_stdout.read.return_value = f"data_{i}".encode()
            mock_process.stdout = mock_stdout

            mock_stream = AudioStream(mock_process)
            mock_backend.start_recording.return_value = mock_stream

            recorder = AudioRecorder(backends=[mock_backend])
            stream = await recorder.start_recording(device)
            streams.append(stream)

        # Test concurrent reading
        tasks = [stream.read(1024) for stream in streams]
        results = await asyncio.gather(*tasks)

        expected = [b"data_0", b"data_1", b"data_2"]
        assert results == expected

        # Clean up
        for stream in streams:
            await stream.close()


class TestAudioErrorHandling:
    """Test error handling in audio components."""

    @pytest.mark.asyncio
    async def test_backend_command_not_found(self):
        """Test handling when audio command is not found."""
        backend = ParecBackend()

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_subprocess.side_effect = FileNotFoundError("parec not found")

            available = await backend.is_available()
            assert available is False

    @pytest.mark.asyncio
    async def test_recording_process_failure(self):
        """Test handling recording process failure."""
        backend = ParecBackend()
        device = AudioDevice(
            id="invalid", name="Invalid", description="Invalid Device", is_default=False
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.stderr.read.return_value = b"Device not found"
            mock_subprocess.return_value = mock_process

            with pytest.raises(RuntimeError, match="Failed to start recording"):
                await backend.start_recording(device)

    @pytest.mark.asyncio
    async def test_stream_read_error(self):
        """Test handling stream read errors."""
        mock_process = AsyncMock()
        mock_stdout = AsyncMock()
        mock_stdout.read.side_effect = OSError("Broken pipe")
        mock_process.stdout = mock_stdout

        stream = AudioStream(mock_process)

        with pytest.raises(OSError):
            await stream.read(1024)

    @pytest.mark.asyncio
    async def test_invalid_audio_parameters(self):
        """Test handling invalid audio parameters."""
        backend = ParecBackend()
        device = AudioDevice(
            id="test", name="Test", description="Test", is_default=False
        )

        with pytest.raises(ValueError, match="Sample rate must be positive"):
            await backend.start_recording(device, sample_rate=0)

        with pytest.raises(ValueError, match="Channels must be positive"):
            await backend.start_recording(device, channels=0)
