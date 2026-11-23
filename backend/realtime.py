import asyncio
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .auth import COOKIE, authenticated_user, public_user, token_digest
from .comments import board_snapshot

router = APIRouter()


class Hub:
    """Single-process connection registry. Durable state always comes from SQL."""

    def __init__(self):
        self.connections = {}

    def members(self):
        by_user = {item[0].id: public_user(item[0]) for item in self.connections.values()}
        return sorted(by_user.values(), key=lambda u: u["id"])

    async def broadcast(self, message):
        sockets = list(self.connections)
        if not sockets:
            return
        results = await asyncio.gather(*[
            asyncio.wait_for(socket.send_json(message), timeout=3) for socket in sockets
        ], return_exceptions=True)
        removed = False
        for socket, result in zip(sockets, results):
            if isinstance(result, BaseException):
                self.connections.pop(socket, None)
                removed = True
        if removed:
            await self.presence()

    async def presence(self):
        await self.broadcast({"type": "presence", "members": self.members()})

    async def revoke(self, digest):
        sockets = [socket for socket, (_, session) in list(self.connections.items()) if session == digest]
        for socket in sockets:
            self.connections.pop(socket, None)
            try:
                await socket.close(code=1008)
            except (RuntimeError, WebSocketDisconnect):
                pass
        await self.presence()


@router.websocket("/api/ws")
async def wall_socket(socket: WebSocket):
    token = socket.cookies.get(COOKIE)
    user = authenticated_user(socket.app, token)
    origin = socket.headers.get("origin")
    if not user or (origin and urlparse(origin).netloc != socket.headers.get("host")):
        await socket.close(code=1008)
        return
    hub = socket.app.state.hub
    await socket.accept()
    try:
        # Registration and snapshot use the same lock as mutations, preventing join-time event gaps.
        async with socket.app.state.mutation_lock:
            hub.connections[socket] = (user, token_digest(token))
            await socket.send_json({"type": "board", "board": board_snapshot(socket.app)})
            await hub.presence()
        while True:
            text = await asyncio.wait_for(socket.receive_text(), timeout=50)
            if len(text) > 256:
                await socket.close(code=1009)
                break
            if not authenticated_user(socket.app, token):
                await socket.close(code=1008)
                break
            if text == "ping":
                await socket.send_json({"type": "pong"})
    except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError):
        pass
    finally:
        hub.connections.pop(socket, None)
        await hub.presence()
