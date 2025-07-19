"""Tests for whisper_dictation.ipc module."""

import json
import tempfile
from pathlib import Path

import pytest

from whisper_dictation.ipc import (
    IPCClient,
    IPCServer,
    MessageHandler,
    deserialize_message,
    serialize_message,
)
from whisper_dictation.models import (
    DaemonState,
    ErrorResponse,
    IPCMessageType,
    StartRequest,
    StatusRequest,
    StatusResponse,
)


class TestMessageSerialization:
    """Test message serialization and deserialization."""

    def test_serialize_start_request(self):
        """Test serializing a StartRequest."""
        req = StartRequest()
        data = serialize_message(req)
        parsed = json.loads(data)

        assert parsed["type"] == "start"
        assert parsed["data"] is None

    def test_serialize_start_request_with_config(self):
        """Test serializing StartRequest with config."""
        config = {"model": "base", "device": "auto"}
        req = StartRequest(config=config)
        data = serialize_message(req)
        parsed = json.loads(data)

        assert parsed["type"] == "start"
        assert parsed["data"]["config"] == config

    def test_serialize_status_response(self):
        """Test serializing a StatusResponse."""
        resp = StatusResponse(
            state=DaemonState.RUNNING,
            uptime=123.45,
            model_loaded=True,
            current_model="base",
        )
        data = serialize_message(resp)
        parsed = json.loads(data)

        assert parsed["type"] == "status"
        assert parsed["data"]["state"] == "running"
        assert parsed["data"]["uptime"] == 123.45
        assert parsed["data"]["model_loaded"] is True
        assert parsed["data"]["current_model"] == "base"

    def test_deserialize_start_request(self):
        """Test deserializing a StartRequest."""
        data = json.dumps({"type": "start", "data": {"config": {"model": "base"}}})

        msg = deserialize_message(data)
        assert msg.type == IPCMessageType.START
        assert msg.data["config"]["model"] == "base"

    def test_deserialize_status_request(self):
        """Test deserializing a StatusRequest."""
        data = json.dumps({"type": "status", "data": None})

        msg = deserialize_message(data)
        assert msg.type == IPCMessageType.STATUS
        assert msg.data is None

    def test_deserialize_invalid_json(self):
        """Test deserializing invalid JSON."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            deserialize_message("invalid json")

    def test_deserialize_missing_type(self):
        """Test deserializing message without type."""
        data = json.dumps({"data": None})

        with pytest.raises(ValueError, match="Missing required field: type"):
            deserialize_message(data)

    def test_deserialize_invalid_type(self):
        """Test deserializing message with invalid type."""
        data = json.dumps({"type": "invalid", "data": None})

        with pytest.raises(ValueError, match="Invalid message type"):
            deserialize_message(data)


class TestMessageHandler:
    """Test MessageHandler class."""

    def test_message_handler_creation(self):
        """Test creating a MessageHandler."""
        handler = MessageHandler()
        assert isinstance(handler, MessageHandler)

    @pytest.mark.asyncio
    async def test_handle_start_request(self):
        """Test handling a StartRequest."""
        handler = MessageHandler()
        req = StartRequest()

        response = await handler.handle(req)
        assert isinstance(response, ErrorResponse)
        assert "not implemented" in response.message.lower()

    @pytest.mark.asyncio
    async def test_handle_status_request(self):
        """Test handling a StatusRequest."""
        handler = MessageHandler()
        req = StatusRequest()

        response = await handler.handle(req)
        assert isinstance(response, StatusResponse)
        assert response.state == DaemonState.STOPPED


class TestIPCServer:
    """Test IPCServer class."""

    def test_ipc_server_creation(self):
        """Test creating an IPCServer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            handler = MessageHandler()
            server = IPCServer(socket_path, handler)

            assert server.socket_path == socket_path
            assert server.handler is handler
            assert server.server is None

    @pytest.mark.asyncio
    async def test_ipc_server_start_stop(self):
        """Test starting and stopping the IPC server."""
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            handler = MessageHandler()
            server = IPCServer(socket_path, handler)

            # Start server
            await server.start()
            assert server.server is not None
            assert socket_path.exists()

            # Stop server
            await server.stop()
            assert server.server is None

    @pytest.mark.asyncio
    async def test_ipc_server_context_manager(self):
        """Test using IPCServer as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            handler = MessageHandler()

            async with IPCServer(socket_path, handler) as server:
                assert server.server is not None
                assert socket_path.exists()

            assert server.server is None


class TestIPCClient:
    """Test IPCClient class."""

    def test_ipc_client_creation(self):
        """Test creating an IPCClient."""
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            client = IPCClient(socket_path)

            assert client.socket_path == socket_path

    @pytest.mark.asyncio
    async def test_ipc_client_send_message(self):
        """Test sending a message through IPCClient."""
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            handler = MessageHandler()

            # Start server
            async with IPCServer(socket_path, handler):
                client = IPCClient(socket_path)

                # Send status request
                req = StatusRequest()
                response = await client.send_message(req)

                assert isinstance(response, StatusResponse)
                assert response.state == DaemonState.STOPPED

    @pytest.mark.asyncio
    async def test_ipc_client_connection_error(self):
        """Test IPCClient connection error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "nonexistent.sock"
            client = IPCClient(socket_path)

            req = StatusRequest()
            with pytest.raises(ConnectionError):
                await client.send_message(req)

    @pytest.mark.asyncio
    async def test_ipc_client_context_manager(self):
        """Test using IPCClient as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = Path(tmpdir) / "test.sock"
            handler = MessageHandler()

            async with (
                IPCServer(socket_path, handler),
                IPCClient(socket_path) as client,
            ):
                req = StatusRequest()
                response = await client.send_message(req)
                assert isinstance(response, StatusResponse)
