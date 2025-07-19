"""Type definitions and data models for whisper_dictation."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DaemonState(Enum):
    """States that the daemon can be in."""

    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


class IPCMessageType(Enum):
    """Types of IPC messages."""

    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    STATUS = "status"
    ERROR = "error"


@dataclass
class IPCMessage:
    """Base class for IPC messages."""

    type: IPCMessageType
    data: dict[str, Any] | None = None


class StartRequest(IPCMessage):
    """Request to start the daemon."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize StartRequest."""
        data = {"config": config} if config is not None else None
        super().__init__(type=IPCMessageType.START, data=data)
        self.config = config


class StopRequest(IPCMessage):
    """Request to stop the daemon."""

    def __init__(self) -> None:
        """Initialize StopRequest."""
        super().__init__(type=IPCMessageType.STOP)


class PauseRequest(IPCMessage):
    """Request to pause the daemon."""

    def __init__(self) -> None:
        """Initialize PauseRequest."""
        super().__init__(type=IPCMessageType.PAUSE)


class ResumeRequest(IPCMessage):
    """Request to resume the daemon."""

    def __init__(self) -> None:
        """Initialize ResumeRequest."""
        super().__init__(type=IPCMessageType.RESUME)


class StatusRequest(IPCMessage):
    """Request daemon status."""

    def __init__(self) -> None:
        """Initialize StatusRequest."""
        super().__init__(type=IPCMessageType.STATUS)


class StatusResponse(IPCMessage):
    """Response with daemon status."""

    def __init__(
        self,
        state: DaemonState,
        uptime: float,
        model_loaded: bool,
        current_model: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Initialize StatusResponse."""
        data = {
            "state": state,
            "uptime": uptime,
            "model_loaded": model_loaded,
        }
        if current_model is not None:
            data["current_model"] = current_model
        if error_message is not None:
            data["error_message"] = error_message

        super().__init__(type=IPCMessageType.STATUS, data=data)
        self.state = state
        self.uptime = uptime
        self.model_loaded = model_loaded
        self.current_model = current_model
        self.error_message = error_message


class ErrorResponse(IPCMessage):
    """Error response message."""

    def __init__(self, message: str, code: int = 1) -> None:
        """Initialize ErrorResponse."""
        data = {"message": message, "code": code}
        super().__init__(type=IPCMessageType.ERROR, data=data)
        self.message = message
        self.code = code
