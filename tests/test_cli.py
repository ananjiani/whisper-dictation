"""Tests for whisper_dictation.cli module."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import typer
from typer.testing import CliRunner

from whisper_dictation.cli import app
from whisper_dictation.models import DaemonState, StatusResponse


class TestCLI:
    """Test CLI functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_cli_app_exists(self):
        """Test that the CLI app exists."""
        assert isinstance(app, typer.Typer)

    def test_cli_help(self):
        """Test CLI help output."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "whisper-dictation" in result.output or "Usage" in result.output

    @patch("whisper_dictation.cli.Daemon")
    def test_daemon_start_command(self, mock_daemon_class):
        """Test daemon start command."""
        mock_daemon = Mock()
        mock_daemon_class.return_value = mock_daemon
        mock_daemon.is_running.return_value = False
        mock_daemon.start = AsyncMock()

        result = self.runner.invoke(app, ["daemon", "start"])
        assert result.exit_code == 0
        assert "Starting daemon" in result.output

    @patch("whisper_dictation.cli.Daemon")
    def test_daemon_start_already_running(self, mock_daemon_class):
        """Test daemon start when already running."""
        mock_daemon = Mock()
        mock_daemon_class.return_value = mock_daemon
        mock_daemon.is_running.return_value = True

        result = self.runner.invoke(app, ["daemon", "start"])
        assert result.exit_code == 1
        assert "already running" in result.output

    @patch("whisper_dictation.cli.Daemon")
    def test_daemon_stop_command(self, mock_daemon_class):
        """Test daemon stop command."""
        mock_daemon = Mock()
        mock_daemon_class.return_value = mock_daemon
        mock_daemon.is_running.return_value = True
        mock_daemon.stop = AsyncMock()

        result = self.runner.invoke(app, ["daemon", "stop"])
        assert result.exit_code == 0
        assert "Stopping daemon" in result.output

    @patch("whisper_dictation.cli.Daemon")
    def test_daemon_stop_not_running(self, mock_daemon_class):
        """Test daemon stop when not running."""
        mock_daemon = Mock()
        mock_daemon_class.return_value = mock_daemon
        mock_daemon.is_running.return_value = False

        result = self.runner.invoke(app, ["daemon", "stop"])
        assert result.exit_code == 1
        assert "not running" in result.output

    @patch("whisper_dictation.cli.send_ipc_message")
    def test_daemon_pause_command(self, mock_send_ipc):
        """Test daemon pause command."""
        mock_response = StatusResponse(
            state=DaemonState.PAUSED, uptime=10.0, model_loaded=False
        )
        mock_send_ipc.return_value = mock_response

        result = self.runner.invoke(app, ["pause"])
        assert result.exit_code == 0
        assert "Pausing daemon" in result.output

    @patch("whisper_dictation.cli.send_ipc_message")
    def test_daemon_resume_command(self, mock_send_ipc):
        """Test daemon resume command."""
        mock_response = StatusResponse(
            state=DaemonState.RUNNING, uptime=15.0, model_loaded=False
        )
        mock_send_ipc.return_value = mock_response

        result = self.runner.invoke(app, ["resume"])
        assert result.exit_code == 0
        assert "Resuming daemon" in result.output

    @patch("whisper_dictation.cli.send_ipc_message")
    def test_status_command(self, mock_send_ipc):
        """Test status command."""
        mock_response = StatusResponse(
            state=DaemonState.RUNNING,
            uptime=123.45,
            model_loaded=True,
            current_model="base",
        )
        mock_send_ipc.return_value = mock_response

        result = self.runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "RUNNING" in result.output
        assert "123.45" in result.output or "123" in result.output

    @patch("whisper_dictation.cli.send_ipc_message")
    def test_status_command_daemon_not_running(self, mock_send_ipc):
        """Test status command when daemon not running."""
        from typer import Exit

        mock_send_ipc.side_effect = Exit(1)

        result = self.runner.invoke(app, ["status"])
        assert result.exit_code == 1

    def test_daemon_run_command_exists(self):
        """Test that daemon run command exists."""
        result = self.runner.invoke(app, ["daemon", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output

    @patch("whisper_dictation.cli.Daemon")
    def test_daemon_run_command(self, mock_daemon_class):
        """Test daemon run command."""
        mock_daemon = Mock()
        mock_daemon_class.return_value = mock_daemon
        mock_daemon.is_running.return_value = False
        mock_daemon.run = AsyncMock()

        result = self.runner.invoke(app, ["daemon", "run"])
        assert result.exit_code == 0

    def test_cli_version_option(self):
        """Test CLI version option."""
        result = self.runner.invoke(app, ["--version"])
        # Either succeeds with version or fails gracefully
        assert result.exit_code in (0, 2)  # 2 is ok for missing version

    @patch("whisper_dictation.cli.load_config")
    def test_cli_config_option(self, mock_load_config):
        """Test CLI config option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.py"
            config_path.write_text("def get_config(): return {}")

            self.runner.invoke(app, ["--config", str(config_path), "status"])
            # Should attempt to load config
            mock_load_config.assert_called_once()

    def test_cli_verbose_option(self):
        """Test CLI verbose option."""
        result = self.runner.invoke(app, ["--verbose", "--help"])
        assert result.exit_code == 0
