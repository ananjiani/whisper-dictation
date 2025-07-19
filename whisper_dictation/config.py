"""Configuration management for whisper_dictation."""

import importlib.util
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AudioConfig:
    """Audio configuration settings."""

    device: str = "default"
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024


@dataclass
class ModelConfig:
    """Model configuration settings."""

    name: str = "base"
    device: str = "auto"
    compute_type: str = "default"
    use_vad: bool = True
    vad_threshold: float = 0.5


@dataclass
class OutputConfig:
    """Output configuration settings."""

    method: str = "ydotool"
    prefix: str = ""
    suffix: str = ""
    use_clipboard: bool = False


@dataclass
class DaemonConfig:
    """Daemon configuration settings."""

    socket_path: str | None = None
    pid_file: str | None = None
    log_level: str = "INFO"
    max_session_time: float = 300.0


@dataclass
class Config:
    """Main configuration class."""

    audio: AudioConfig | None = field(default=None)
    model: ModelConfig | None = field(default=None)
    output: OutputConfig | None = field(default=None)
    daemon: DaemonConfig | None = field(default=None)

    def __post_init__(self) -> None:
        """Initialize default sub-configs if not provided."""
        if self.audio is None:
            self.audio = AudioConfig()
        if self.model is None:
            self.model = ModelConfig()
        if self.output is None:
            self.output = OutputConfig()
        if self.daemon is None:
            self.daemon = DaemonConfig()

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        # After __post_init__, these are guaranteed to be non-None
        assert self.audio is not None
        assert self.model is not None
        assert self.output is not None
        assert self.daemon is not None

        return {
            "audio": asdict(self.audio),
            "model": asdict(self.model),
            "output": asdict(self.output),
            "daemon": asdict(self.daemon),
        }

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        audio_data = config_dict.get("audio", {})
        model_data = config_dict.get("model", {})
        output_data = config_dict.get("output", {})
        daemon_data = config_dict.get("daemon", {})

        return cls(
            audio=AudioConfig(**audio_data),
            model=ModelConfig(**model_data),
            output=OutputConfig(**output_data),
            daemon=DaemonConfig(**daemon_data),
        )


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    if "XDG_CONFIG_HOME" in os.environ:
        config_dir = Path(os.environ["XDG_CONFIG_HOME"])
    else:
        config_dir = Path.home() / ".config"

    return config_dir / "whisper-dictation"


def get_data_dir() -> Path:
    """Get the data directory path."""
    if "XDG_DATA_HOME" in os.environ:
        data_dir = Path(os.environ["XDG_DATA_HOME"])
    else:
        data_dir = Path.home() / ".local" / "share"

    return data_dir / "whisper-dictation"


def get_config_path() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.py"


def get_socket_path() -> Path:
    """Get the daemon socket path."""
    return get_data_dir() / "daemon.sock"


def get_pid_file_path() -> Path:
    """Get the daemon PID file path."""
    return get_data_dir() / "daemon.pid"


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file or return default."""
    if config_path is None:
        config_path = get_config_path()

    if not config_path.exists():
        logger.debug(f"Config file not found: {config_path}")
        return Config()

    try:
        # Load the config file as a module
        spec = importlib.util.spec_from_file_location("user_config", config_path)
        if spec is None or spec.loader is None:
            logger.warning(f"Cannot load config from {config_path}")
            return Config()

        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)

        # Look for get_config function
        if not hasattr(config_module, "get_config"):
            logger.warning(f"Config file {config_path} missing get_config() function")
            return Config()

        # Call get_config function
        config_dict = config_module.get_config()
        if not isinstance(config_dict, dict):
            logger.warning(
                f"get_config() must return a dictionary, got {type(config_dict)}"
            )
            return Config()

        return Config.from_dict(config_dict)

    except Exception as e:
        logger.warning(f"Error loading config from {config_path}: {e}")
        return Config()
