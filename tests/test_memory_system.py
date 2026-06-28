"""
Agent OS V6.0 - Memory System Tests
Unit tests for MemoryEntry, Session, MemoryStore, MemoryEngine, MemoryService
"""
import pytest
import asyncio

from agent_os.config import get_config, MemoryConfig, set_config, AppConfig
from agent_os.core_platform.exceptions import (
    ValidationException, NotFoundException,
)
from agent_os.core_platform.memory_system.models import (
    MemoryEntry, MemoryType, MemoryRole, Session,
    MemoryQueryResult, MemoryContext,
)
from agent_os.core_platform.memory_system.store import MemoryStore
from agent_os.core_platform.memory_system.engine import MemoryEngine, get_memory_engine
from agent_os.services.memory_service.service import MemoryService, get_memory_service


# ============================================================
# MemoryEntry Tests
# ============================================================

class TestMemoryEntry:
    """Tests for MemoryEntry model."""

    def test_create_entry(self):
        e = MemoryEntry(
            session_id="s1", tenant_id="t1",
            content="Hello world", role=MemoryRole.USER.value,
        )
        assert e.entry_id is not None
        assert e.session_id == "s1"
        assert e.memory_type == MemoryType.WORKING.value
        assert e.importance == 0.5

    def test_create_entry_semantic(self):
        e = MemoryEntry(
            tenant_id="t1",
            memory_type=MemoryType.SEMANTIC.value,
            content="Knowledge base entry",
            embedding=[0.1, 0.2, 0.3],
        )
        assert e.memory_type == MemoryType.SEMANTIC.value
        assert e.embedding == [0.1, 0.2, 0.3]

    def test_to_dict_basic(self):
        e = MemoryEntry(
            session_id="s1", tenant_id="t1",
            content="Hello", role="user",
        )
        d = e.to_dict()
        assert d["session_id"] == "s1"
        assert d["content"] == "Hello"
        assert d["role"] == "user"
        assert "embedding" not in d

    def test_to_dict_with_embedding(self):
        e = MemoryEntry(
            tenant_id="t1",
            memory_type=MemoryType.SEMANTIC.value,
            content="Knowledge",
            embedding=[1.0, 2.0, 3.0],
        )
        d = e.to_dict(include_embedding=True)
        assert d["embedding_dim"] == 3

    def test_to_dict_truncates_content(self):
        e = MemoryEntry(content="x" * 1000)
        d = e.to_dict()
        assert len(d["content"]) == 500

    def test_default_values(self):
        e = MemoryEntry()
        assert e.entry_id is not None
        assert e.memory_type == MemoryType.WORKING.value
        assert e.role == MemoryRole.USER.value
        assert e.importance == 0.5
        assert e.access_count == 0
        assert e.tags == []
        assert e.metadata == {}

    def test_importance_range(self):
        e = MemoryEntry(importance=0.0)
        assert e.importance == 0.0
        e = MemoryEntry(importance=1.0)
        assert e.importance == 1.0

    def test_tags(self):
        e = MemoryEntry(tags=["python", "ai", "knowledge"])
        assert "python" in e.tags
        assert "ai" in e.tags
        assert len(e.tags) == 3


# ============================================================
# Session Tests
# ============================================================

class TestSession:
    """Tests for Session model."""

    def test_create_session(self):
        s = Session(tenant_id="t1", user_id="u1", agent_id="a1")
        assert s.session_id is not None
        assert s.tenant_id == "t1"
        assert s.status == "active"
        assert s.total_interactions == 0

    def test_to_dict(self):
        s = Session(
            tenant_id="t1", user_id="u1", agent_id="a1",
            title="Test Session", status="active",
        )
        d = s.to_dict()
        assert d["session_id"] == s.session_id
        assert d["tenant_id"] == "t1"
        assert d["title"] == "Test Session"
        assert d["status"] == "active"
        assert d["total_interactions"] == 0

    def test_session_with_metadata(self):
        s = Session(
            tenant_id="t1",
            metadata={"source": "api", "version": "1.0"},
        )
        d = s.to_dict()
        assert d["metadata"]["source"] == "api"


# ============================================================
# MemoryQueryResult Tests
# ============================================================

class TestMemoryQueryResult:
    """Tests for MemoryQueryResult model."""

    def test_empty_result(self):
        r = MemoryQueryResult(query="test")
        assert r.query == "test"
        assert r.total_found == 0
        assert r.working_memories == []
        assert r.episodic_memories == []
        assert r.semantic_memories == []

    def test_to_dict(self):
        e1 = MemoryEntry(content="Hello", session_id="s1")
        e2 = MemoryEntry(content="World", session_id="s1")
        r = MemoryQueryResult(
            query="test",
            working_memories=[e1],
            episodic_memories=[e2],
            total_found=2,
            latency_ms=5.5,
        )
        d = r.to_dict()
        assert d["total_found"] == 2
        assert d["latency_ms"] == 5.5
        assert len(d["working_memories"]) == 1
        assert len(d["episodic_memories"]) == 1


# ============================================================
# MemoryContext Tests
# ============================================================

class TestMemoryContext:
    """Tests for MemoryContext model."""

    def test_empty_context(self):
        c = MemoryContext()
        assert c.entries == []
        assert c.context_text == ""
        assert c.source_layers == []

    def test_to_dict(self):
        e1 = MemoryEntry(content="Hello", role="user")
        c = MemoryContext(
            entries=[e1],
            context_text="[user]: Hello",
            source_layers=["working"],
        )
        d = c.to_dict()
        assert d["total_entries"] == 1
        assert "working" in d["source_layers"]
        assert len(d["context_text"]) <= 1000


# ============================================================
# MemoryType / MemoryRole Tests
# ============================================================

class TestMemoryEnums:
    """Tests for MemoryType and MemoryRole enums."""

    def test_memory_types(self):
        assert MemoryType.WORKING.value == "working"
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"

    def test_memory_roles(self):
        assert MemoryRole.USER.value == "user"
        assert MemoryRole.ASSISTANT.value == "assistant"
        assert MemoryRole.SYSTEM.value == "system"
        assert MemoryRole.TOOL.value == "tool"


# ============================================================
# MemoryStore Tests
# ============================================================

class TestMemoryStore:
    """Tests for MemoryStore (in-memory backend)."""

    @pytest.fixture
    def store(self):
        s = MemoryStore(backend="memory")
        s._working.clear()
        s._episodic.clear()
        s._semantic.clear()
        s._sessions.clear()
        return s

    # ── Session Management ──────────────────────────

    @pytest.mark.asyncio
    async def test_create_session(self, store):
        s = Session(tenant_id="t1", user_id="u1")
        result = await store.create_session(s)
        assert result.session_id == s.session_id
        assert result.session_id in store._sessions
        assert result.session_id in store._working

    @pytest.mark.asyncio
    async def test_get_session(self, store):
        s = Session(tenant_id="t1", user_id="u1")
        await store.create_session(s)
        fetched = await store.get_session(s.session_id)
        assert fetched is not None
        assert fetched.tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, store):
        result = await store.get_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_session(self, store):
        s = Session(tenant_id="t1", title="Old")
        await store.create_session(s)
        updated = await store.update_session(s.session_id, title="New", status="paused")
        assert updated is not None
        assert updated.title == "New"
        assert updated.status == "paused"

    @pytest.mark.asyncio
    async def test_update_session_not_found(self, store):
        result = await store.update_session("nonexistent", title="x")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session(self, store):
        s = Session(tenant_id="t1")
        await store.create_session(s)
        result = await store.delete_session(s.session_id)
        assert result is True
        assert s.session_id not in store._sessions

    @pytest.mark.asyncio
    async def test_list_sessions(self, store):
        s1 = Session(tenant_id="t1", user_id="u1")
        s2 = Session(tenant_id="t1", user_id="u2")
        s3 = Session(tenant_id="t2", user_id="u3")
        await store.create_session(s1)
        await store.create_session(s2)
        await store.create_session(s3)

        t1_sessions = await store.list_sessions("t1")
        assert len(t1_sessions) == 2
        t2_sessions = await store.list_sessions("t2")
        assert len(t2_sessions) == 1

    # ── Working Memory ──────────────────────────────

    @pytest.mark.asyncio
    async def test_add_working(self, store):
        s = Session(tenant_id="t1")
        await store.create_session(s)
        e = MemoryEntry(session_id=s.session_id, content="Hello")
        result = await store.add_working(s.session_id, e)
        assert result is not None
        assert len(store._working[s.session_id]) == 1

    @pytest.mark.asyncio
    async def test_get_working(self, store):
        s = Session(tenant_id="t1")
        await store.create_session(s)
        for i in range(5):
            await store.add_working(s.session_id, MemoryEntry(content=f"msg{i}"))

        entries = await store.get_working(s.session_id, limit=3)
        assert len(entries) == 3
        assert entries[-1].content == "msg4"

    @pytest.mark.asyncio
    async def test_working_capacity_limit(self, store):
        s = Session(tenant_id="t1")
        await store.create_session(s)
        cap = store._config.working_memory_capacity

        for i in range(cap + 5):
            await store.add_working(s.session_id, MemoryEntry(content=f"msg{i}"))

        entries = await store.get_working(s.session_id, limit=100)
        assert len(entries) == cap

    @pytest.mark.asyncio
    async def test_clear_working(self, store):
        s = Session(tenant_id="t1")
        await store.create_session(s)
        await store.add_working(s.session_id, MemoryEntry(content="msg"))
        await store.clear_working(s.session_id)
        entries = await store.get_working(s.session_id)
        assert len(entries) == 0

    # ── Episodic Memory ─────────────────────────────

    @pytest.mark.asyncio
    async def test_add_episodic(self, store):
        s = Session(tenant_id="t1")
        await store.create_session(s)
        e = MemoryEntry(
            session_id=s.session_id,
            memory_type=MemoryType.EPISODIC.value,
            content="Episode 1",
        )
        result = await store.add_episodic(s.session_id, e)
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_episodic(self, store):
        s = Session(tenant_id="t1")
        await store.create_session(s)
        for i in range(10):
            await store.add_episodic(
                s.session_id,
                MemoryEntry(memory_type=MemoryType.EPISODIC.value, content=f"ep{i}"),
            )

        entries = await store.get_episodic(s.session_id, limit=3)
        assert len(entries) == 3

    @pytest.mark.asyncio
    async def test_search_episodic(self, store):
        s = Session(tenant_id="t1")
        await store.create_session(s)
        await store.add_episodic(
            s.session_id,
            MemoryEntry(memory_type=MemoryType.EPISODIC.value, content="Python is great"),
        )
        await store.add_episodic(
            s.session_id,
            MemoryEntry(memory_type=MemoryType.EPISODIC.value, content="Java is verbose"),
        )

        results = await store.search_episodic(s.session_id, "python")
        assert len(results) == 1
        assert "Python" in results[0].content

    @pytest.mark.asyncio
    async def test_search_episodic_by_tag(self, store):
        s = Session(tenant_id="t1")
        await store.create_session(s)
        await store.add_episodic(
            s.session_id,
            MemoryEntry(
                memory_type=MemoryType.EPISODIC.value,
                content="Some content",
                tags=["important", "python"],
            ),
        )

        results = await store.search_episodic(s.session_id, "important")
        assert len(results) == 1

    # ── Semantic Memory ─────────────────────────────

    @pytest.mark.asyncio
    async def test_add_semantic(self, store):
        e = MemoryEntry(
            tenant_id="t1",
            memory_type=MemoryType.SEMANTIC.value,
            content="Knowledge",
            embedding=[0.1, 0.2, 0.3],
        )
        result = await store.add_semantic(e)
        assert result is not None
        assert result.entry_id in store._semantic

    @pytest.mark.asyncio
    async def test_get_semantic(self, store):
        e = MemoryEntry(
            tenant_id="t1",
            memory_type=MemoryType.SEMANTIC.value,
            content="Knowledge",
            embedding=[0.1, 0.2, 0.3],
        )
        await store.add_semantic(e)
        fetched = await store.get_semantic(e.entry_id)
        assert fetched is not None
        assert fetched.access_count == 1

    @pytest.mark.asyncio
    async def test_get_semantic_not_found(self, store):
        result = await store.get_semantic("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_semantic_cosine(self, store):
        e1 = MemoryEntry(
            tenant_id="t1",
            memory_type=MemoryType.SEMANTIC.value,
            content="Python programming",
            embedding=[1.0, 0.0, 0.0],
        )
        e2 = MemoryEntry(
            tenant_id="t1",
            memory_type=MemoryType.SEMANTIC.value,
            content="Cooking recipes",
            embedding=[0.0, 1.0, 0.0],
        )
        await store.add_semantic(e1)
        await store.add_semantic(e2)

        # Query with embedding similar to e1
        results = await store.search_semantic(
            query_embedding=[1.0, 0.0, 0.0],
            tenant_id="t1",
            top_k=2,
            threshold=0.0,
        )
        assert len(results) == 2
        # First result should be most similar
        assert "Python" in results[0].content

    @pytest.mark.asyncio
    async def test_search_semantic_threshold(self, store):
        e1 = MemoryEntry(
            tenant_id="t1",
            memory_type=MemoryType.SEMANTIC.value,
            content="Python",
            embedding=[1.0, 0.0],
        )
        await store.add_semantic(e1)

        # Query with orthogonal embedding (cos_sim ≈ 0)
        results = await store.search_semantic(
            query_embedding=[0.0, 1.0],
            tenant_id="t1",
            threshold=0.5,
        )
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_semantic_by_text(self, store):
        e1 = MemoryEntry(
            tenant_id="t1",
            memory_type=MemoryType.SEMANTIC.value,
            content="Python is a programming language",
        )
        await store.add_semantic(e1)

        results = await store.search_semantic_by_text("programming", tenant_id="t1")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_delete_semantic(self, store):
        e = MemoryEntry(
            tenant_id="t1",
            memory_type=MemoryType.SEMANTIC.value,
            content="To delete",
        )
        await store.add_semantic(e)
        result = await store.delete_semantic(e.entry_id)
        assert result is True
        assert e.entry_id not in store._semantic

    @pytest.mark.asyncio
    async def test_semantic_capacity_limit(self, store):
        cap = store._config.semantic_memory_capacity
        for i in range(cap + 5):
            await store.add_semantic(
                MemoryEntry(
                    tenant_id="t1",
                    memory_type=MemoryType.SEMANTIC.value,
                    content=f"entry_{i}",
                )
            )
        assert len(store._semantic) == cap

    # ── Consolidation ───────────────────────────────

    @pytest.mark.asyncio
    async def test_consolidate_to_semantic(self, store):
        e = MemoryEntry(
            session_id="s1",
            tenant_id="t1",
            memory_type=MemoryType.EPISODIC.value,
            content="Important knowledge",
            importance=0.9,
            embedding=[0.5, 0.5],
        )
        result = await store.consolidate_to_semantic(e)
        assert result is not None
        assert result.memory_type == MemoryType.SEMANTIC.value
        assert result.content == "Important knowledge"

    # ── Cosine Similarity ───────────────────────────

    def test_cosine_similarity_identical(self):
        sim = MemoryStore._cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert abs(sim - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self):
        sim = MemoryStore._cosine_similarity([1.0, 0.0], [0.0, 1.0])
        assert abs(sim - 0.0) < 0.001

    def test_cosine_similarity_opposite(self):
        sim = MemoryStore._cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert abs(sim + 1.0) < 0.001

    def test_cosine_similarity_different_length(self):
        sim = MemoryStore._cosine_similarity([1.0, 2.0], [1.0])
        assert sim == 0.0

    def test_cosine_similarity_empty(self):
        sim = MemoryStore._cosine_similarity([], [])
        assert sim == 0.0

    def test_cosine_similarity_zero_vector(self):
        sim = MemoryStore._cosine_similarity([0.0, 0.0], [1.0, 2.0])
        assert sim == 0.0

    # ── Stats & Health ──────────────────────────────

    @pytest.mark.asyncio
    async def test_get_stats(self, store):
        s = Session(tenant_id="t1")
        await store.create_session(s)
        await store.add_working(s.session_id, MemoryEntry(content="w1", tenant_id="t1"))
        await store.add_episodic(s.session_id, MemoryEntry(
            memory_type=MemoryType.EPISODIC.value, content="e1", tenant_id="t1",
        ))

        stats = await store.get_stats("t1")
        assert stats["working_memories"] == 1
        assert stats["episodic_memories"] == 1
        assert stats["active_sessions"] == 1
        assert stats["backend"] == "memory"

    @pytest.mark.asyncio
    async def test_health_check(self, store):
        hc = await store.health_check()
        assert hc["status"] == "healthy"
        assert hc["service"] == "MemoryStore"


# ============================================================
# MemoryEngine Tests
# ============================================================

class TestMemoryEngine:
    """Tests for MemoryEngine (three-layer memory)."""

    @pytest.fixture
    def engine(self):
        cfg = AppConfig()
        set_config(cfg)
        e = MemoryEngine()
        e._store._working.clear()
        e._store._episodic.clear()
        e._store._semantic.clear()
        e._store._sessions.clear()
        return e

    # ── Session Management ──────────────────────────

    @pytest.mark.asyncio
    async def test_create_session(self, engine):
        s = await engine.create_session(
            tenant_id="t1", user_id="u1", agent_id="a1", title="Test",
        )
        assert s.session_id is not None
        assert s.tenant_id == "t1"
        assert s.total_interactions == 0

    @pytest.mark.asyncio
    async def test_get_session(self, engine):
        s = await engine.create_session(tenant_id="t1", user_id="u1")
        fetched = await engine.get_session(s.session_id)
        assert fetched is not None
        assert fetched.tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_update_session(self, engine):
        s = await engine.create_session(tenant_id="t1")
        updated = await engine.update_session(s.session_id, title="Updated", status="paused")
        assert updated.title == "Updated"
        assert updated.status == "paused"

    @pytest.mark.asyncio
    async def test_delete_session(self, engine):
        s = await engine.create_session(tenant_id="t1")
        result = await engine.delete_session(s.session_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_list_sessions(self, engine):
        await engine.create_session(tenant_id="t1", user_id="u1")
        await engine.create_session(tenant_id="t1", user_id="u2")
        await engine.create_session(tenant_id="t2", user_id="u3")

        t1 = await engine.list_sessions("t1")
        assert len(t1) == 2

    # ── Working Memory ──────────────────────────────

    @pytest.mark.asyncio
    async def test_add_to_working(self, engine):
        s = await engine.create_session(tenant_id="t1")
        e = await engine.add_to_working(
            session_id=s.session_id, content="Hello",
            role="user", tenant_id="t1",
        )
        assert e.content == "Hello"
        assert e.memory_type == MemoryType.WORKING.value

    @pytest.mark.asyncio
    async def test_add_to_working_auto_episodic(self, engine):
        """Adding to working should auto-consolidate to episodic."""
        s = await engine.create_session(tenant_id="t1")
        await engine.add_to_working(
            session_id=s.session_id, content="Hello", tenant_id="t1",
        )
        episodic = await engine.get_episodic_history(s.session_id)
        assert len(episodic) == 1

    @pytest.mark.asyncio
    async def test_add_to_working_batch(self, engine):
        s = await engine.create_session(tenant_id="t1")
        entries = await engine.add_to_working_batch(
            session_id=s.session_id,
            messages=[
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            tenant_id="t1",
        )
        assert len(entries) == 2
        assert entries[0].role == "user"

    @pytest.mark.asyncio
    async def test_get_working_context(self, engine):
        s = await engine.create_session(tenant_id="t1")
        await engine.add_to_working(session_id=s.session_id, content="msg1", tenant_id="t1")
        await engine.add_to_working(session_id=s.session_id, content="msg2", tenant_id="t1")

        ctx = await engine.get_working_context(s.session_id)
        assert len(ctx) == 2

    @pytest.mark.asyncio
    async def test_clear_working(self, engine):
        s = await engine.create_session(tenant_id="t1")
        await engine.add_to_working(session_id=s.session_id, content="msg", tenant_id="t1")
        await engine.clear_working(s.session_id)
        ctx = await engine.get_working_context(s.session_id)
        assert len(ctx) == 0

    # ── Episodic Memory ─────────────────────────────

    @pytest.mark.asyncio
    async def test_add_to_episodic(self, engine):
        s = await engine.create_session(tenant_id="t1")
        e = await engine.add_to_episodic(
            session_id=s.session_id, content="Episode",
            role="user", tenant_id="t1",
        )
        assert e.memory_type == MemoryType.EPISODIC.value

    @pytest.mark.asyncio
    async def test_get_episodic_history(self, engine):
        s = await engine.create_session(tenant_id="t1")
        for i in range(5):
            await engine.add_to_episodic(
                session_id=s.session_id, content=f"ep{i}", tenant_id="t1",
            )

        history = await engine.get_episodic_history(s.session_id, limit=3)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_search_episodic(self, engine):
        s = await engine.create_session(tenant_id="t1")
        await engine.add_to_episodic(
            session_id=s.session_id, content="Python programming", tenant_id="t1",
        )
        await engine.add_to_episodic(
            session_id=s.session_id, content="Java development", tenant_id="t1",
        )

        results = await engine.search_episodic(s.session_id, "python")
        assert len(results) == 1

    # ── Semantic Memory ─────────────────────────────

    @pytest.mark.asyncio
    async def test_add_to_semantic(self, engine):
        e = await engine.add_to_semantic(
            content="Python is a language", tenant_id="t1",
            tags=["python"],
        )
        assert e.memory_type == MemoryType.SEMANTIC.value
        assert e.embedding is not None  # Hash embedding should be generated

    @pytest.mark.asyncio
    async def test_add_to_semantic_no_embed(self, engine):
        e = await engine.add_to_semantic(
            content="No embedding", tenant_id="t1", embed=False,
        )
        assert e.embedding is None

    @pytest.mark.asyncio
    async def test_search_semantic(self, engine):
        await engine.add_to_semantic(
            content="Python is a programming language",
            tenant_id="t1", tags=["python"],
        )
        await engine.add_to_semantic(
            content="Cooking is an art",
            tenant_id="t1", tags=["cooking"],
        )

        results = await engine.search_semantic("programming", tenant_id="t1")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_semantic_entry(self, engine):
        e = await engine.add_to_semantic(content="Knowledge", tenant_id="t1")
        fetched = await engine.get_semantic_entry(e.entry_id)
        assert fetched is not None
        assert fetched.content == "Knowledge"

    @pytest.mark.asyncio
    async def test_delete_semantic_entry(self, engine):
        e = await engine.add_to_semantic(content="Temp", tenant_id="t1")
        result = await engine.delete_semantic_entry(e.entry_id)
        assert result is True

    # ── Consolidation ───────────────────────────────

    @pytest.mark.asyncio
    async def test_consolidate_episodic_to_semantic(self, engine):
        s = await engine.create_session(tenant_id="t1")
        ep = await engine.add_to_episodic(
            session_id=s.session_id, content="Important fact",
            tenant_id="t1", importance=0.9,
        )
        result = await engine.consolidate_episodic_to_semantic(
            s.session_id, ep.entry_id,
        )
        assert result is not None
        assert result.memory_type == MemoryType.SEMANTIC.value

    @pytest.mark.asyncio
    async def test_auto_consolidate(self, engine):
        s = await engine.create_session(tenant_id="t1")
        # Add entries with high access count and importance
        for i in range(10):
            e = await engine.add_to_episodic(
                session_id=s.session_id,
                content=f"Important fact {i}",
                tenant_id="t1",
                importance=0.9,
            )
            # Manually increase access count
            e.access_count = 10

        result = await engine.auto_consolidate(s.session_id)
        assert len(result) >= 0  # Should not error

    # ── Query & Context ─────────────────────────────

    @pytest.mark.asyncio
    async def test_query(self, engine):
        s = await engine.create_session(tenant_id="t1")
        await engine.add_to_working(
            session_id=s.session_id, content="Hello", tenant_id="t1",
        )
        await engine.add_to_semantic(
            content="Python programming", tenant_id="t1",
        )

        result = await engine.query(s.session_id, "python", tenant_id="t1")
        assert result.total_found >= 1
        assert result.query == "python"
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_query_layers_filter(self, engine):
        s = await engine.create_session(tenant_id="t1")
        await engine.add_to_working(
            session_id=s.session_id, content="Hello", tenant_id="t1",
        )

        # Only working
        result = await engine.query(
            s.session_id, "hello", tenant_id="t1",
            include_episodic=False, include_semantic=False,
        )
        assert len(result.working_memories) >= 1
        assert len(result.episodic_memories) == 0
        assert len(result.semantic_memories) == 0

    @pytest.mark.asyncio
    async def test_assemble_context(self, engine):
        s = await engine.create_session(tenant_id="t1")
        await engine.add_to_working(
            session_id=s.session_id, content="User: Hello", role="user", tenant_id="t1",
        )
        await engine.add_to_working(
            session_id=s.session_id, content="Assistant: Hi", role="assistant", tenant_id="t1",
        )

        ctx = await engine.assemble_context(s.session_id, query="hello", tenant_id="t1")
        assert ctx.entries is not None
        assert len(ctx.entries) >= 2
        assert "working" in ctx.source_layers
        assert len(ctx.context_text) > 0

    # ── Stats & Health ──────────────────────────────

    @pytest.mark.asyncio
    async def test_get_stats(self, engine):
        s = await engine.create_session(tenant_id="t1")
        await engine.add_to_working(session_id=s.session_id, content="msg", tenant_id="t1")

        stats = await engine.get_stats("t1")
        assert stats["working_memories"] >= 1
        assert stats["active_sessions"] >= 1

    @pytest.mark.asyncio
    async def test_health_check(self, engine):
        hc = await engine.health_check()
        assert hc["status"] == "healthy"


# ============================================================
# MemoryService Tests
# ============================================================

class TestMemoryService:
    """Tests for MemoryService (service layer with validation)."""

    @pytest.fixture
    def service(self):
        cfg = AppConfig()
        set_config(cfg)
        svc = MemoryService()
        svc._engine._store._working.clear()
        svc._engine._store._episodic.clear()
        svc._engine._store._semantic.clear()
        svc._engine._store._sessions.clear()
        return svc

    # ── Session Management ──────────────────────────

    @pytest.mark.asyncio
    async def test_create_session(self, service):
        s = await service.create_session(
            tenant_id="t1", user_id="u1", agent_id="a1", title="Test",
        )
        assert "session_id" in s
        assert s["tenant_id"] == "t1"

    @pytest.mark.asyncio
    async def test_get_session(self, service):
        s = await service.create_session(tenant_id="t1", user_id="u1")
        fetched = await service.get_session(s["session_id"])
        assert fetched["tenant_id"] == "t1"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, service):
        with pytest.raises(NotFoundException):
            await service.get_session("nonexistent")

    @pytest.mark.asyncio
    async def test_update_session(self, service):
        s = await service.create_session(tenant_id="t1")
        updated = await service.update_session(
            s["session_id"], title="New", status="completed",
        )
        assert updated["title"] == "New"
        assert updated["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_session_not_found(self, service):
        with pytest.raises(NotFoundException):
            await service.update_session("nonexistent", title="x")

    @pytest.mark.asyncio
    async def test_delete_session(self, service):
        s = await service.create_session(tenant_id="t1")
        result = await service.delete_session(s["session_id"])
        assert result["deleted"] is True

    @pytest.mark.asyncio
    async def test_list_sessions(self, service):
        await service.create_session(tenant_id="t1", user_id="u1")
        await service.create_session(tenant_id="t1", user_id="u2")

        sessions = await service.list_sessions("t1")
        assert len(sessions) == 2

    # ── Working Memory ──────────────────────────────

    @pytest.mark.asyncio
    async def test_add_to_working(self, service):
        s = await service.create_session(tenant_id="t1")
        e = await service.add_to_working(
            session_id=s["session_id"], content="Hello",
            role="user", tenant_id="t1",
        )
        assert e["content"] == "Hello"
        assert e["role"] == "user"

    @pytest.mark.asyncio
    async def test_add_to_working_empty_content(self, service):
        s = await service.create_session(tenant_id="t1")
        with pytest.raises(ValidationException):
            await service.add_to_working(
                session_id=s["session_id"], content="", tenant_id="t1",
            )

    @pytest.mark.asyncio
    async def test_add_to_working_batch(self, service):
        s = await service.create_session(tenant_id="t1")
        batch = await service.add_to_working_batch(
            session_id=s["session_id"],
            messages=[
                {"role": "user", "content": "Question"},
                {"role": "assistant", "content": "Answer"},
            ],
            tenant_id="t1",
        )
        assert len(batch) == 2

    @pytest.mark.asyncio
    async def test_add_to_working_batch_empty(self, service):
        s = await service.create_session(tenant_id="t1")
        with pytest.raises(ValidationException):
            await service.add_to_working_batch(
                session_id=s["session_id"], messages=[], tenant_id="t1",
            )

    @pytest.mark.asyncio
    async def test_get_working_context(self, service):
        s = await service.create_session(tenant_id="t1")
        await service.add_to_working(
            session_id=s["session_id"], content="msg1", tenant_id="t1",
        )
        ctx = await service.get_working_context(s["session_id"])
        assert len(ctx) == 1

    @pytest.mark.asyncio
    async def test_clear_working(self, service):
        s = await service.create_session(tenant_id="t1")
        await service.add_to_working(
            session_id=s["session_id"], content="msg", tenant_id="t1",
        )
        result = await service.clear_working(s["session_id"])
        assert result["cleared"] is True

    # ── Episodic Memory ─────────────────────────────

    @pytest.mark.asyncio
    async def test_add_to_episodic(self, service):
        s = await service.create_session(tenant_id="t1")
        e = await service.add_to_episodic(
            session_id=s["session_id"], content="Episode", tenant_id="t1",
        )
        assert e["memory_type"] == MemoryType.EPISODIC.value

    @pytest.mark.asyncio
    async def test_get_episodic_history(self, service):
        s = await service.create_session(tenant_id="t1")
        for i in range(3):
            await service.add_to_episodic(
                session_id=s["session_id"], content=f"ep{i}", tenant_id="t1",
            )
        history = await service.get_episodic_history(s["session_id"], limit=2)
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_search_episodic(self, service):
        s = await service.create_session(tenant_id="t1")
        await service.add_to_episodic(
            session_id=s["session_id"], content="Python is fun", tenant_id="t1",
        )
        results = await service.search_episodic(s["session_id"], "python")
        assert len(results) == 1

    # ── Semantic Memory ─────────────────────────────

    @pytest.mark.asyncio
    async def test_add_to_semantic(self, service):
        e = await service.add_to_semantic(
            content="Knowledge base", tenant_id="t1", tags=["kb"],
        )
        assert e["memory_type"] == MemoryType.SEMANTIC.value
        assert "embedding_dim" in e

    @pytest.mark.asyncio
    async def test_add_to_semantic_empty(self, service):
        with pytest.raises(ValidationException):
            await service.add_to_semantic(content="", tenant_id="t1")

    @pytest.mark.asyncio
    async def test_search_semantic(self, service):
        await service.add_to_semantic(content="Python programming", tenant_id="t1")
        await service.add_to_semantic(content="Cooking recipes", tenant_id="t1")

        results = await service.search_semantic("programming", tenant_id="t1")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_semantic_entry(self, service):
        e = await service.add_to_semantic(content="Knowledge", tenant_id="t1")
        fetched = await service.get_semantic_entry(e["entry_id"])
        assert fetched["content"] == "Knowledge"

    @pytest.mark.asyncio
    async def test_get_semantic_entry_not_found(self, service):
        with pytest.raises(NotFoundException):
            await service.get_semantic_entry("nonexistent")

    @pytest.mark.asyncio
    async def test_delete_semantic_entry(self, service):
        e = await service.add_to_semantic(content="Temp", tenant_id="t1")
        result = await service.delete_semantic_entry(e["entry_id"])
        assert result["deleted"] is True

    # ── Query & Context ─────────────────────────────

    @pytest.mark.asyncio
    async def test_query(self, service):
        s = await service.create_session(tenant_id="t1")
        await service.add_to_working(
            session_id=s["session_id"], content="Hello world", tenant_id="t1",
        )
        await service.add_to_semantic(content="Python knowledge", tenant_id="t1")

        result = await service.query(s["session_id"], "python", tenant_id="t1")
        assert result["total_found"] >= 1
        assert "working_memories" in result
        assert "episodic_memories" in result
        assert "semantic_memories" in result

    @pytest.mark.asyncio
    async def test_query_empty(self, service):
        s = await service.create_session(tenant_id="t1")
        with pytest.raises(ValidationException):
            await service.query(s["session_id"], "", tenant_id="t1")

    @pytest.mark.asyncio
    async def test_assemble_context(self, service):
        s = await service.create_session(tenant_id="t1")
        await service.add_to_working(
            session_id=s["session_id"], content="User: Hi", role="user", tenant_id="t1",
        )
        await service.add_to_working(
            session_id=s["session_id"], content="AI: Hello", role="assistant", tenant_id="t1",
        )

        ctx = await service.assemble_context(s["session_id"], query="hi", tenant_id="t1")
        assert ctx["total_entries"] >= 2
        assert "working" in ctx["source_layers"]

    # ── Consolidation ───────────────────────────────

    @pytest.mark.asyncio
    async def test_consolidate_episodic_to_semantic(self, service):
        s = await service.create_session(tenant_id="t1")
        ep = await service.add_to_episodic(
            session_id=s["session_id"], content="Important", tenant_id="t1",
        )
        result = await service.consolidate_episodic_to_semantic(
            s["session_id"], ep["entry_id"],
        )
        assert "entry_id" in result

    @pytest.mark.asyncio
    async def test_auto_consolidate(self, service):
        s = await service.create_session(tenant_id="t1")
        for i in range(5):
            await service.add_to_episodic(
                session_id=s["session_id"], content=f"Fact {i}", tenant_id="t1",
            )

        result = await service.auto_consolidate(s["session_id"])
        assert "consolidated" in result
        assert "session_id" in result

    # ── Stats & Health ──────────────────────────────

    @pytest.mark.asyncio
    async def test_get_stats(self, service):
        s = await service.create_session(tenant_id="t1")
        await service.add_to_working(
            session_id=s["session_id"], content="msg", tenant_id="t1",
        )
        stats = await service.get_stats("t1")
        assert stats["working_memories"] >= 1
        assert stats["active_sessions"] >= 1

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        hc = await service.health_check()
        assert hc["status"] == "healthy"
        assert hc["service"] == "MemoryService"
        assert hc["backend"] == "memory"

    # ── Singleton Tests ─────────────────────────────

    def test_get_memory_service_singleton(self):
        svc1 = get_memory_service()
        svc2 = get_memory_service()
        assert svc1 is svc2

    def test_get_memory_engine_singleton(self):
        e1 = get_memory_engine()
        e2 = get_memory_engine()
        assert e1 is e2


# ============================================================
# Integration Tests
# ============================================================

class TestMemoryIntegration:
    """End-to-end integration tests for the memory system."""

    @pytest.fixture
    def service(self):
        cfg = AppConfig()
        set_config(cfg)
        svc = MemoryService()
        svc._engine._store._working.clear()
        svc._engine._store._episodic.clear()
        svc._engine._store._semantic.clear()
        svc._engine._store._sessions.clear()
        return svc

    @pytest.mark.asyncio
    async def test_full_workflow(self, service):
        """Test complete memory workflow: session → working → episodic → semantic."""
        # 1. Create session
        session = await service.create_session(
            tenant_id="t1", user_id="u1", agent_id="a1",
            title="Integration Test",
        )
        sid = session["session_id"]

        # 2. Add conversation turns to working memory
        await service.add_to_working(
            session_id=sid, content="What is Python?",
            role="user", tenant_id="t1",
        )
        await service.add_to_working(
            session_id=sid, content="Python is a programming language.",
            role="assistant", tenant_id="t1",
        )
        await service.add_to_working(
            session_id=sid, content="How do I print hello?",
            role="user", tenant_id="t1",
        )
        await service.add_to_working(
            session_id=sid, content="Use print('hello')",
            role="assistant", tenant_id="t1",
        )

        # 3. Verify working memory
        working = await service.get_working_context(sid)
        assert len(working) == 4

        # 4. Verify episodic auto-consolidation
        episodic = await service.get_episodic_history(sid)
        assert len(episodic) == 4

        # 5. Add to semantic memory
        await service.add_to_semantic(
            content="Python print() function outputs text to console.",
            tenant_id="t1", tags=["python", "print"],
        )
        await service.add_to_semantic(
            content="Python is created by Guido van Rossum.",
            tenant_id="t1", tags=["python", "history"],
        )

        # 6. Search semantic memory
        results = await service.search_semantic("print", tenant_id="t1")
        assert len(results) >= 1

        # 7. Cross-layer query
        qr = await service.query(sid, "python", tenant_id="t1")
        assert qr["total_found"] >= 1

        # 8. Assemble context
        ctx = await service.assemble_context(sid, query="python", tenant_id="t1")
        assert ctx["total_entries"] >= 1

        # 9. Stats
        stats = await service.get_stats("t1")
        assert stats["working_memories"] == 4
        assert stats["episodic_memories"] == 4
        assert stats["semantic_memories"] == 2

        # 10. Cleanup
        result = await service.delete_session(sid)
        assert result["deleted"] is True

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, service):
        """Test that tenants are properly isolated."""
        # Tenant 1
        s1 = await service.create_session(tenant_id="t1", user_id="u1")
        await service.add_to_working(
            session_id=s1["session_id"], content="T1 data", tenant_id="t1",
        )
        await service.add_to_semantic(content="T1 knowledge", tenant_id="t1")

        # Tenant 2
        s2 = await service.create_session(tenant_id="t2", user_id="u2")
        await service.add_to_working(
            session_id=s2["session_id"], content="T2 data", tenant_id="t2",
        )
        await service.add_to_semantic(content="T2 knowledge", tenant_id="t2")

        # Query T1 semantic
        t1_results = await service.search_semantic("T1", tenant_id="t1")
        assert len(t1_results) == 1

        # Query T2 semantic
        t2_results = await service.search_semantic("T2", tenant_id="t2")
        assert len(t2_results) == 1

        # T1 sessions
        t1_sessions = await service.list_sessions("t1")
        assert len(t1_sessions) == 1

        # T2 sessions
        t2_sessions = await service.list_sessions("t2")
        assert len(t2_sessions) == 1

        # Stats per tenant
        t1_stats = await service.get_stats("t1")
        t2_stats = await service.get_stats("t2")
        assert t1_stats["semantic_memories"] == 1
        assert t2_stats["semantic_memories"] == 1

    @pytest.mark.asyncio
    async def test_working_memory_overflow(self, service):
        """Test that working memory respects capacity limits."""
        s = await service.create_session(tenant_id="t1")
        cfg = get_config().memory
        cap = cfg.working_memory_capacity

        # Add more than capacity
        for i in range(cap + 10):
            await service.add_to_working(
                session_id=s["session_id"], content=f"msg_{i}", tenant_id="t1",
            )

        ctx = await service.get_working_context(s["session_id"], limit=100)
        assert len(ctx) == cap
        # First messages should be evicted
        assert ctx[0]["content"] == f"msg_{10}"

    @pytest.mark.asyncio
    async def test_cosine_similarity_precision(self, service):
        """Test that cosine similarity returns correct ordering."""
        await service.add_to_semantic(
            content="Machine learning and AI",
            tenant_id="t1", tags=["ai", "ml"],
        )
        await service.add_to_semantic(
            content="Cooking Italian pasta",
            tenant_id="t1", tags=["cooking"],
        )
        await service.add_to_semantic(
            content="Deep learning neural networks",
            tenant_id="t1", tags=["ai", "dl"],
        )

        results = await service.search_semantic("artificial intelligence", tenant_id="t1")
        assert len(results) >= 1
        # AI-related entries should come first
        if len(results) >= 2:
            first_tags = results[0].get("tags", [])
            # Should have AI-related tags in top results
            assert any("ai" in t for t in first_tags) or "ai" in first_tags


# ============================================================
# Config Tests
# ============================================================

class TestMemoryConfig:
    """Tests for MemoryConfig."""

    def test_default_values(self):
        cfg = MemoryConfig()
        assert cfg.working_memory_capacity == 20
        assert cfg.episodic_memory_capacity == 1000
        assert cfg.semantic_memory_capacity == 10000
        assert cfg.embedding_dim == 128
        assert cfg.max_context_window == 10
        assert cfg.session_ttl_seconds == 3600
        assert cfg.cache_ttl_seconds == 300
        assert cfg.consolidation_threshold == 5
        assert cfg.backend == "memory"
        assert cfg.similarity_threshold == 0.3
        assert cfg.top_k_semantic == 5

    def test_in_app_config(self):
        cfg = AppConfig()
        assert cfg.memory is not None
        assert isinstance(cfg.memory, MemoryConfig)
        assert cfg.memory.working_memory_capacity == 20