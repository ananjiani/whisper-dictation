"""IPC communication layer for whisper_dictation daemon."""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .models import (
    DaemonState,
    ErrorResponse,
    IPCMessage,
    IPCMessageType,
    StatusResponse,
)

logger = logging.getLogger(__name__)


def serialize_message(message: IPCMessage) -> str:
    """Serialize an IPC message to JSON string."""

    def json_encoder(obj: Any) -> Any:
        """Custom JSON encoder for enum types."""
        if hasattr(obj, "value"):  # Enum type
            return obj.value
        raise TypeError(
            f"Object of type {obj.__class__.__name__} is not JSON serializable"
        )

    data = {
        "type": message.type.value,
        "data": message.data,
    }
    return json.dumps(data, default=json_encoder)


def deserialize_message(data: str) -> IPCMessage:
    """Deserialize JSON string to IPC message."""
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    if "type" not in parsed:
        raise ValueError("Missing required field: type")

    try:
        msg_type = IPCMessageType(parsed["type"])
    except ValueError as e:
        raise ValueError(f"Invalid message type: {parsed['type']}") from e

    message_data = parsed.get("data")

    # Reconstruct specific message types based on type and data structure
    if msg_type == IPCMessageType.STATUS and message_data and "state" in message_data:
        # This is a StatusResponse
        from .models import DaemonState, StatusResponse

        try:
            state = DaemonState(message_data["state"])
            return StatusResponse(
                state=state,
                uptime=message_data["uptime"],
                model_loaded=message_data["model_loaded"],
                current_model=message_data.get("current_model"),
                error_message=message_data.get("error_message"),
            )
        except (KeyError, ValueError):
            pass  # Fall back to generic IPCMessage

    elif msg_type == IPCMessageType.ERROR and message_data:
        # This is an ErrorResponse
        from .models import ErrorResponse

        try:
            return ErrorResponse(
                message=message_data["message"],
                code=message_data.get("code", 1),
            )
        except KeyError:
            pass  # Fall back to generic IPCMessage

    # For all other cases or when reconstruction fails, return generic IPCMessage
    return IPCMessage(type=msg_type, data=message_data)


class MessageHandler:
    """Handles incoming IPC messages."""

    def __init__(self) -> None:
        """Initialize the message handler."""
        self._handlers: dict[
            IPCMessageType, Callable[[IPCMessage], Awaitable[IPCMessage]]
        ] = {
            IPCMessageType.START: self._handle_start,
            IPCMessageType.STOP: self._handle_stop,
            IPCMessageType.PAUSE: self._handle_pause,
            IPCMessageType.RESUME: self._handle_resume,
            IPCMessageType.STATUS: self._handle_status,
        }

    async def handle(self, message: IPCMessage) -> IPCMessage:
        """Handle an IPC message and return a response."""
        handler = self._handlers.get(message.type)
        if handler is None:
            return ErrorResponse(f"Unknown message type: {message.type.value}")

        try:
            return await handler(message)
        except Exception as e:
            logger.exception("Error handling message")
            return ErrorResponse(f"Handler error: {e}")

    async def _handle_start(self, message: IPCMessage) -> IPCMessage:  # noqa: ARG002
        """Handle start request."""
        return ErrorResponse("Start handler not implemented", 501)

    async def _handle_stop(self, message: IPCMessage) -> IPCMessage:  # noqa: ARG002
        """Handle stop request."""
        return ErrorResponse("Stop handler not implemented", 501)

    async def _handle_pause(self, message: IPCMessage) -> IPCMessage:  # noqa: ARG002
        """Handle pause request."""
        return ErrorResponse("Pause handler not implemented", 501)

    async def _handle_resume(self, message: IPCMessage) -> IPCMessage:  # noqa: ARG002
        """Handle resume request."""
        return ErrorResponse("Resume handler not implemented", 501)

    async def _handle_status(self, message: IPCMessage) -> IPCMessage:  # noqa: ARG002
        """Handle status request."""
        return StatusResponse(
            state=DaemonState.STOPPED,
            uptime=0.0,
            model_loaded=False,
        )


class IPCServer:
    """Unix socket server for IPC communication."""

    def __init__(self, socket_path: Path, handler: MessageHandler) -> None:
        """Initialize the IPC server."""
        self.socket_path = socket_path
        self.handler = handler
        self.server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the IPC server."""
        # Remove existing socket file if it exists
        if self.socket_path.exists():
            self.socket_path.unlink()

        # Ensure parent directory exists
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)

        self.server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_path)
        )
        logger.info(f"IPC server started on {self.socket_path}")

    async def stop(self) -> None:
        """Stop the IPC server."""
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

        # Clean up socket file
        if self.socket_path.exists():
            self.socket_path.unlink()

        logger.info("IPC server stopped")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a client connection."""
        try:
            # Read message length (4 bytes, big endian)
            length_data = await reader.readexactly(4)
            message_length = int.from_bytes(length_data, "big")

            # Read message data
            message_data = await reader.readexactly(message_length)
            message_str = message_data.decode("utf-8")

            # Deserialize and handle message
            try:
                message = deserialize_message(message_str)
                response = await self.handler.handle(message)
            except Exception as e:
                logger.exception("Error processing message")
                response = ErrorResponse(f"Message processing error: {e}")

            # Serialize and send response
            response_str = serialize_message(response)
            response_data = response_str.encode("utf-8")
            response_length = len(response_data)

            writer.write(response_length.to_bytes(4, "big"))
            writer.write(response_data)
            await writer.drain()

        except asyncio.IncompleteReadError:
            logger.debug("Client disconnected")
        except Exception:
            logger.exception("Error handling client")
        finally:
            writer.close()
            await writer.wait_closed()

    async def __aenter__(self) -> "IPCServer":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.stop()


class IPCClient:
    """Unix socket client for IPC communication."""

    def __init__(self, socket_path: Path) -> None:
        """Initialize the IPC client."""
        self.socket_path = socket_path
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def _connect(self) -> None:
        """Connect to the IPC server."""
        try:
            self._reader, self._writer = await asyncio.open_unix_connection(
                path=str(self.socket_path)
            )
        except (FileNotFoundError, ConnectionRefusedError, OSError) as e:
            raise ConnectionError(f"Cannot connect to daemon: {e}") from e

    async def _disconnect(self) -> None:
        """Disconnect from the IPC server."""
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

    async def send_message(self, message: IPCMessage) -> IPCMessage:
        """Send a message and return the response."""
        if self._reader is None or self._writer is None:
            await self._connect()

        # Check again after connection attempt
        if self._reader is None or self._writer is None:
            raise ConnectionError("Failed to establish connection")

        # Serialize message
        message_str = serialize_message(message)
        message_data = message_str.encode("utf-8")
        message_length = len(message_data)

        # Send message
        self._writer.write(message_length.to_bytes(4, "big"))
        self._writer.write(message_data)
        await self._writer.drain()

        # Read response length
        length_data = await self._reader.readexactly(4)
        response_length = int.from_bytes(length_data, "big")

        # Read response data
        response_data = await self._reader.readexactly(response_length)
        response_str = response_data.decode("utf-8")

        # Deserialize response
        return deserialize_message(response_str)

    async def __aenter__(self) -> "IPCClient":
        """Async context manager entry."""
        await self._connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._disconnect()
