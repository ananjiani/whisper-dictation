"""Tests for whisper_dictation.config module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from whisper_dictation.config import (
    AudioConfig,
    Config,
    DaemonConfig,
    ModelConfig,
    OutputConfig,
    get_config_path,
    get_pid_file_path,
    get_socket_path,
    load_config,
)


class TestAudioConfig:
    """Test AudioConfig class."""

    def test_audio_config_defaults(self):
        """Test AudioConfig with default values."""
        config = AudioConfig()
        assert config.device == "default"
        assert config.sample_rate == 16000
        assert config.channels == 1
        assert config.chunk_size == 1024

    def test_audio_config_custom_values(self):
        """Test AudioConfig with custom values."""
        config = AudioConfig(
            device="hw:1,0", sample_rate=44100, channels=2, chunk_size=2048
        )
        assert config.device == "hw:1,0"
        assert config.sample_rate == 44100
        assert config.channels == 2
        assert config.chunk_size == 2048


class TestModelConfig:
    """Test ModelConfig class."""

    def test_model_config_defaults(self):
        """Test ModelConfig with default values."""
        config = ModelConfig()
        assert config.name == "base"
        assert config.device == "auto"
        assert config.compute_type == "default"
        assert config.use_vad is True
        assert config.vad_threshold == 0.5

    def test_model_config_custom_values(self):
        """Test ModelConfig with custom values."""
        config = ModelConfig(
            name="large-v3",
            device="cuda",
            compute_type="float16",
            use_vad=False,
            vad_threshold=0.7,
        )
        assert config.name == "large-v3"
        assert config.device == "cuda"
        assert config.compute_type == "float16"
        assert config.use_vad is False
        assert config.vad_threshold == 0.7


class TestOutputConfig:
    """Test OutputConfig class."""

    def test_output_config_defaults(self):
        """Test OutputConfig with default values."""
        config = OutputConfig()
        assert config.method == "ydotool"
        assert config.prefix == ""
        assert config.suffix == ""
        assert config.use_clipboard is False

    def test_output_config_custom_values(self):
        """Test OutputConfig with custom values."""
        config = OutputConfig(
            method="stdout", prefix="[SPEECH] ", suffix=" [END]", use_clipboard=True
        )
        assert config.method == "stdout"
        assert config.prefix == "[SPEECH] "
        assert config.suffix == " [END]"
        assert config.use_clipboard is True


class TestDaemonConfig:
    """Test DaemonConfig class."""

    def test_daemon_config_defaults(self):
        """Test DaemonConfig with default values."""
        config = DaemonConfig()
        assert config.socket_path is None
        assert config.pid_file is None
        assert config.log_level == "INFO"
        assert config.max_session_time == 300.0

    def test_daemon_config_custom_values(self):
        """Test DaemonConfig with custom values."""
        config = DaemonConfig(
            socket_path="/tmp/custom.sock",
            pid_file="/tmp/custom.pid",
            log_level="DEBUG",
            max_session_time=600.0,
        )
        assert config.socket_path == "/tmp/custom.sock"
        assert config.pid_file == "/tmp/custom.pid"
        assert config.log_level == "DEBUG"
        assert config.max_session_time == 600.0


class TestConfig:
    """Test main Config class."""

    def test_config_defaults(self):
        """Test Config with default values."""
        config = Config()
        assert isinstance(config.audio, AudioConfig)
        assert isinstance(config.model, ModelConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.daemon, DaemonConfig)

    def test_config_custom_sections(self):
        """Test Config with custom section configs."""
        audio = AudioConfig(device="hw:2,0")
        model = ModelConfig(name="large")
        output = OutputConfig(method="stdout")
        daemon = DaemonConfig(log_level="DEBUG")

        config = Config(audio=audio, model=model, output=output, daemon=daemon)

        assert config.audio.device == "hw:2,0"
        assert config.model.name == "large"
        assert config.output.method == "stdout"
        assert config.daemon.log_level == "DEBUG"

    def test_config_to_dict(self):
        """Test converting Config to dictionary."""
        config = Config()
        config_dict = config.to_dict()

        assert "audio" in config_dict
        assert "model" in config_dict
        assert "output" in config_dict
        assert "daemon" in config_dict

        assert config_dict["audio"]["device"] == "default"
        assert config_dict["model"]["name"] == "base"
        assert config_dict["output"]["method"] == "ydotool"
        assert config_dict["daemon"]["log_level"] == "INFO"

    def test_config_from_dict(self):
        """Test creating Config from dictionary."""
        config_dict = {
            "audio": {"device": "hw:1,0", "sample_rate": 44100},
            "model": {"name": "large", "device": "cuda"},
            "output": {"method": "stdout", "prefix": "[SPEECH] "},
            "daemon": {"log_level": "DEBUG", "max_session_time": 600.0},
        }

        config = Config.from_dict(config_dict)

        assert config.audio.device == "hw:1,0"
        assert config.audio.sample_rate == 44100
        assert config.model.name == "large"
        assert config.model.device == "cuda"
        assert config.output.method == "stdout"
        assert config.output.prefix == "[SPEECH] "
        assert config.daemon.log_level == "DEBUG"
        assert config.daemon.max_session_time == 600.0

    def test_config_from_dict_partial(self):
        """Test creating Config from partial dictionary."""
        config_dict = {"audio": {"device": "hw:1,0"}, "model": {"name": "large"}}

        config = Config.from_dict(config_dict)

        # Custom values
        assert config.audio.device == "hw:1,0"
        assert config.model.name == "large"

        # Default values for other fields
        assert config.audio.sample_rate == 16000  # default
        assert config.model.device == "auto"  # default
        assert config.output.method == "ydotool"  # default
        assert config.daemon.log_level == "INFO"  # default


class TestConfigFunctions:
    """Test module-level configuration functions."""

    def test_get_config_path_default(self):
        """Test getting default config path."""
        with patch.dict(os.environ, {"HOME": "/home/user"}, clear=True):
            path = get_config_path()
            expected = Path("/home/user/.config/whisper-dictation/config.py")
            assert path == expected

    def test_get_config_path_xdg_config_home(self):
        """Test getting config path with XDG_CONFIG_HOME."""
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}, clear=True):
            path = get_config_path()
            expected = Path("/custom/config/whisper-dictation/config.py")
            assert path == expected

    def test_get_socket_path_default(self):
        """Test getting default socket path."""
        with patch.dict(os.environ, {"HOME": "/home/user"}, clear=True):
            path = get_socket_path()
            expected = Path("/home/user/.local/share/whisper-dictation/daemon.sock")
            assert path == expected

    def test_get_socket_path_xdg_data_home(self):
        """Test getting socket path with XDG_DATA_HOME."""
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/custom/data"}, clear=True):
            path = get_socket_path()
            expected = Path("/custom/data/whisper-dictation/daemon.sock")
            assert path == expected

    def test_get_pid_file_path_default(self):
        """Test getting default PID file path."""
        with patch.dict(os.environ, {"HOME": "/home/user"}, clear=True):
            path = get_pid_file_path()
            expected = Path("/home/user/.local/share/whisper-dictation/daemon.pid")
            assert path == expected

    def test_get_pid_file_path_xdg_data_home(self):
        """Test getting PID file path with XDG_DATA_HOME."""
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/custom/data"}, clear=True):
            path = get_pid_file_path()
            expected = Path("/custom/data/whisper-dictation/daemon.pid")
            assert path == expected

    def test_load_config_no_file(self):
        """Test loading config when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.py"
            config = load_config(config_path)

            # Should return default config
            assert isinstance(config, Config)
            assert config.audio.device == "default"
            assert config.model.name == "base"

    def test_load_config_with_file(self):
        """Test loading config from file."""
        config_content = '''
def get_config():
    """Return configuration dictionary."""
    return {
        "audio": {
            "device": "hw:1,0",
            "sample_rate": 44100
        },
        "model": {
            "name": "large",
            "device": "cuda"
        },
        "output": {
            "method": "stdout",
            "prefix": "[DICTATION] "
        },
        "daemon": {
            "log_level": "DEBUG"
        }
    }
'''

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.py"
            config_path.write_text(config_content)

            config = load_config(config_path)

            assert config.audio.device == "hw:1,0"
            assert config.audio.sample_rate == 44100
            assert config.model.name == "large"
            assert config.model.device == "cuda"
            assert config.output.method == "stdout"
            assert config.output.prefix == "[DICTATION] "
            assert config.daemon.log_level == "DEBUG"

    def test_load_config_invalid_file(self):
        """Test loading config from invalid Python file."""
        config_content = """
# Invalid Python syntax
def get_config(
    return {}
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.py"
            config_path.write_text(config_content)

            # Should return default config on error
            config = load_config(config_path)
            assert isinstance(config, Config)
            assert config.audio.device == "default"

    def test_load_config_no_get_config_function(self):
        """Test loading config from file without get_config function."""
        config_content = """
# Valid Python but no get_config function
some_variable = "value"
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.py"
            config_path.write_text(config_content)

            # Should return default config when get_config function is missing
            config = load_config(config_path)
            assert isinstance(config, Config)
            assert config.audio.device == "default"
