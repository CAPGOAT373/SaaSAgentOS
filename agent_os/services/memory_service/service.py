"""
Agent OS V6.0 - Memory Service
Service layer wrapping the three-layer memory engine
"""
from typing import Optional, Dict, Any, List

from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.exceptions import NotFoundException, ValidationException
from agent_os.core_platform.memory_system.models import (
    MemoryEntry, MemoryType, MemoryRole, Session, MemoryQueryResult, MemoryContext,
)
from agent_os.core_platform.memory_system.engine import MemoryEngine, get_memory_engine
from agent_os.config import get_config


class MemoryService(BaseService):
    """
    Memory Service: three-layer memory management.

    API:
    - Session: create_session / get_session / update_session / delete_session / list_sessions
    - Working Memory: add_to_working / add_to_working_batch / get_working_context / clear_working
    - Episodic Memory: add_to_episodic / get_episodic_history / search_episodic
    - Semantic Memory: add_to_semantic / search_semantic / get_semantic_entry / delete_semantic_entry
    - Query: query / assemble_context
    - Consolidation: consolidate_episodic_to_semantic / auto_consolidate
    - Stats: get_stats / health_check
    """

    def __init__(self):
        super().__init__()
        self._engine = get_memory_engine()
        self._config = get_config().memory

    # ── Session Management ────────────────────────────

    async def create_session(
        self, tenant_id: str, user_id: str = "",
        agent_id: str = "", title: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Create a new conversation session."""
        session = await self._engine.create_session(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            title=title,
            metadata=metadata,
        )

        await self.emit_event("memory.session.created", {
            "session_id": session.session_id,
            "tenant_id": tenant_id,
        }, ctx)

        self.log("info", f"Session created: {session.session_id}", ctx)
        return session.to_dict()

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get a session by ID."""
        session = await self._engine.get_session(session_id)
        if not session:
            raise NotFoundException("Session", session_id)
        return session.to_dict()

    async def update_session(
        self, session_id: str, title: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Update session metadata."""
        kwargs = {}
        if title is not None:
            kwargs["title"] = title
        if status is not None:
            kwargs["status"] = status
        if metadata is not None:
            kwargs["metadata"] = metadata

        session = await self._engine.update_session(session_id, **kwargs)
        if not session:
            raise NotFoundException("Session", session_id)

        await self.emit_event("memory.session.updated", {
            "session_id": session_id,
        }, ctx)

        return session.to_dict()

    async def delete_session(
        self, session_id: str, ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Delete a session and its memories."""
        await self._engine.delete_session(session_id)

        await self.emit_event("memory.session.deleted", {
            "session_id": session_id,
        }, ctx)

        self.log("info", f"Session deleted: {session_id}", ctx)
        return {"deleted": True, "session_id": session_id}

    async def list_sessions(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List all sessions for a tenant."""
        sessions = await self._engine.list_sessions(tenant_id)
        return [s.to_dict() for s in sessions]

    # ── Working Memory ────────────────────────────────

    async def add_to_working(
        self, session_id: str, content: str,
        role: str = MemoryRole.USER.value,
        importance: float = 0.5,
        tenant_id: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Add an entry to working memory."""
        if not content or not content.strip():
            raise ValidationException("Content cannot be empty")

        entry = await self._engine.add_to_working(
            session_id=session_id,
            content=content,
            role=role,
            importance=importance,
            tenant_id=tenant_id,
            tags=tags,
            metadata=metadata,
        )

        await self.emit_event("memory.working.added", {
            "entry_id": entry.entry_id,
            "session_id": session_id,
            "role": role,
        }, ctx)

        return entry.to_dict()

    async def add_to_working_batch(
        self, session_id: str, messages: List[Dict[str, Any]],
        tenant_id: str = "",
        ctx: Optional[ServiceContext] = None,
    ) -> List[Dict[str, Any]]:
        """Add multiple messages to working memory."""
        if not messages:
            raise ValidationException("Messages list cannot be empty")

        entries = await self._engine.add_to_working_batch(
            session_id=session_id,
            messages=messages,
            tenant_id=tenant_id,
        )

        await self.emit_event("memory.working.batch_added", {
            "session_id": session_id,
            "count": len(entries),
        }, ctx)

        self.log("info", f"Batch added {len(entries)} entries to working memory", ctx)
        return [e.to_dict() for e in entries]

    async def get_working_context(
        self, session_id: str, limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent working memory entries."""
        entries = await self._engine.get_working_context(session_id, limit)
        return [e.to_dict() for e in entries]

    async def clear_working(
        self, session_id: str, ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Clear working memory for a session."""
        await self._engine.clear_working(session_id)
        return {"cleared": True, "session_id": session_id}

    # ── Episodic Memory ───────────────────────────────

    async def add_to_episodic(
        self, session_id: str, content: str,
        role: str = MemoryRole.USER.value,
        importance: float = 0.5,
        tenant_id: str = "",
        tags: Optional[List[str]] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Add an entry to episodic memory."""
        entry = await self._engine.add_to_episodic(
            session_id=session_id,
            content=content,
            role=role,
            importance=importance,
            tenant_id=tenant_id,
            tags=tags,
        )
        return entry.to_dict()

    async def get_episodic_history(
        self, session_id: str, limit: int = 20, offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get episodic memory history."""
        entries = await self._engine.get_episodic_history(session_id, limit, offset)
        return [e.to_dict() for e in entries]

    async def search_episodic(
        self, session_id: str, query: str, limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search episodic memory."""
        entries = await self._engine.search_episodic(session_id, query, limit)
        return [e.to_dict() for e in entries]

    # ── Semantic Memory ───────────────────────────────

    async def add_to_semantic(
        self, content: str, tenant_id: str = "",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embed: bool = True,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Add an entry to semantic memory."""
        if not content or not content.strip():
            raise ValidationException("Content cannot be empty")

        entry = await self._engine.add_to_semantic(
            content=content,
            tenant_id=tenant_id,
            importance=importance,
            tags=tags,
            metadata=metadata,
            embed=embed,
        )

        await self.emit_event("memory.semantic.added", {
            "entry_id": entry.entry_id,
            "tenant_id": tenant_id,
        }, ctx)

        self.log("info", f"Semantic memory added: {entry.entry_id}", ctx)
        return entry.to_dict(include_embedding=True)

    async def search_semantic(
        self, query: str, tenant_id: str = "",
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> List[Dict[str, Any]]:
        """Search semantic memory."""
        entries = await self._engine.search_semantic(
            query=query,
            tenant_id=tenant_id,
            top_k=top_k,
            threshold=threshold,
        )

        self.log("info", f"Semantic search '{query[:50]}': {len(entries)} results", ctx)
        return [e.to_dict(include_embedding=True) for e in entries]

    async def get_semantic_entry(self, entry_id: str) -> Dict[str, Any]:
        """Get a semantic memory entry."""
        entry = await self._engine.get_semantic_entry(entry_id)
        if not entry:
            raise NotFoundException("SemanticMemory", entry_id)
        return entry.to_dict(include_embedding=True)

    async def delete_semantic_entry(
        self, entry_id: str, ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Delete a semantic memory entry."""
        await self._engine.delete_semantic_entry(entry_id)
        return {"deleted": True, "entry_id": entry_id}

    # ── Query & Context ───────────────────────────────

    async def query(
        self, session_id: str, query: str,
        tenant_id: str = "",
        include_working: bool = True,
        include_episodic: bool = True,
        include_semantic: bool = True,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Query all memory layers."""
        if not query or not query.strip():
            raise ValidationException("Query cannot be empty")

        result = await self._engine.query(
            session_id=session_id,
            query=query,
            tenant_id=tenant_id,
            include_working=include_working,
            include_episodic=include_episodic,
            include_semantic=include_semantic,
        )

        self.log("info", f"Memory query: {result.total_found} results ({result.latency_ms:.1f}ms)", ctx)
        return result.to_dict()

    async def assemble_context(
        self, session_id: str, query: str = "",
        tenant_id: str = "",
        max_working: Optional[int] = None,
        max_episodic: int = 5,
        max_semantic: int = 5,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Assemble context from all memory layers."""
        context = await self._engine.assemble_context(
            session_id=session_id,
            query=query,
            tenant_id=tenant_id,
            max_working=max_working,
            max_episodic=max_episodic,
            max_semantic=max_semantic,
        )

        self.log("info", f"Context assembled: {len(context.entries)} entries from {context.source_layers}", ctx)
        return context.to_dict()

    # ── Consolidation ──────────────────────────────────

    async def consolidate_episodic_to_semantic(
        self, session_id: str, entry_id: str,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Consolidate an episodic entry to semantic memory."""
        entry = await self._engine.consolidate_episodic_to_semantic(
            session_id, entry_id,
        )
        if entry:
            await self.emit_event("memory.consolidated", {
                "entry_id": entry_id,
                "session_id": session_id,
            }, ctx)
            return entry.to_dict(include_embedding=True)
        return {"consolidated": False, "entry_id": entry_id}

    async def auto_consolidate(
        self, session_id: str, ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Auto-consolidate high-importance episodic entries."""
        entries = await self._engine.auto_consolidate(session_id)

        await self.emit_event("memory.auto_consolidated", {
            "session_id": session_id,
            "count": len(entries),
        }, ctx)

        self.log("info", f"Auto-consolidated {len(entries)} entries", ctx)
        return {
            "consolidated": len(entries),
            "session_id": session_id,
            "entries": [e.to_dict(include_embedding=True) for e in entries],
        }

    # ── Statistics ────────────────────────────────────

    async def get_stats(self, tenant_id: str = "") -> Dict[str, Any]:
        """Get memory statistics."""
        return await self._engine.get_stats(tenant_id)

    async def health_check(self) -> Dict[str, Any]:
        """Health check."""
        return {
            "status": "healthy",
            "service": "MemoryService",
            "backend": self._config.backend,
            "config": {
                "working_capacity": self._config.working_memory_capacity,
                "episodic_capacity": self._config.episodic_memory_capacity,
                "semantic_capacity": self._config.semantic_memory_capacity,
                "session_ttl": self._config.session_ttl_seconds,
            },
        }


_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service