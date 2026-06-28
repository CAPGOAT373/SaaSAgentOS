"""
Agent OS V6.0 - Memory Engine
Three-layer memory: Working, Episodic, Semantic
"""
import time
from typing import Optional, Dict, Any, List

from agent_os.config import get_config
from agent_os.core_platform.memory_system.models import (
    MemoryEntry, MemoryType, MemoryRole, Session,
    MemoryQueryResult, MemoryContext,
)
from agent_os.core_platform.memory_system.store import MemoryStore


class MemoryEngine:
    """
    Three-layer Memory Engine.

    Layers:
    - Working Memory: Short-term, current conversation context (limited capacity)
    - Episodic Memory: Medium-term, session history and interactions
    - Semantic Memory: Long-term, vector-based knowledge with semantic search

    Features:
    - Auto-consolidation from working → episodic
    - Consolidation from episodic → semantic (based on importance + access count)
    - Semantic search using embeddings
    - Context assembly for LLM prompts
    - Session lifecycle management
    """

    def __init__(self):
        self._config = get_config().memory
        self._store = MemoryStore(backend=self._config.backend)
        self._embedding_provider = None

    async def _get_embedder(self):
        if self._embedding_provider is None:
            try:
                from agent_os.ai_layer.rag.embedding import (
                    HashEmbeddingProvider, get_embedding_provider,
                )
                self._embedding_provider = get_embedding_provider()
            except Exception:
                from agent_os.ai_layer.rag.embedding import HashEmbeddingProvider
                self._embedding_provider = HashEmbeddingProvider(
                    dim=self._config.embedding_dim,
                )
        return self._embedding_provider

    # ── Session Management ────────────────────────────

    async def create_session(
        self, tenant_id: str, user_id: str = "",
        agent_id: str = "", title: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """Create a new conversation session."""
        session = Session(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            title=title or f"Session {tenant_id}",
            metadata=metadata or {},
        )
        return await self._store.create_session(session)

    async def get_session(self, session_id: str) -> Optional[Session]:
        return await self._store.get_session(session_id)

    async def update_session(self, session_id: str, **kwargs) -> Optional[Session]:
        return await self._store.update_session(session_id, **kwargs)

    async def delete_session(self, session_id: str) -> bool:
        return await self._store.delete_session(session_id)

    async def list_sessions(self, tenant_id: str) -> List[Session]:
        return await self._store.list_sessions(tenant_id)

    # ── Working Memory ────────────────────────────────

    async def add_to_working(
        self, session_id: str, content: str,
        role: str = MemoryRole.USER.value,
        importance: float = 0.5,
        tenant_id: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Add an entry to working memory (current conversation context)."""
        entry = MemoryEntry(
            session_id=session_id,
            tenant_id=tenant_id,
            memory_type=MemoryType.WORKING.value,
            role=role,
            content=content,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
        )

        entry = await self._store.add_working(session_id, entry)

        # Auto-consolidate to episodic memory
        episodic_entry = MemoryEntry(
            session_id=entry.session_id,
            tenant_id=entry.tenant_id,
            memory_type=MemoryType.EPISODIC.value,
            role=entry.role,
            content=entry.content,
            importance=entry.importance,
            tags=entry.tags,
            metadata=entry.metadata,
        )
        await self._store.add_episodic(session_id, episodic_entry)

        return entry

    async def add_to_working_batch(
        self, session_id: str, messages: List[Dict[str, Any]],
        tenant_id: str = "",
    ) -> List[MemoryEntry]:
        """Add multiple messages to working memory."""
        entries = []
        for msg in messages:
            entry = await self.add_to_working(
                session_id=session_id,
                content=msg.get("content", ""),
                role=msg.get("role", MemoryRole.USER.value),
                importance=msg.get("importance", 0.5),
                tenant_id=tenant_id,
                tags=msg.get("tags"),
                metadata=msg.get("metadata"),
            )
            entries.append(entry)
        return entries

    async def get_working_context(
        self, session_id: str, limit: Optional[int] = None,
    ) -> List[MemoryEntry]:
        """Get recent working memory entries for context."""
        return await self._store.get_working(session_id, limit)

    async def clear_working(self, session_id: str) -> bool:
        return await self._store.clear_working(session_id)

    # ── Episodic Memory ───────────────────────────────

    async def add_to_episodic(
        self, session_id: str, content: str,
        role: str = MemoryRole.USER.value,
        importance: float = 0.5,
        tenant_id: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Add an entry directly to episodic memory."""
        entry = MemoryEntry(
            session_id=session_id,
            tenant_id=tenant_id,
            memory_type=MemoryType.EPISODIC.value,
            role=role,
            content=content,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
        )
        return await self._store.add_episodic(session_id, entry)

    async def get_episodic_history(
        self, session_id: str, limit: int = 20, offset: int = 0,
    ) -> List[MemoryEntry]:
        """Get episodic memory history for a session."""
        return await self._store.get_episodic(session_id, limit, offset)

    async def search_episodic(
        self, session_id: str, query: str, limit: int = 10,
    ) -> List[MemoryEntry]:
        """Search episodic memory by keyword."""
        return await self._store.search_episodic(session_id, query, limit)

    # ── Semantic Memory ───────────────────────────────

    async def add_to_semantic(
        self, content: str, tenant_id: str = "",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embed: bool = True,
    ) -> MemoryEntry:
        """Add an entry to semantic (long-term) memory with optional embedding."""
        embedding = None
        if embed:
            try:
                embedder = await self._get_embedder()
                embedding = await embedder.embed_single(content)
            except Exception:
                pass

        entry = MemoryEntry(
            tenant_id=tenant_id,
            memory_type=MemoryType.SEMANTIC.value,
            role=MemoryRole.SYSTEM.value,
            content=content,
            importance=importance,
            embedding=embedding,
            tags=tags or [],
            metadata=metadata or {},
        )
        return await self._store.add_semantic(entry)

    async def search_semantic(
        self, query: str, tenant_id: str = "",
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> List[MemoryEntry]:
        """Search semantic memory by query (using embeddings)."""
        top_k = top_k or self._config.top_k_semantic
        threshold = threshold or self._config.similarity_threshold

        # Try embedding-based search
        try:
            embedder = await self._get_embedder()
            query_embedding = await embedder.embed_single(query)
            results = await self._store.search_semantic(
                query_embedding, tenant_id=tenant_id,
                top_k=top_k, threshold=threshold,
            )
            if results:
                return results
        except Exception:
            pass

        # Fallback to text-based search
        return await self._store.search_semantic_by_text(
            query, tenant_id=tenant_id, top_k=top_k,
        )

    async def get_semantic_entry(self, entry_id: str) -> Optional[MemoryEntry]:
        return await self._store.get_semantic(entry_id)

    async def delete_semantic_entry(self, entry_id: str) -> bool:
        return await self._store.delete_semantic(entry_id)

    # ── Consolidation ──────────────────────────────────

    async def consolidate_episodic_to_semantic(
        self, session_id: str, entry_id: str,
    ) -> Optional[MemoryEntry]:
        """Promote an episodic entry to semantic memory."""
        entries = await self._store.get_episodic(session_id, limit=1000)
        for entry in entries:
            if entry.entry_id == entry_id:
                # Embed the content
                try:
                    embedder = await self._get_embedder()
                    entry.embedding = await embedder.embed_single(entry.content)
                except Exception:
                    pass
                return await self._store.consolidate_to_semantic(entry)
        return None

    async def auto_consolidate(
        self, session_id: str,
    ) -> List[MemoryEntry]:
        """Auto-consolidate high-importance episodic entries to semantic."""
        entries = await self._store.get_episodic(session_id, limit=1000)
        threshold = self._config.consolidation_threshold

        consolidated = []
        for entry in entries:
            if entry.access_count >= threshold and entry.importance >= 0.5:
                try:
                    embedder = await self._get_embedder()
                    entry.embedding = await embedder.embed_single(entry.content)
                except Exception:
                    pass
                result = await self._store.consolidate_to_semantic(entry)
                if result:
                    consolidated.append(result)

        return consolidated

    # ── Query & Context Assembly ──────────────────────

    async def query(
        self, session_id: str, query: str,
        tenant_id: str = "",
        include_working: bool = True,
        include_episodic: bool = True,
        include_semantic: bool = True,
    ) -> MemoryQueryResult:
        """Query all memory layers for relevant context."""
        start = time.time()

        working = []
        episodic = []
        semantic = []

        if include_working:
            working = await self._store.get_working(session_id)

        if include_episodic:
            episodic = await self._store.search_episodic(session_id, query)

        if include_semantic:
            semantic = await self.search_semantic(query, tenant_id=tenant_id)

        total = len(working) + len(episodic) + len(semantic)
        latency = (time.time() - start) * 1000

        return MemoryQueryResult(
            query=query,
            working_memories=working,
            episodic_memories=episodic,
            semantic_memories=semantic,
            total_found=total,
            latency_ms=latency,
        )

    async def assemble_context(
        self, session_id: str, query: str = "",
        tenant_id: str = "",
        max_working: Optional[int] = None,
        max_episodic: int = 5,
        max_semantic: int = 5,
    ) -> MemoryContext:
        """Assemble context from all memory layers for LLM prompt."""
        entries = []
        sources = []

        # Working memory (most recent)
        working = await self._store.get_working(
            session_id, limit=max_working or self._config.max_context_window,
        )
        if working:
            entries.extend(working)
            sources.append("working")

        # Episodic memory (relevant history)
        if query:
            episodic = await self._store.search_episodic(
                session_id, query, limit=max_episodic,
            )
            if episodic:
                entries.extend(episodic)
                sources.append("episodic")

        # Semantic memory (long-term knowledge)
        if query:
            semantic = await self.search_semantic(
                query, tenant_id=tenant_id, top_k=max_semantic,
            )
            if semantic:
                entries.extend(semantic)
                sources.append("semantic")

        # Build context text
        context_parts = []
        for entry in entries:
            context_parts.append(f"[{entry.role}]: {entry.content}")

        return MemoryContext(
            entries=entries,
            context_text="\n".join(context_parts),
            source_layers=sources,
        )

    # ── Statistics ────────────────────────────────────

    async def get_stats(self, tenant_id: str = "") -> Dict[str, Any]:
        return await self._store.get_stats(tenant_id)

    async def health_check(self) -> Dict[str, Any]:
        return await self._store.health_check()


_memory_engine: Optional[MemoryEngine] = None


def get_memory_engine() -> MemoryEngine:
    global _memory_engine
    if _memory_engine is None:
        _memory_engine = MemoryEngine()
    return _memory_engine