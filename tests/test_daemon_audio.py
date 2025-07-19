"""Tests for daemon audio integration."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from whisper_dictation.audio import AudioDevice, AudioStream
from whisper_dictation.daemon import Daemon, DaemonMessageHandler
from whisper_dictation.models import (
    DaemonState,
    ErrorResponse,
    ListAudioDevicesRequest,
    ListAudioDevicesResponse,
    StartRecordingRequest,
    StatusResponse,
    StopRecordingRequest,
)


class TestDaemonAudioIntegration:
    """Test audio integration with daemon."""

    @pytest.mark.asyncio
    async def test_daemon_list_audio_devices(self):
        """Test listing audio devices through daemon."""
        daemon = Daemon()
        handler = DaemonMessageHandler(daemon)

        mock_device = AudioDevice(
            id="test", name="Test Device", description="Test", is_default=False
        )

        with patch("whisper_dictation.daemon.AudioRecorder") as mock_recorder_class:
            mock_recorder = AsyncMock()
            mock_recorder.list_devices.return_value = [mock_device]
            mock_recorder_class.return_value = mock_recorder

            request = ListAudioDevicesRequest()
            response = await handler._handle_list_audio_devices(request)

            assert isinstance(response, ListAudioDevicesResponse)
            assert len(response.devices) == 1
            assert response.devices[0]["id"] == "test"
            assert response.devices[0]["name"] == "Test Device"

    @pytest.mark.asyncio
    async def test_daemon_start_recording_success(self):
        """Test starting recording through daemon."""
        daemon = Daemon()
        handler = DaemonMessageHandler(daemon)

        mock_device = AudioDevice(
            id="test-device", name="Test Device", description="Test", is_default=False
        )
        mock_stream = Mock(spec=AudioStream)

        with patch("whisper_dictation.daemon.AudioRecorder") as mock_recorder_class:
            mock_recorder = AsyncMock()
            mock_recorder.list_devices.return_value = [mock_device]
            mock_recorder.start_recording.return_value = mock_stream
            mock_recorder_class.return_value = mock_recorder

            request = StartRecordingRequest(device_id="test-device")
            response = await handler._handle_start_recording(request)

            assert isinstance(response, StatusResponse)
            assert daemon.current_stream == mock_stream
            mock_recorder.start_recording.assert_called_once_with(
                mock_device, sample_rate=16000, channels=1, backend_name=None
            )

    @pytest.mark.asyncio
    async def test_daemon_start_recording_device_not_found(self):
        """Test starting recording with non-existent device."""
        daemon = Daemon()
        handler = DaemonMessageHandler(daemon)

        with patch("whisper_dictation.daemon.AudioRecorder") as mock_recorder_class:
            mock_recorder = AsyncMock()
            mock_recorder.list_devices.return_value = []  # No devices
            mock_recorder_class.return_value = mock_recorder

            request = StartRecordingRequest(device_id="non-existent")
            response = await handler._handle_start_recording(request)

            assert isinstance(response, ErrorResponse)
            assert "not found" in response.message

    @pytest.mark.asyncio
    async def test_daemon_start_recording_already_recording(self):
        """Test starting recording when already recording."""
        daemon = Daemon()
        daemon.current_stream = Mock(spec=AudioStream)  # Already recording
        handler = DaemonMessageHandler(daemon)

        request = StartRecordingRequest(device_id="test")
        response = await handler._handle_start_recording(request)

        assert isinstance(response, ErrorResponse)
        assert response.code == 409
        assert "already in progress" in response.message

    @pytest.mark.asyncio
    async def test_daemon_stop_recording_success(self):
        """Test stopping recording through daemon."""
        daemon = Daemon()
        handler = DaemonMessageHandler(daemon)

        mock_stream = AsyncMock(spec=AudioStream)
        daemon.current_stream = mock_stream

        request = StopRecordingRequest()
        response = await handler._handle_stop_recording(request)

        assert isinstance(response, StatusResponse)
        assert daemon.current_stream is None
        mock_stream.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_daemon_stop_recording_not_recording(self):
        """Test stopping recording when not recording."""
        daemon = Daemon()
        handler = DaemonMessageHandler(daemon)

        request = StopRecordingRequest()
        response = await handler._handle_stop_recording(request)

        assert isinstance(response, ErrorResponse)
        assert response.code == 404
        assert "No recording in progress" in response.message

    @pytest.mark.asyncio
    async def test_daemon_stop_cleans_up_audio_stream(self):
        """Test that daemon stop cleans up audio stream."""
        daemon = Daemon()
        daemon.state = DaemonState.RUNNING  # Set to running state
        mock_stream = AsyncMock(spec=AudioStream)
        daemon.current_stream = mock_stream

        await daemon.stop()

        mock_stream.close.assert_called_once()
        assert daemon.current_stream is None

    @pytest.mark.asyncio
    async def test_daemon_uses_default_device(self):
        """Test using default device for recording."""
        daemon = Daemon()
        handler = DaemonMessageHandler(daemon)

        mock_device = AudioDevice(
            id="default", name="Default Device", description="Default", is_default=True
        )
        mock_stream = Mock(spec=AudioStream)

        with patch("whisper_dictation.daemon.AudioRecorder") as mock_recorder_class:
            mock_recorder = AsyncMock()
            mock_recorder.get_default_device.return_value = mock_device
            mock_recorder.start_recording.return_value = mock_stream
            mock_recorder_class.return_value = mock_recorder

            request = StartRecordingRequest(device_id="default")
            response = await handler._handle_start_recording(request)

            assert isinstance(response, StatusResponse)
            mock_recorder.get_default_device.assert_called_once()
            mock_recorder.start_recording.assert_called_once_with(
                mock_device, sample_rate=16000, channels=1, backend_name=None
            )
