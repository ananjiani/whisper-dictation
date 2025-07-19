"""CLI interface for whisper_dictation using Typer."""

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import Config, get_socket_path, load_config
from .daemon import Daemon
from .ipc import IPCClient
from .models import (
    ErrorResponse,
    IPCMessage,
    PauseRequest,
    ResumeRequest,
    StatusRequest,
    StatusResponse,
)

# Create the main app
app = typer.Typer(
    name="whisper-dictation",
    help="Voice dictation tool using faster-whisper",
    add_completion=False,
)

# Create daemon subcommand
daemon_app = typer.Typer(
    name="daemon",
    help="Daemon management commands",
)
app.add_typer(daemon_app, name="daemon")

console = Console()
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"whisper-dictation {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    config_path: Path | None = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
    _version: bool | None = typer.Option(
        None, "--version", callback=version_callback, help="Show version and exit"
    ),
) -> None:
    """Voice dictation tool using faster-whisper."""
    setup_logging(verbose)

    # Store config in app state for other commands
    config = load_config(config_path) if config_path else load_config()

    # Store in global state
    global _current_config
    _current_config = config


# Global config storage
_current_config: Config | None = None


def get_config() -> Config:
    """Get config from global state."""
    global _current_config
    return _current_config or Config()


@daemon_app.command("start")
def daemon_start() -> None:
    """Start the daemon."""
    config = get_config()
    daemon = Daemon(config)

    if daemon.is_running():
        console.print("[red]Daemon is already running[/red]")
        raise typer.Exit(1) from None

    console.print("Starting daemon...")
    try:
        asyncio.run(daemon.start())
        console.print("[green]Daemon started successfully[/green]")
    except Exception as e:
        console.print(f"[red]Failed to start daemon: {e}[/red]")
        raise typer.Exit(1) from None


@daemon_app.command("stop")
def daemon_stop() -> None:
    """Stop the daemon."""
    config = get_config()
    daemon = Daemon(config)

    if not daemon.is_running():
        console.print("[yellow]Daemon is not running[/yellow]")
        raise typer.Exit(1) from None

    console.print("Stopping daemon...")
    try:
        asyncio.run(daemon.stop())
        console.print("[green]Daemon stopped successfully[/green]")
    except Exception as e:
        console.print(f"[red]Failed to stop daemon: {e}[/red]")
        raise typer.Exit(1) from None


@daemon_app.command("run")
def daemon_run() -> None:
    """Run the daemon in foreground."""
    config = get_config()
    daemon = Daemon(config)

    if daemon.is_running():
        console.print("[red]Daemon is already running[/red]")
        raise typer.Exit(1) from None

    console.print("Running daemon in foreground...")
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon interrupted[/yellow]")
    except Exception as e:
        console.print(f"[red]Daemon error: {e}[/red]")
        raise typer.Exit(1) from None


async def send_ipc_message(message: IPCMessage) -> IPCMessage:
    """Send IPC message to daemon."""
    config = get_config()
    # After Config.__post_init__, daemon is guaranteed to be non-None
    assert config.daemon is not None
    socket_path = Path(config.daemon.socket_path or get_socket_path())

    try:
        async with IPCClient(socket_path) as client:
            response = await client.send_message(message)
            return response
    except ConnectionError:
        console.print("[red]Cannot connect to daemon. Is it running?[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]IPC error: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("pause")
def pause() -> None:
    """Pause the daemon."""
    console.print("Pausing daemon...")
    try:
        response = asyncio.run(send_ipc_message(PauseRequest()))
        if isinstance(response, ErrorResponse):
            console.print(f"[red]Failed to pause: {response.message}[/red]")
            raise typer.Exit(1) from None
        else:
            console.print("[green]Daemon paused[/green]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Failed to pause daemon: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("resume")
def resume() -> None:
    """Resume the daemon."""
    console.print("Resuming daemon...")
    try:
        response = asyncio.run(send_ipc_message(ResumeRequest()))
        if isinstance(response, ErrorResponse):
            console.print(f"[red]Failed to resume: {response.message}[/red]")
            raise typer.Exit(1) from None
        else:
            console.print("[green]Daemon resumed[/green]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Failed to resume daemon: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("status")
def status() -> None:
    """Show daemon status."""
    try:
        response = asyncio.run(send_ipc_message(StatusRequest()))

        if isinstance(response, ErrorResponse):
            console.print(f"[red]Error getting status: {response.message}[/red]")
            raise typer.Exit(1) from None

        if isinstance(response, StatusResponse):
            # Create a status table
            table = Table(title="Daemon Status")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("State", response.state.value.upper())
            table.add_row("Uptime", f"{response.uptime:.2f} seconds")
            table.add_row("Model Loaded", "Yes" if response.model_loaded else "No")

            if hasattr(response, "current_model") and response.current_model:
                table.add_row("Current Model", response.current_model)

            if hasattr(response, "error_message") and response.error_message:
                table.add_row("Error", response.error_message)

            console.print(table)
        else:
            console.print("[yellow]Received unexpected response type[/yellow]")

    except typer.Exit:
        raise
    except ConnectionError:
        console.print("[red]Daemon is not running[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Failed to get status: {e}[/red]")
        raise typer.Exit(1) from None


# Alias functions for test compatibility
daemon_command = daemon_app
status_command = status


if __name__ == "__main__":
    app()
