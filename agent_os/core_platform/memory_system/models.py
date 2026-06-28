"""
Agent OS V6.0 - Memory System Models
Three-layer memory: Working, Episodic, Semantic
"""
import uuid
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone


class MemoryType(str, Enum):
    WORKING = "working"      # Short-term, current context
    EPISODIC = "episodic"    # Medium-term, session history
    SEMANTIC = "semantic"    # Long-term, vector knowledge


class MemoryRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class MemoryEntry:
    """A single memory entry in any layer."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    tenant_id: str = ""
    memory_type: str = MemoryType.WORKING.value
    role: str = MemoryRole.USER.value
    content: str = ""
    embedding: Optional[List[float]] = field(default=None, repr=False)
    importance: float = 0.5  # 0.0 - 1.0
    access_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_accessed_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self, include_embedding: bool = False) -> dict:
        d = {
            "entry_id": self.entry_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "memory_type": self.memory_type,
            "role": self.role,
            "content": self.content[:500],
            "importance": self.importance,
            "access_count": self.access_count,
            "created_at": self.created_at,
            "last_accessed_at": self.last_accessed_at,
            "tags": self.tags,
            "metadata": self.metadata,
        }
        if include_embedding and self.embedding:
            d["embedding_dim"] = len(self.embedding)
        return d


@dataclass
class Session:
    """A conversation session with memory layers."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    agent_id: str = ""
    title: str = ""
    status: str = "active"  # active | paused | completed
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    expires_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    total_interactions: int = 0

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "total_interactions": self.total_interactions,
            "metadata": self.metadata,
        }


@dataclass
class MemoryQueryResult:
    """Result of a memory query across layers."""
    query: str = ""
    working_memories: List[MemoryEntry] = field(default_factory=list)
    episodic_memories: List[MemoryEntry] = field(default_factory=list)
    semantic_memories: List[MemoryEntry] = field(default_factory=list)
    total_found: int = 0
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "working_memories": [m.to_dict() for m in self.working_memories],
            "episodic_memories": [m.to_dict() for m in self.episodic_memories],
            "semantic_memories": [m.to_dict() for m in self.semantic_memories],
            "total_found": self.total_found,
            "latency_ms": round(self.latency_ms, 2),
        }


@dataclass
class MemoryContext:
    """Assembled context from all memory layers for LLM prompt."""
    entries: List[MemoryEntry] = field(default_factory=list)
    context_text: str = ""
    source_layers: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "context_text": self.context_text[:1000],
            "source_layers": self.source_layers,
            "total_entries": len(self.entries),
        }