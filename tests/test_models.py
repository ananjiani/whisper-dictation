"""Tests for whisper_dictation.models module."""

from enum import Enum

from whisper_dictation.models import (
    DaemonState,
    ErrorResponse,
    IPCMessage,
    IPCMessageType,
    PauseRequest,
    ResumeRequest,
    StartRequest,
    StatusRequest,
    StatusResponse,
    StopRequest,
)


class TestDaemonState:
    """Test DaemonState enum."""

    def test_daemon_state_values(self):
        """Test that DaemonState has expected values."""
        assert DaemonState.STARTING.value == "starting"
        assert DaemonState.RUNNING.value == "running"
        assert DaemonState.PAUSED.value == "paused"
        assert DaemonState.STOPPING.value == "stopping"
        assert DaemonState.STOPPED.value == "stopped"

    def test_daemon_state_is_enum(self):
        """Test that DaemonState is an Enum."""
        assert issubclass(DaemonState, Enum)


class TestIPCMessageType:
    """Test IPCMessageType enum."""

    def test_ipc_message_type_values(self):
        """Test that IPCMessageType has expected values."""
        assert IPCMessageType.START.value == "start"
        assert IPCMessageType.STOP.value == "stop"
        assert IPCMessageType.PAUSE.value == "pause"
        assert IPCMessageType.RESUME.value == "resume"
        assert IPCMessageType.STATUS.value == "status"
        assert IPCMessageType.ERROR.value == "error"

    def test_ipc_message_type_is_enum(self):
        """Test that IPCMessageType is an Enum."""
        assert issubclass(IPCMessageType, Enum)


class TestIPCMessage:
    """Test IPCMessage base class."""

    def test_ipc_message_creation(self):
        """Test creating an IPCMessage."""
        msg = IPCMessage(type=IPCMessageType.STATUS, data={"test": "data"})
        assert msg.type == IPCMessageType.STATUS
        assert msg.data == {"test": "data"}

    def test_ipc_message_optional_data(self):
        """Test IPCMessage with no data."""
        msg = IPCMessage(type=IPCMessageType.STOP)
        assert msg.type == IPCMessageType.STOP
        assert msg.data is None


class TestStartRequest:
    """Test StartRequest message."""

    def test_start_request_creation(self):
        """Test creating a StartRequest."""
        req = StartRequest()
        assert req.type == IPCMessageType.START
        assert req.data is None

    def test_start_request_with_config(self):
        """Test StartRequest with configuration."""
        config = {"model": "base", "device": "auto"}
        req = StartRequest(config=config)
        assert req.type == IPCMessageType.START
        assert req.data == {"config": config}


class TestStopRequest:
    """Test StopRequest message."""

    def test_stop_request_creation(self):
        """Test creating a StopRequest."""
        req = StopRequest()
        assert req.type == IPCMessageType.STOP
        assert req.data is None


class TestPauseRequest:
    """Test PauseRequest message."""

    def test_pause_request_creation(self):
        """Test creating a PauseRequest."""
        req = PauseRequest()
        assert req.type == IPCMessageType.PAUSE
        assert req.data is None


class TestResumeRequest:
    """Test ResumeRequest message."""

    def test_resume_request_creation(self):
        """Test creating a ResumeRequest."""
        req = ResumeRequest()
        assert req.type == IPCMessageType.RESUME
        assert req.data is None


class TestStatusRequest:
    """Test StatusRequest message."""

    def test_status_request_creation(self):
        """Test creating a StatusRequest."""
        req = StatusRequest()
        assert req.type == IPCMessageType.STATUS
        assert req.data is None


class TestStatusResponse:
    """Test StatusResponse message."""

    def test_status_response_creation(self):
        """Test creating a StatusResponse."""
        resp = StatusResponse(
            state=DaemonState.RUNNING, uptime=123.45, model_loaded=True
        )
        assert resp.type == IPCMessageType.STATUS
        assert resp.state == DaemonState.RUNNING
        assert resp.uptime == 123.45
        assert resp.model_loaded is True
        assert resp.data == {
            "state": DaemonState.RUNNING,
            "uptime": 123.45,
            "model_loaded": True,
        }

    def test_status_response_optional_fields(self):
        """Test StatusResponse with optional fields."""
        resp = StatusResponse(
            state=DaemonState.STARTING,
            uptime=0.0,
            model_loaded=False,
            current_model="base",
            error_message="Loading model...",
        )
        assert resp.current_model == "base"
        assert resp.error_message == "Loading model..."
        assert resp.data["current_model"] == "base"
        assert resp.data["error_message"] == "Loading model..."


class TestErrorResponse:
    """Test ErrorResponse message."""

    def test_error_response_creation(self):
        """Test creating an ErrorResponse."""
        resp = ErrorResponse(message="Something went wrong", code=500)
        assert resp.type == IPCMessageType.ERROR
        assert resp.message == "Something went wrong"
        assert resp.code == 500
        assert resp.data == {
            "message": "Something went wrong",
            "code": 500,
        }

    def test_error_response_default_code(self):
        """Test ErrorResponse with default error code."""
        resp = ErrorResponse(message="Error occurred")
        assert resp.message == "Error occurred"
        assert resp.code == 1
        assert resp.data["code"] == 1
