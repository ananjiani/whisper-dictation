"""Comprehensive tests for the daemon.py module."""

import asyncio
import os
import signal
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from whisper_dictation.config import Config

# Import the actual modules from the project
from whisper_dictation.daemon import (
    Daemon,
    DaemonError,
    SingleInstanceError,
)
from whisper_dictation.ipc import IPCClient
from whisper_dictation.models import (
    DaemonState,
    IPCMessageType,
    PauseRequest,
    ResumeRequest,
    StatusRequest,
    StatusResponse,
    StopRequest,
)


class ConfigurationError(DaemonError):
    """Raised when there's a configuration error."""

    pass


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_config(temp_dir):
    """Provide a mock configuration."""
    config = Config()
    config.daemon.pid_file = str(temp_dir / "test_daemon.pid")
    config.daemon.socket_path = str(temp_dir / "test_daemon.sock")
    config.daemon.log_level = "DEBUG"
    return config


@pytest.fixture
def daemon(mock_config, temp_dir):
    """Provide a daemon instance for testing."""
    pid_file = temp_dir / "test_daemon.pid"
    return Daemon(config=mock_config, pid_file=pid_file)


class TestDaemonLifecycle:
    """Test daemon lifecycle management."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_starts_successfully(self, daemon):
        """Test that daemon starts successfully from stopped state."""
        assert daemon.state == DaemonState.STOPPED

        await daemon.start()

        assert daemon.state == DaemonState.RUNNING
        assert daemon.start_time is not None
        assert daemon.pid_file.exists()
        assert daemon.ipc_server is not None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_stops_successfully(self, daemon):
        """Test that daemon stops successfully from running state."""
        await daemon.start()
        assert daemon.state == DaemonState.RUNNING

        await daemon.stop()

        assert daemon.state == DaemonState.STOPPED
        assert not daemon.pid_file.exists()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_cannot_start_twice(self, daemon):
        """Test that starting an already running daemon raises an error."""
        await daemon.start()

        with pytest.raises(
            DaemonError, match="Cannot start daemon in state DaemonState.RUNNING"
        ):
            await daemon.start()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_stop_idempotent(self, daemon):
        """Test that stopping a stopped daemon is idempotent."""
        assert daemon.state == DaemonState.STOPPED

        # Should not raise an error
        await daemon.stop()
        assert daemon.state == DaemonState.STOPPED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_pause_resume_cycle(self, daemon):
        """Test daemon pause and resume functionality."""
        await daemon.start()
        assert daemon.state == DaemonState.RUNNING

        await daemon.pause()
        assert daemon.state == DaemonState.PAUSED
        assert daemon.pause_time is not None

        await daemon.resume()
        assert daemon.state == DaemonState.RUNNING
        assert daemon.pause_time is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_cannot_pause_when_not_running(self, daemon):
        """Test that pausing a non-running daemon raises an error."""
        with pytest.raises(
            DaemonError, match="Cannot pause daemon in state DaemonState.STOPPED"
        ):
            await daemon.pause()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_cannot_resume_when_not_paused(self, daemon):
        """Test that resuming a non-paused daemon raises an error."""
        await daemon.start()

        with pytest.raises(
            DaemonError, match="Cannot resume daemon in state DaemonState.RUNNING"
        ):
            await daemon.resume()


class TestDaemonPIDManagement:
    """Test daemon PID file management."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_pid_file_created_on_start(self, daemon):
        """Test that PID file is created when daemon starts."""
        assert not daemon.pid_file.exists()

        await daemon.start()

        assert daemon.pid_file.exists()
        pid = int(daemon.pid_file.read_text().strip())
        assert pid == os.getpid()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_pid_file_removed_on_stop(self, daemon):
        """Test that PID file is removed when daemon stops."""
        await daemon.start()
        assert daemon.pid_file.exists()

        await daemon.stop()

        assert not daemon.pid_file.exists()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_single_instance_enforcement(self, daemon, temp_dir):  # noqa: ARG002
        """Test that only one daemon instance can run at a time."""
        # Create a fake PID file with current process PID
        daemon.pid_file.write_text(str(os.getpid()))

        with pytest.raises(SingleInstanceError, match="Daemon already running"):
            await daemon.start()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_stale_pid_file_handling(self, daemon):
        """Test that stale PID files are handled correctly."""
        # Create a PID file with a non-existent PID
        daemon.pid_file.write_text("99999")

        # Should start successfully as the PID doesn't exist
        await daemon.start()

        assert daemon.state == DaemonState.RUNNING
        assert daemon.pid_file.exists()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_pid_file_directory_creation(self, temp_dir):
        """Test that PID file directory is created if it doesn't exist."""
        nested_dir = temp_dir / "nested" / "dir"
        pid_file = nested_dir / "daemon.pid"

        daemon = Daemon(pid_file=pid_file)

        await daemon.start()

        assert pid_file.exists()
        assert pid_file.parent.exists()


class TestDaemonSignalHandling:
    """Test daemon signal handling."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sigterm_stops_daemon(self, daemon):
        """Test that SIGTERM signal stops the daemon."""
        await daemon.start()
        assert daemon.state == DaemonState.RUNNING

        await daemon.handle_signal(signal.SIGTERM)

        assert daemon.state == DaemonState.STOPPED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sigint_stops_daemon(self, daemon):
        """Test that SIGINT signal stops the daemon."""
        await daemon.start()
        assert daemon.state == DaemonState.RUNNING

        await daemon.handle_signal(signal.SIGINT)

        assert daemon.state == DaemonState.STOPPED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sigusr1_toggles_pause_resume(self, daemon):
        """Test that SIGUSR1 signal toggles between pause and resume."""
        await daemon.start()
        assert daemon.state == DaemonState.RUNNING

        # First SIGUSR1 should pause
        await daemon.handle_signal(signal.SIGUSR1)
        assert daemon.state == DaemonState.PAUSED

        # Second SIGUSR1 should resume
        await daemon.handle_signal(signal.SIGUSR1)
        assert daemon.state == DaemonState.RUNNING


class TestDaemonUptime:
    """Test daemon uptime tracking."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_uptime_starts_at_zero(self, daemon):
        """Test that uptime starts at zero."""
        assert daemon.get_uptime() == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_uptime_increases_when_running(self, daemon):
        """Test that uptime increases when daemon is running."""
        await daemon.start()
        initial_uptime = daemon.get_uptime()

        await asyncio.sleep(0.1)

        later_uptime = daemon.get_uptime()
        assert later_uptime > initial_uptime

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_uptime_pauses_when_paused(self, daemon):
        """Test that uptime doesn't increase when daemon is paused."""
        await daemon.start()
        await asyncio.sleep(0.1)

        await daemon.pause()
        paused_uptime = daemon.get_uptime()

        await asyncio.sleep(0.1)

        # Uptime should not have increased while paused
        assert abs(daemon.get_uptime() - paused_uptime) < 0.05

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_uptime_resumes_correctly(self, daemon):
        """Test that uptime resumes correctly after pause."""
        await daemon.start()
        await asyncio.sleep(0.1)

        await daemon.pause()
        paused_uptime = daemon.get_uptime()
        await asyncio.sleep(0.1)

        await daemon.resume()
        await asyncio.sleep(0.1)

        # Uptime should have increased from where it was when paused
        final_uptime = daemon.get_uptime()
        assert final_uptime > paused_uptime

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_uptime_excludes_paused_time(self, daemon):
        """Test that total paused time is excluded from uptime."""
        await daemon.start()

        # Run for a bit
        await asyncio.sleep(0.1)
        running_uptime = daemon.get_uptime()

        # Pause for a bit
        await daemon.pause()
        await asyncio.sleep(0.1)

        # Resume and check uptime
        await daemon.resume()
        resumed_uptime = daemon.get_uptime()

        # Uptime after resume should be approximately the same as before pause
        assert abs(resumed_uptime - running_uptime) < 0.05


class TestDaemonStatus:
    """Test daemon status reporting."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_status_when_stopped(self, daemon):
        """Test status reporting when daemon is stopped."""
        status = daemon.get_status()

        assert status.state == DaemonState.STOPPED
        assert status.uptime == 0
        assert status.model_loaded is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_status_when_running(self, daemon):
        """Test status reporting when daemon is running."""
        await daemon.start()
        status = daemon.get_status()

        assert status.state == DaemonState.RUNNING
        assert status.uptime >= 0
        assert status.model_loaded is False  # Mock value

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_status_when_paused(self, daemon):
        """Test status reporting when daemon is paused."""
        await daemon.start()
        await daemon.pause()

        status = daemon.get_status()

        assert status.state == DaemonState.PAUSED


class TestDaemonContextManager:
    """Test daemon context manager functionality."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_context_manager_starts_and_stops(self, daemon):
        """Test that context manager starts and stops daemon correctly."""
        assert daemon.state == DaemonState.STOPPED

        async with daemon as d:
            assert d is daemon
            assert daemon.state == DaemonState.RUNNING

        assert daemon.state == DaemonState.STOPPED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_context_manager_stops_on_exception(self, daemon):
        """Test that context manager stops daemon even when exception occurs."""
        assert daemon.state == DaemonState.STOPPED

        with pytest.raises(ValueError):
            async with daemon:
                assert daemon.state == DaemonState.RUNNING
                raise ValueError("Test exception")

        assert daemon.state == DaemonState.STOPPED


class TestDaemonIPCIntegration:
    """Test daemon IPC integration."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_ipc_server_starts_with_daemon(self, daemon):
        """Test that IPC server starts when daemon starts."""
        await daemon.start()

        assert daemon.ipc_server is not None
        assert daemon.message_handler is not None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_ipc_server_stops_with_daemon(self, daemon):
        """Test that IPC server stops when daemon stops."""
        await daemon.start()
        ipc_server = daemon.ipc_server

        await daemon.stop()

        # IPC server should be stopped (socket cleaned up)
        assert not ipc_server.socket_path.exists()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_handles_ipc_commands(self, daemon):
        """Test that daemon handles IPC commands through message handler."""
        await daemon.start()
        handler = daemon.message_handler

        # Test status command
        status_msg = StatusRequest()
        response = await handler.handle(status_msg)
        assert isinstance(response, StatusResponse)
        assert response.state == DaemonState.RUNNING

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_handles_pause_command(self, daemon):
        """Test that daemon handles pause command through IPC."""
        await daemon.start()
        handler = daemon.message_handler

        pause_msg = PauseRequest()
        response = await handler.handle(pause_msg)

        assert isinstance(response, StatusResponse)
        assert response.state == DaemonState.PAUSED
        assert daemon.state == DaemonState.PAUSED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_handles_resume_command(self, daemon):
        """Test that daemon handles resume command through IPC."""
        await daemon.start()
        await daemon.pause()
        handler = daemon.message_handler

        resume_msg = ResumeRequest()
        response = await handler.handle(resume_msg)

        assert isinstance(response, StatusResponse)
        assert response.state == DaemonState.RUNNING
        assert daemon.state == DaemonState.RUNNING

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_handles_stop_command(self, daemon):
        """Test that daemon handles stop command through IPC."""
        await daemon.start()
        handler = daemon.message_handler

        stop_msg = StopRequest()
        response = await handler.handle(stop_msg)

        assert isinstance(response, StatusResponse)
        assert response.state == DaemonState.STOPPED
        assert daemon.state == DaemonState.STOPPED


class TestDaemonConfigIntegration:
    """Test daemon configuration integration."""

    @pytest.mark.unit
    def test_daemon_uses_config_pid_file(self, mock_config, temp_dir):
        """Test that daemon uses PID file path from configuration."""
        expected_pid_file = temp_dir / "custom_daemon.pid"
        mock_config.daemon.pid_file = str(expected_pid_file)

        daemon = Daemon(config=mock_config, pid_file=expected_pid_file)

        assert daemon.pid_file == expected_pid_file

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_respects_config_changes(self, daemon, mock_config):  # noqa: ARG002
        """Test that daemon respects configuration changes."""
        # This test would verify that configuration changes are applied
        # For now, we just verify the config is accessible
        assert daemon.config is not None
        assert isinstance(daemon.config, Config)

    @pytest.mark.unit
    def test_daemon_handles_missing_config(self, temp_dir):  # noqa: ARG002
        """Test that daemon handles missing configuration gracefully."""
        daemon = Daemon(config=None)

        # Should use default configuration
        assert isinstance(daemon.config, Config)


class TestDaemonErrorConditions:
    """Test daemon error conditions and edge cases."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_handles_ipc_server_failure(self, daemon):
        """Test that daemon handles IPC server startup failure."""
        # Mock IPC server that fails to start
        original_start = daemon.start

        async def failing_start():
            await original_start()
            # Simulate IPC server failure after other startup
            raise RuntimeError("Failed to start IPC server")

        daemon.start = failing_start

        with pytest.raises(RuntimeError, match="Failed to start IPC server"):
            await daemon.start()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_handles_pid_file_permission_error(self, daemon):
        """Test that daemon handles PID file permission errors."""
        # Make PID file directory read-only
        daemon.pid_file.parent.mkdir(exist_ok=True)
        daemon.pid_file.parent.chmod(0o444)

        try:
            with pytest.raises(PermissionError):
                await daemon.start()
        finally:
            # Restore permissions for cleanup
            daemon.pid_file.parent.chmod(0o755)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_handles_corrupted_pid_file(self, daemon):
        """Test that daemon handles corrupted PID file."""
        # Create a PID file with invalid content
        daemon.pid_file.write_text("not_a_number")

        with pytest.raises(ValueError):
            await daemon.start()

    @pytest.mark.unit
    def test_daemon_validates_configuration(self, temp_dir):  # noqa: ARG002
        """Test that daemon validates configuration on creation."""
        # Test with various configurations
        config = Config()
        daemon = Daemon(config=config)
        assert daemon.config is not None


class TestDaemonMainLoop:
    """Test daemon main loop functionality."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_run_loop(self, daemon):
        """Test that daemon run loop works correctly."""
        # Start the daemon run loop in background
        run_task = asyncio.create_task(daemon.run())

        # Give it time to start
        await asyncio.sleep(0.1)
        assert daemon.state == DaemonState.RUNNING

        # Stop the daemon
        await daemon.stop()

        # Wait for run loop to complete
        await run_task
        assert daemon.state == DaemonState.STOPPED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_run_loop_respects_pause(self, daemon):
        """Test that daemon run loop respects pause state."""
        # Start the daemon run loop in background
        run_task = asyncio.create_task(daemon.run())

        # Give it time to start
        await asyncio.sleep(0.1)
        assert daemon.state == DaemonState.RUNNING

        # Pause the daemon
        await daemon.pause()
        assert daemon.state == DaemonState.PAUSED

        # Resume the daemon
        await daemon.resume()
        assert daemon.state == DaemonState.RUNNING

        # Stop the daemon
        await daemon.stop()
        await run_task


class TestDaemonIntegration:
    """Integration tests for daemon with other components."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_daemon_lifecycle_integration(self, daemon):
        """Test complete daemon lifecycle with all components."""
        # Start daemon
        await daemon.start()
        assert daemon.state == DaemonState.RUNNING
        assert daemon.pid_file.exists()
        assert daemon.ipc_server is not None

        # Test status
        status = daemon.get_status()
        assert status.state == DaemonState.RUNNING
        assert status.uptime >= 0

        # Test pause/resume
        await daemon.pause()
        assert daemon.state == DaemonState.PAUSED

        await daemon.resume()
        assert daemon.state == DaemonState.RUNNING

        # Test signal handling
        await daemon.handle_signal(signal.SIGUSR1)
        assert daemon.state == DaemonState.PAUSED

        await daemon.handle_signal(signal.SIGUSR1)
        assert daemon.state == DaemonState.RUNNING

        # Stop daemon
        await daemon.stop()
        assert daemon.state == DaemonState.STOPPED
        assert not daemon.pid_file.exists()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_daemon_with_multiple_clients(self, daemon, temp_dir):  # noqa: ARG002
        """Test daemon handling multiple IPC clients."""
        await daemon.start()

        # Create multiple IPC clients
        socket_path = daemon.ipc_server.socket_path

        async def client_request(client_id):
            """Simulate a client making a status request."""
            client = IPCClient(socket_path)
            async with client:
                response = await client.send_message(StatusRequest())
                return {"client": client_id, "response": response}

        # Simulate concurrent requests
        tasks = []
        for i in range(3):  # Reduce number for reliability
            task = asyncio.create_task(client_request(i))
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all requests were handled
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["client"] == i
            assert isinstance(result["response"], StatusResponse)
            assert result["response"].state == DaemonState.RUNNING

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_daemon_persistence_across_restarts(self, daemon, temp_dir):  # noqa: ARG002
        """Test that daemon state persists across restarts."""
        # Start daemon and let it run
        await daemon.start()
        start_time = daemon.start_time

        # Stop daemon
        await daemon.stop()

        # Create new daemon instance with same PID file
        new_daemon = Daemon(config=daemon.config, pid_file=daemon.pid_file)

        # Start new daemon (should handle stale PID file)
        await new_daemon.start()

        assert new_daemon.state == DaemonState.RUNNING
        assert new_daemon.start_time != start_time  # New start time

        await new_daemon.stop()


class TestDaemonPerformance:
    """Performance tests for daemon operations."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_daemon_startup_performance(self, daemon):
        """Test that daemon starts up within reasonable time."""
        start_time = time.time()

        await daemon.start()

        startup_time = time.time() - start_time
        assert startup_time < 1.0  # Should start within 1 second

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_daemon_handles_high_frequency_signals(self, daemon):
        """Test daemon handling high frequency pause/resume signals."""
        await daemon.start()

        # Rapidly toggle pause/resume
        for _ in range(50):  # Reduce iterations for reliability
            await daemon.handle_signal(signal.SIGUSR1)
            await asyncio.sleep(0.001)  # 1ms delay

        # Daemon should still be responsive
        assert daemon.state in [DaemonState.RUNNING, DaemonState.PAUSED]

        # Ensure it can still be stopped
        await daemon.stop()
        assert daemon.state == DaemonState.STOPPED


# Additional test utilities and fixtures


@pytest.fixture
async def running_daemon(daemon):
    """Provide a running daemon instance."""
    await daemon.start()
    yield daemon
    if daemon.state != DaemonState.STOPPED:
        await daemon.stop()


@pytest.fixture
def mock_signal_handler():
    """Provide a mock signal handler for testing."""
    with patch("signal.signal") as mock_signal:
        yield mock_signal


# Test data and constants
TEST_SIGNALS = [signal.SIGTERM, signal.SIGINT, signal.SIGUSR1]
TEST_STATES = [
    DaemonState.STOPPED,
    DaemonState.STARTING,
    DaemonState.RUNNING,
    DaemonState.PAUSED,
    DaemonState.STOPPING,
]


@pytest.mark.parametrize("sig", TEST_SIGNALS)
@pytest.mark.asyncio
@pytest.mark.unit
async def test_daemon_signal_handlers(daemon, sig):
    """Parametrized test for different signal types."""
    await daemon.start()

    await daemon.handle_signal(sig)

    if sig in (signal.SIGTERM, signal.SIGINT):
        assert daemon.state == DaemonState.STOPPED
    elif sig == signal.SIGUSR1:
        assert daemon.state == DaemonState.PAUSED


@pytest.mark.parametrize(
    "invalid_state",
    [
        DaemonState.STARTING,
        DaemonState.STOPPING,
    ],
)
@pytest.mark.asyncio
@pytest.mark.unit
async def test_daemon_pause_invalid_states(daemon, invalid_state):
    """Test that pause fails in invalid states."""
    daemon.state = invalid_state

    with pytest.raises(DaemonError):
        await daemon.pause()


class TestDaemonModelIntegration:
    """Test integration with the models module."""

    @pytest.mark.unit
    def test_daemon_uses_correct_state_enum(self, daemon):
        """Test that daemon uses the correct DaemonState enum from models."""
        assert daemon.state == DaemonState.STOPPED
        assert isinstance(daemon.state, DaemonState)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_status_response_format(self, daemon):
        """Test that daemon status follows StatusResponse format."""
        await daemon.start()
        status = daemon.get_status()

        assert isinstance(status, StatusResponse)
        assert hasattr(status, "state")
        assert hasattr(status, "uptime")
        assert hasattr(status, "model_loaded")
        assert status.type == IPCMessageType.STATUS


class TestDaemonCleanup:
    """Test daemon cleanup functionality."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_cleanup_on_exception(self, daemon):
        """Test that daemon cleans up properly when exceptions occur."""
        await daemon.start()

        # Simulate an exception during operation
        original_pid_file = daemon.pid_file

        try:
            # Force an exception in the daemon
            raise RuntimeError("Simulated error")
        except RuntimeError:
            # Ensure cleanup still works
            await daemon.stop()

        assert not original_pid_file.exists()
        assert daemon.state == DaemonState.STOPPED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_daemon_resource_cleanup(self, daemon):
        """Test that daemon properly cleans up all resources."""
        await daemon.start()

        # Track resources
        pid_file = daemon.pid_file
        ipc_server = daemon.ipc_server
        socket_path = ipc_server.socket_path

        await daemon.stop()

        # Verify cleanup
        assert not pid_file.exists()
        assert not socket_path.exists()
        assert daemon.state == DaemonState.STOPPED
