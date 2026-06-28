"""
Agent OS V6.0 - Memory System
Multi-tier memory: short-term, long-term, semantic, episodic
"""
import uuid
import time
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.core_platform.base import BaseService, ServiceContext


class MemoryType(str, Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    WORKING = "working"


@dataclass
class MemoryEntry:
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    tenant_id: str = ""
    memory_type: str = MemoryType.SHORT_TERM.value
    role: str = "user"
    content: str = ""
    embedding: Optional[List[float]] = None
    importance: float = 0.5
    access_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_accessed: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id, "agent_id": self.agent_id,
            "tenant_id": self.tenant_id, "memory_type": self.memory_type,
            "role": self.role, "content": self.content[:500],
            "importance": self.importance, "access_count": self.access_count,
            "created_at": self.created_at, "last_accessed": self.last_accessed,
        }


class MemorySystem(BaseService):
    """Multi-tier Memory System for agents"""

    def __init__(self):
        super().__init__()
        self._short_term: Dict[str, List[MemoryEntry]] = {}  # agent_id -> entries
        self._long_term: Dict[str, List[MemoryEntry]] = {}
        self._episodic: Dict[str, List[MemoryEntry]] = {}
        self._semantic: Dict[str, List[MemoryEntry]] = {}
        self._short_term_limit = 50

    async def store(
        self, agent_id: str, tenant_id: str, role: str, content: str,
        memory_type: str = MemoryType.SHORT_TERM.value,
        importance: float = 0.5, ctx: Optional[ServiceContext] = None
    ) -> MemoryEntry:
        entry = MemoryEntry(
            agent_id=agent_id, tenant_id=tenant_id,
            memory_type=memory_type, role=role, content=content,
            importance=importance,
        )

        if memory_type == MemoryType.SHORT_TERM.value:
            store = self._short_term
        elif memory_type == MemoryType.LONG_TERM.value:
            store = self._long_term
        elif memory_type == MemoryType.EPISODIC.value:
            store = self._episodic
        elif memory_type == MemoryType.SEMANTIC.value:
            store = self._semantic
        else:
            store = self._short_term

        if agent_id not in store:
            store[agent_id] = []

        store[agent_id].append(entry)

        # Evict old short-term memories
        if memory_type == MemoryType.SHORT_TERM.value and len(store[agent_id]) > self._short_term_limit:
            store[agent_id] = store[agent_id][-self._short_term_limit:]

        # Promote important memories to long-term
        if importance > 0.7 and memory_type == MemoryType.SHORT_TERM.value:
            await self.store(agent_id, tenant_id, role, content, MemoryType.LONG_TERM.value, importance, ctx)

        return entry

    async def retrieve(
        self, agent_id: str, tenant_id: str = "",
        memory_type: str = MemoryType.SHORT_TERM.value,
        limit: int = 10, query: str = ""
    ) -> List[Dict[str, str]]:
        if memory_type == MemoryType.SHORT_TERM.value:
            store = self._short_term
        elif memory_type == MemoryType.LONG_TERM.value:
            store = self._long_term
        elif memory_type == MemoryType.EPISODIC.value:
            store = self._episodic
        elif memory_type == MemoryType.SEMANTIC.value:
            store = self._semantic
        else:
            store = self._short_term

        entries = store.get(agent_id, [])

        if query:
            entries = [e for e in entries if query.lower() in e.content.lower()]

        # Sort by importance and recency
        entries = sorted(entries, key=lambda e: (e.importance, e.created_at), reverse=True)

        for e in entries[:limit]:
            e.access_count += 1
            e.last_accessed = datetime.now(timezone.utc).isoformat()

        return [{"role": e.role, "content": e.content} for e in entries[:limit]]

    async def retrieve_all_tiers(
        self, agent_id: str, limit_per_tier: int = 5
    ) -> Dict[str, List[Dict[str, str]]]:
        return {
            "short_term": await self.retrieve(agent_id, memory_type=MemoryType.SHORT_TERM.value, limit=limit_per_tier),
            "long_term": await self.retrieve(agent_id, memory_type=MemoryType.LONG_TERM.value, limit=limit_per_tier),
            "episodic": await self.retrieve(agent_id, memory_type=MemoryType.EPISODIC.value, limit=limit_per_tier),
            "semantic": await self.retrieve(agent_id, memory_type=MemoryType.SEMANTIC.value, limit=limit_per_tier),
        }

    async def semantic_search(
        self, agent_id: str, query: str, limit: int = 5
    ) -> List[Dict[str, str]]:
        """Simple keyword-based semantic search over all memory tiers"""
        results = []
        for store in [self._short_term, self._long_term, self._episodic, self._semantic]:
            entries = store.get(agent_id, [])
            for e in entries:
                score = self._keyword_score(query, e.content)
                if score > 0:
                    results.append((score, e))

        results.sort(key=lambda x: x[0], reverse=True)
        return [{"role": e.role, "content": e.content} for _, e in results[:limit]]

    def _keyword_score(self, query: str, content: str) -> float:
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        if not query_words:
            return 0.0
        return len(query_words & content_words) / len(query_words)

    async def summarize_memory(
        self, agent_id: str, ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        """Summarize all memories for an agent"""
        entries = self._short_term.get(agent_id, []) + self._long_term.get(agent_id, [])
        return {
            "agent_id": agent_id,
            "total_entries": len(entries),
            "short_term_count": len(self._short_term.get(agent_id, [])),
            "long_term_count": len(self._long_term.get(agent_id, [])),
            "episodic_count": len(self._episodic.get(agent_id, [])),
            "semantic_count": len(self._semantic.get(agent_id, [])),
            "recent_entries": [e.to_dict() for e in entries[-5:]],
        }

    async def clear_memory(self, agent_id: str, memory_type: Optional[str] = None):
        if memory_type:
            stores = {
                MemoryType.SHORT_TERM.value: self._short_term,
                MemoryType.LONG_TERM.value: self._long_term,
                MemoryType.EPISODIC.value: self._episodic,
                MemoryType.SEMANTIC.value: self._semantic,
            }
            store = stores.get(memory_type)
            if store and agent_id in store:
                store[agent_id] = []
        else:
            for store in [self._short_term, self._long_term, self._episodic, self._semantic]:
                if agent_id in store:
                    store[agent_id] = []

    async def health_check(self) -> Dict[str, Any]:
        total = sum(len(v) for v in self._short_term.values())
        total += sum(len(v) for v in self._long_term.values())
        return {
            "status": "healthy",
            "service": "MemorySystem",
            "total_entries": total,
            "agents_with_memory": len(self._short_term),
        }


_memory_system: Optional[MemorySystem] = None


def get_memory_system() -> MemorySystem:
    global _memory_system
    if _memory_system is None:
        _memory_system = MemorySystem()
    return _memory_system