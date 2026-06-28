"""
Agent OS V6.0 - Memory Store
Storage backends for three-layer memory: InMemory + Redis
"""
import json
import time
from typing import Optional, Dict, Any, List

from agent_os.config import get_config
from agent_os.core_platform.memory_system.models import (
    MemoryEntry, MemoryType, Session,
)


class MemoryStore:
    """
    Memory storage backend abstraction.

    Supports:
    - InMemory: Fast, ephemeral, suitable for development
    - Redis: Persistent, distributed, suitable for production
    """

    def __init__(self, backend: str = "memory"):
        self._backend = backend
        self._config = get_config().memory
        # In-memory fallback storage
        self._working: Dict[str, List[MemoryEntry]] = {}  # session_id -> entries
        self._episodic: Dict[str, List[MemoryEntry]] = {}  # session_id -> entries
        self._semantic: Dict[str, MemoryEntry] = {}  # entry_id -> entry
        self._sessions: Dict[str, Session] = {}  # session_id -> Session
        self._redis = None

    async def _get_redis(self):
        if self._backend != "redis":
            return None
        if self._redis is None:
            try:
                from agent_os.infra.redis import get_redis_client
                self._redis = get_redis_client()
                await self._redis.connect()
            except Exception:
                self._redis = None
        return self._redis

    # ── Session Management ────────────────────────────

    async def create_session(self, session: Session) -> Session:
        self._sessions[session.session_id] = session
        self._working[session.session_id] = []
        self._episodic[session.session_id] = []

        redis = await self._get_redis()
        if redis:
            try:
                await redis.set(
                    f"mem:session:{session.session_id}",
                    json.dumps(session.to_dict()),
                    expire=self._config.session_ttl_seconds,
                )
            except Exception:
                pass

        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session:
            return session

        redis = await self._get_redis()
        if redis:
            try:
                data = await redis.get(f"mem:session:{session_id}")
                if data:
                    session = Session(**json.loads(data))
                    self._sessions[session_id] = session
                    return session
            except Exception:
                pass

        return None

    async def update_session(self, session_id: str, **kwargs) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if not session:
            return None

        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)

        redis = await self._get_redis()
        if redis:
            try:
                await redis.set(
                    f"mem:session:{session_id}",
                    json.dumps(session.to_dict()),
                    expire=self._config.session_ttl_seconds,
                )
            except Exception:
                pass

        return session

    async def delete_session(self, session_id: str) -> bool:
        self._sessions.pop(session_id, None)
        self._working.pop(session_id, None)
        self._episodic.pop(session_id, None)

        redis = await self._get_redis()
        if redis:
            try:
                await redis.delete(f"mem:session:{session_id}")
            except Exception:
                pass

        return True

    async def list_sessions(self, tenant_id: str) -> List[Session]:
        return [
            s for s in self._sessions.values()
            if s.tenant_id == tenant_id
        ]

    # ── Working Memory ────────────────────────────────

    async def add_working(self, session_id: str, entry: MemoryEntry) -> MemoryEntry:
        if session_id not in self._working:
            self._working[session_id] = []

        entries = self._working[session_id]

        # Enforce capacity limit (FIFO)
        if len(entries) >= self._config.working_memory_capacity:
            entries.pop(0)

        entries.append(entry)
        return entry

    async def get_working(
        self, session_id: str, limit: Optional[int] = None,
    ) -> List[MemoryEntry]:
        entries = self._working.get(session_id, [])
        limit = limit or self._config.max_context_window
        return entries[-limit:]

    async def clear_working(self, session_id: str) -> bool:
        if session_id in self._working:
            self._working[session_id] = []
        return True

    # ── Episodic Memory ───────────────────────────────

    async def add_episodic(self, session_id: str, entry: MemoryEntry) -> MemoryEntry:
        if session_id not in self._episodic:
            self._episodic[session_id] = []

        entries = self._episodic[session_id]

        if len(entries) >= self._config.episodic_memory_capacity:
            entries.pop(0)

        entries.append(entry)
        return entry

    async def get_episodic(
        self, session_id: str, limit: int = 20, offset: int = 0,
    ) -> List[MemoryEntry]:
        entries = self._episodic.get(session_id, [])
        return entries[-(offset + limit):-offset] if offset else entries[-limit:]

    async def search_episodic(
        self, session_id: str, query: str, limit: int = 10,
    ) -> List[MemoryEntry]:
        entries = self._episodic.get(session_id, [])
        query_lower = query.lower()
        results = [
            e for e in entries
            if query_lower in e.content.lower() or
            query_lower in " ".join(e.tags).lower()
        ]
        return results[-limit:]

    # ── Semantic Memory ───────────────────────────────

    async def add_semantic(self, entry: MemoryEntry) -> MemoryEntry:
        if len(self._semantic) >= self._config.semantic_memory_capacity:
            # Remove oldest entry
            oldest = min(
                self._semantic.values(),
                key=lambda e: e.last_accessed_at or e.created_at,
            )
            self._semantic.pop(oldest.entry_id, None)

        self._semantic[entry.entry_id] = entry
        return entry

    async def get_semantic(self, entry_id: str) -> Optional[MemoryEntry]:
        entry = self._semantic.get(entry_id)
        if entry:
            entry.access_count += 1
            entry.last_accessed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return entry

    async def search_semantic(
        self, query_embedding: List[float], tenant_id: str = "",
        top_k: int = 5, threshold: float = 0.3,
    ) -> List[MemoryEntry]:
        if not query_embedding:
            return []

        # Filter by tenant
        candidates = [
            e for e in self._semantic.values()
            if not tenant_id or e.tenant_id == tenant_id
        ]

        if not candidates:
            return []

        # Compute cosine similarity
        scored = []
        for entry in candidates:
            if entry.embedding:
                sim = self._cosine_similarity(query_embedding, entry.embedding)
                if sim >= threshold:
                    scored.append((sim, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for sim, entry in scored[:top_k]:
            entry.access_count += 1
            entry.last_accessed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            results.append(entry)

        return results

    async def search_semantic_by_text(
        self, query: str, tenant_id: str = "",
        top_k: int = 5,
    ) -> List[MemoryEntry]:
        """Simple text-based semantic search fallback."""
        query_lower = query.lower()
        candidates = [
            e for e in self._semantic.values()
            if not tenant_id or e.tenant_id == tenant_id
        ]

        scored = []
        for entry in candidates:
            score = 0
            if query_lower in entry.content.lower():
                score += 1.0
            for tag in entry.tags:
                if query_lower in tag.lower():
                    score += 0.5
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    async def delete_semantic(self, entry_id: str) -> bool:
        self._semantic.pop(entry_id, None)
        return True

    # ── Consolidation ──────────────────────────────────

    async def consolidate_to_semantic(
        self, entry: MemoryEntry,
    ) -> Optional[MemoryEntry]:
        """Promote an episodic entry to semantic memory."""
        semantic_entry = MemoryEntry(
            session_id=entry.session_id,
            tenant_id=entry.tenant_id,
            memory_type=MemoryType.SEMANTIC.value,
            role=entry.role,
            content=entry.content,
            importance=entry.importance,
            embedding=entry.embedding,
            tags=entry.tags,
            metadata=entry.metadata,
        )
        return await self.add_semantic(semantic_entry)

    # ── Utility ───────────────────────────────────────

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def get_stats(self, tenant_id: str = "") -> Dict[str, Any]:
        working_count = sum(
            len(v) for k, v in self._working.items()
            if not tenant_id or any(e.tenant_id == tenant_id for e in v)
        )
        episodic_count = sum(
            len(v) for k, v in self._episodic.items()
            if not tenant_id or any(e.tenant_id == tenant_id for e in v)
        )
        semantic_count = sum(
            1 for e in self._semantic.values()
            if not tenant_id or e.tenant_id == tenant_id
        )
        session_count = sum(
            1 for s in self._sessions.values()
            if not tenant_id or s.tenant_id == tenant_id
        )

        return {
            "backend": self._backend,
            "working_memories": working_count,
            "episodic_memories": episodic_count,
            "semantic_memories": semantic_count,
            "active_sessions": session_count,
            "config": {
                "working_capacity": self._config.working_memory_capacity,
                "episodic_capacity": self._config.episodic_memory_capacity,
                "semantic_capacity": self._config.semantic_memory_capacity,
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "MemoryStore",
            "backend": self._backend,
            "config": {
                "working_capacity": self._config.working_memory_capacity,
                "episodic_capacity": self._config.episodic_memory_capacity,
                "semantic_capacity": self._config.semantic_memory_capacity,
            },
        }