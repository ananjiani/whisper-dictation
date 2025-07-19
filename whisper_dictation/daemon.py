"""Daemon implementation for whisper_dictation."""

import asyncio
import logging
import os
import signal
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import Config
from .ipc import IPCServer, MessageHandler
from .models import (
    DaemonState,
    ErrorResponse,
    IPCMessage,
    StatusResponse,
)

logger = logging.getLogger(__name__)


class DaemonError(Exception):
    """Base exception for daemon-related errors."""

    pass


class SingleInstanceError(DaemonError):
    """Raised when trying to start a daemon when one is already running."""

    pass


class ConfigurationError(DaemonError):
    """Raised when there's a configuration error."""

    pass


class DaemonMessageHandler(MessageHandler):
    """Message handler that integrates with daemon."""

    def __init__(self, daemon: "Daemon") -> None:
        super().__init__()
        self.daemon = daemon

    async def _handle_start(self, message: IPCMessage) -> IPCMessage:  # noqa: ARG002
        """Handle start request."""
        try:
            if self.daemon.state != DaemonState.STOPPED:
                return ErrorResponse("Daemon already running", 409)
            await self.daemon.start()
            return self.daemon.get_status()
        except Exception as e:
            return ErrorResponse(str(e))

    async def _handle_stop(self, message: IPCMessage) -> IPCMessage:  # noqa: ARG002
        """Handle stop request."""
        try:
            await self.daemon.stop()
            return StatusResponse(
                state=DaemonState.STOPPED,
                uptime=0.0,
                model_loaded=False,
            )
        except Exception as e:
            return ErrorResponse(str(e))

    async def _handle_pause(self, message: IPCMessage) -> IPCMessage:  # noqa: ARG002
        """Handle pause request."""
        try:
            await self.daemon.pause()
            return self.daemon.get_status()
        except Exception as e:
            return ErrorResponse(str(e))

    async def _handle_resume(self, message: IPCMessage) -> IPCMessage:  # noqa: ARG002
        """Handle resume request."""
        try:
            await self.daemon.resume()
            return self.daemon.get_status()
        except Exception as e:
            return ErrorResponse(str(e))

    async def _handle_status(self, message: IPCMessage) -> IPCMessage:  # noqa: ARG002
        """Handle status request."""
        return self.daemon.get_status()


class Daemon:
    """Main daemon class for whisper_dictation."""

    def __init__(
        self, config: Config | None = None, pid_file: Path | None = None
    ) -> None:
        """Initialize the daemon."""
        self.config = config or Config()
        self.pid_file = pid_file or Path(tempfile.gettempdir()) / "whisper_daemon.pid"
        self.state = DaemonState.STOPPED
        self.ipc_server: IPCServer | None = None
        self.message_handler: DaemonMessageHandler | None = None
        self.start_time: float | None = None
        self.pause_time: float | None = None
        self.total_paused_time: float = 0
        self._shutdown_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Start unpaused

    async def start(self) -> None:
        """Start the daemon."""
        if self.state != DaemonState.STOPPED:
            raise DaemonError(f"Cannot start daemon in state {self.state}")

        if self.pid_file.exists():
            pid = int(self.pid_file.read_text().strip())
            if self._is_process_running(pid):
                raise SingleInstanceError(f"Daemon already running with PID {pid}")

        self.state = DaemonState.STARTING
        self.start_time = time.time()
        self._write_pid_file()

        # Setup IPC server with message handler
        self.message_handler = DaemonMessageHandler(self)

        # Use socket path from config or fallback to default
        # After Config.__post_init__, daemon is guaranteed to be non-None
        assert self.config.daemon is not None
        if self.config.daemon.socket_path:
            socket_path = Path(self.config.daemon.socket_path)
        else:
            from .config import get_socket_path

            socket_path = get_socket_path()

        self.ipc_server = IPCServer(socket_path, self.message_handler)
        await self.ipc_server.start()

        self.state = DaemonState.RUNNING

    async def stop(self) -> None:
        """Stop the daemon."""
        if self.state == DaemonState.STOPPED:
            return

        self.state = DaemonState.STOPPING

        if self.ipc_server:
            await self.ipc_server.stop()

        self._cleanup_pid_file()
        self.state = DaemonState.STOPPED
        self._shutdown_event.set()

    async def pause(self) -> None:
        """Pause the daemon."""
        if self.state != DaemonState.RUNNING:
            raise DaemonError(f"Cannot pause daemon in state {self.state}")

        self.state = DaemonState.PAUSED
        self.pause_time = time.time()
        self._pause_event.clear()

    async def resume(self) -> None:
        """Resume the daemon."""
        if self.state != DaemonState.PAUSED:
            raise DaemonError(f"Cannot resume daemon in state {self.state}")

        if self.pause_time:
            self.total_paused_time += time.time() - self.pause_time
            self.pause_time = None

        self.state = DaemonState.RUNNING
        self._pause_event.set()

    def get_uptime(self) -> float:
        """Get daemon uptime in seconds."""
        if not self.start_time:
            return 0

        current_time = time.time()
        uptime = current_time - self.start_time - self.total_paused_time

        if self.state == DaemonState.PAUSED and self.pause_time:
            uptime -= current_time - self.pause_time

        return max(0, uptime)

    def get_status(self) -> StatusResponse:
        """Get daemon status."""
        return StatusResponse(
            state=self.state,
            uptime=self.get_uptime(),
            model_loaded=False,  # Mock value for now
        )

    def is_running(self) -> bool:
        """Check if daemon is running by checking PID file."""
        if not self.pid_file.exists():
            return False

        try:
            pid = int(self.pid_file.read_text().strip())
            return self._is_process_running(pid)
        except (ValueError, OSError):
            return False

    async def handle_signal(self, signum: int) -> None:
        """Handle system signals."""
        if signum == signal.SIGTERM or signum == signal.SIGINT:
            await self.stop()
        elif signum == signal.SIGUSR1:
            if self.state == DaemonState.RUNNING:
                await self.pause()
            elif self.state == DaemonState.PAUSED:
                await self.resume()

    async def run(self) -> None:
        """Main daemon loop."""
        await self.start()
        try:
            while not self._shutdown_event.is_set():
                await self._pause_event.wait()
                await asyncio.sleep(0.1)  # Main loop iteration
        finally:
            await self.stop()

    async def __aenter__(self) -> "Daemon":
        """Context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        await self.stop()

    def _write_pid_file(self) -> None:
        """Write PID to file."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))

    def _cleanup_pid_file(self) -> None:
        """Remove PID file."""
        if self.pid_file.exists():
            self.pid_file.unlink()

    def _is_process_running(self, pid: int) -> bool:
        """Check if process with given PID is running."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
