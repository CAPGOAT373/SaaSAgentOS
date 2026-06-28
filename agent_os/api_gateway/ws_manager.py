"""
Agent OS V6.0 - WebSocket Connection Manager
Real-time event broadcasting with tenant isolation
"""
import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class WSConnection:
    """A single WebSocket connection with metadata"""
    connection_id: str
    websocket: WebSocket
    tenant_id: str = ""
    user_id: str = ""
    subscribed_topics: Set[str] = field(default_factory=set)
    connected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "connection_id": self.connection_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "subscribed_topics": list(self.subscribed_topics),
            "connected_at": self.connected_at,
            "last_activity": self.last_activity,
        }


class WSConnectionManager:
    """Manages all WebSocket connections with tenant isolation"""

    def __init__(self):
        self._connections: Dict[str, WSConnection] = {}
        self._tenant_connections: Dict[str, Set[str]] = {}  # tenant_id -> {connection_ids}
        self._lock = asyncio.Lock()
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)

    async def connect(
        self, websocket: WebSocket, tenant_id: str = "", user_id: str = ""
    ) -> WSConnection:
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        connection_id = str(id(websocket))
        conn = WSConnection(
            connection_id=connection_id,
            websocket=websocket,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        async with self._lock:
            self._connections[connection_id] = conn
            if tenant_id:
                if tenant_id not in self._tenant_connections:
                    self._tenant_connections[tenant_id] = set()
                self._tenant_connections[tenant_id].add(connection_id)

        logger.info(f"WS connection {connection_id} connected (tenant={tenant_id}, user={user_id})")
        return conn

    async def disconnect(self, connection_id: str):
        """Remove a disconnected WebSocket connection"""
        async with self._lock:
            conn = self._connections.pop(connection_id, None)
            if conn and conn.tenant_id:
                tenant_conns = self._tenant_connections.get(conn.tenant_id, set())
                tenant_conns.discard(connection_id)
        logger.info(f"WS connection {connection_id} disconnected")

    async def subscribe(self, connection_id: str, topics: List[str]):
        """Subscribe a connection to event topics"""
        async with self._lock:
            conn = self._connections.get(connection_id)
            if conn:
                for topic in topics:
                    conn.subscribed_topics.add(topic)

    async def unsubscribe(self, connection_id: str, topics: List[str]):
        """Unsubscribe a connection from event topics"""
        async with self._lock:
            conn = self._connections.get(connection_id)
            if conn:
                for topic in topics:
                    conn.subscribed_topics.discard(topic)

    async def broadcast_to_tenant(
        self, tenant_id: str, event_type: str, data: Dict[str, Any]
    ):
        """Broadcast event to all connections of a specific tenant"""
        async with self._lock:
            conn_ids = list(self._tenant_connections.get(tenant_id, set()))

        dead_connections = []
        for cid in conn_ids:
            conn = self._connections.get(cid)
            if not conn:
                continue
            try:
                await conn.websocket.send_json({
                    "type": event_type,
                    "tenant_id": tenant_id,
                    "data": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                conn.last_activity = datetime.now(timezone.utc).isoformat()
            except Exception:
                dead_connections.append(cid)

        for cid in dead_connections:
            await self.disconnect(cid)

    async def broadcast_to_all(
        self, event_type: str, data: Dict[str, Any], exclude_tenant: str = ""
    ):
        """Broadcast event to all connected clients"""
        async with self._lock:
            conns = list(self._connections.items())

        dead_connections = []
        for cid, conn in conns:
            if exclude_tenant and conn.tenant_id == exclude_tenant:
                continue
            try:
                await conn.websocket.send_json({
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                conn.last_activity = datetime.now(timezone.utc).isoformat()
            except Exception:
                dead_connections.append(cid)

        for cid in dead_connections:
            await self.disconnect(cid)

    async def send_to_connection(self, connection_id: str, data: Dict[str, Any]):
        """Send data to a specific connection"""
        conn = self._connections.get(connection_id)
        if conn:
            try:
                await conn.websocket.send_json(data)
                conn.last_activity = datetime.now(timezone.utc).isoformat()
                return True
            except Exception:
                await self.disconnect(connection_id)
        return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""
        async with self._lock:
            tenants = {}
            for tid, cids in self._tenant_connections.items():
                tenants[tid] = len(cids)
            return {
                "total_connections": len(self._connections),
                "tenants_connected": len(self._tenant_connections),
                "per_tenant": tenants,
            }

    async def cleanup_stale(self, max_idle_seconds: int = 300):
        """Clean up stale connections"""
        now = datetime.now(timezone.utc)
        dead = []
        for cid, conn in self._connections.items():
            try:
                last = datetime.fromisoformat(conn.last_activity)
                if (now - last).total_seconds() > max_idle_seconds:
                    dead.append(cid)
            except Exception:
                dead.append(cid)
        for cid in dead:
            await self.disconnect(cid)
        if dead:
            logger.info(f"Cleaned up {len(dead)} stale WS connections")


_ws_manager: Optional[WSConnectionManager] = None


def get_ws_manager() -> WSConnectionManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WSConnectionManager()
    return _ws_manager