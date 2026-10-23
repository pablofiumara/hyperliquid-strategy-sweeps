"""WebSocket room management for the hyperliquid strategy app.

Complements the existing SSE transport: SSE stays the simple single-job stream,
while WebSockets add bidirectional control (cancel) and multi-client presence.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class JobRoomManager:
    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, job_id: int, ws: WebSocket) -> int:
        async with self._lock:
            self._rooms.setdefault(job_id, set()).add(ws)
            return len(self._rooms[job_id])

    async def disconnect(self, job_id: int, ws: WebSocket) -> int:
        async with self._lock:
            conns = self._rooms.get(job_id)
            if conns is not None:
                conns.discard(ws)
                if not conns:
                    del self._rooms[job_id]
                    return 0
                return len(conns)
            return 0

    async def broadcast(self, job_id: int, msg: dict[str, Any]) -> None:
        async with self._lock:
            conns = list(self._rooms.get(job_id, ()))
        for ws in conns:
            try:
                await ws.send_json(msg)
            except Exception:
                pass

    def count(self, job_id: int) -> int:
        return len(self._rooms.get(job_id, ()))