"""
Agent OS V6.0 - Prompt Service Tests
Unit tests for PromptRenderer, PromptManager, and PromptService
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from agent_os.config import get_config, PromptConfig
from agent_os.core_platform.exceptions import (
    NotFoundException, ValidationException, ConflictException,
)
from agent_os.core_platform.prompt_center.template import (
    PromptTemplate, TemplateVariable, PromptVersion, PromptCategory,
    PromptRenderer, get_renderer,
)
from agent_os.core_platform.prompt_center.manager import (
    PromptManager, get_prompt_manager,
)
from agent_os.services.prompt_service.service import (
    PromptService, get_prompt_service,
)


# ============================================================
# PromptRenderer Tests
# ============================================================

class TestPromptRenderer:
    """Tests for the PromptRenderer template engine."""

    @pytest.fixture
    def renderer(self):
        return PromptRenderer()

    # ── Basic Variable Interpolation ──────────────────

    def test_render_simple_variable(self, renderer):
        result = renderer.render("Hello {{name}}!", {"name": "World"})
        assert result == "Hello World!"

    def test_render_multiple_variables(self, renderer):
        result = renderer.render(
            "{{greeting}} {{name}}, welcome to {{platform}}",
            {"greeting": "Hello", "name": "Alice", "platform": "AgentOS"},
        )
        assert result == "Hello Alice, welcome to AgentOS"

    def test_render_keep_placeholder_if_missing(self, renderer):
        result = renderer.render("Hello {{name}}!", {})
        assert result == "Hello {{name}}!"

    # ── Default Values ────────────────────────────────

    def test_render_default_value(self, renderer):
        result = renderer.render("Hello {{name|default:Guest}}!", {})
        assert result == "Hello Guest!"

    def test_render_default_value_not_used(self, renderer):
        result = renderer.render("Hello {{name|default:Guest}}!", {"name": "Alice"})
        assert result == "Hello Alice!"

    def test_render_default_value_with_spaces(self, renderer):
        result = renderer.render("{{status|default:active}}", {})
        assert result == "active"

    # ── Nested Access ─────────────────────────────────

    def test_render_nested_access(self, renderer):
        result = renderer.render(
            "{{user.name}} is {{user.age}} years old",
            {"user": {"name": "Alice", "age": 30}},
        )
        assert result == "Alice is 30 years old"

    def test_render_nested_missing_key(self, renderer):
        result = renderer.render(
            "{{user.name}} - {{user.email}}",
            {"user": {"name": "Alice"}},
        )
        assert result == "Alice - {{user.email}}"

    def test_render_nested_non_dict(self, renderer):
        result = renderer.render("{{items.0}}", {"items": ["a", "b", "c"]})
        assert "{{items.0}}" in result  # Not a dict, so keep placeholder

    # ── Conditionals ──────────────────────────────────

    def test_conditional_true(self, renderer):
        result = renderer.render("{% if show %}Visible{% endif %}", {"show": True})
        assert result == "Visible"

    def test_conditional_false(self, renderer):
        result = renderer.render("{% if show %}Visible{% endif %}", {"show": False})
        assert result == ""

    def test_conditional_truthy_value(self, renderer):
        result = renderer.render("{% if name %}Has name{% endif %}", {"name": "Alice"})
        assert result == "Has name"

    def test_conditional_none_value(self, renderer):
        result = renderer.render("{% if name %}Has name{% endif %}", {"name": None})
        assert result == ""

    def test_conditional_multiline(self, renderer):
        template = "{% if admin %}Admin Panel\nRestricted Area{% endif %}"
        result = renderer.render(template, {"admin": True})
        assert "Admin Panel" in result
        assert "Restricted Area" in result

    # ── For Loops ─────────────────────────────────────

    def test_for_loop(self, renderer):
        template = "{% for item in items %}{{item}}{% endfor %}"
        result = renderer.render(template, {"items": ["a", "b", "c"]})
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_for_loop_empty_list(self, renderer):
        template = "{% for item in items %}{{item}}{% endfor %}"
        result = renderer.render(template, {"items": []})
        assert result == ""

    def test_for_loop_non_list(self, renderer):
        template = "{% for item in items %}{{item}}{% endfor %}"
        result = renderer.render(template, {"items": "not_a_list"})
        assert result == ""

    def test_for_loop_with_variable(self, renderer):
        template = "{% for item in items %}- {{item}}\n{% endfor %}"
        result = renderer.render(template, {"items": ["x", "y"]})
        assert "- x" in result
        assert "- y" in result

    # ── Combined Features ─────────────────────────────

    def test_combined_conditional_and_variable(self, renderer):
        template = "{% if user %}Hello {{user.name}}{% endif %}"
        result = renderer.render(template, {"user": {"name": "Alice"}})
        assert result == "Hello Alice"

    def test_combined_loop_and_nested(self, renderer):
        template = "{% for u in users %}{{u.name}} ({{u.role}})\n{% endfor %}"
        result = renderer.render(template, {
            "users": [
                {"name": "Alice", "role": "admin"},
                {"name": "Bob", "role": "user"},
            ]
        })
        assert "Alice (admin)" in result
        assert "Bob (user)" in result

    # ── Extract Variables ─────────────────────────────

    def test_extract_variables(self, renderer):
        vars_list = renderer.extract_variables("{{name}} {{age}} {{name}}")
        assert vars_list == ["age", "name"]  # sorted, deduped

    def test_extract_variables_nested(self, renderer):
        vars_list = renderer.extract_variables("{{user.name}} {{user.email}} {{role}}")
        assert "user" in vars_list
        assert "role" in vars_list

    def test_extract_variables_empty(self, renderer):
        vars_list = renderer.extract_variables("No variables here")
        assert vars_list == []

    # ── Validate ──────────────────────────────────────

    def test_validate_valid(self, renderer):
        result = renderer.validate("Hello {{name}}!")
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_empty(self, renderer):
        result = renderer.validate("")
        assert result["valid"] is False
        assert any("empty" in e.lower() for e in result["errors"])

    def test_validate_too_long(self, renderer):
        result = renderer.validate("x" * 20000)
        assert result["valid"] is False
        assert any("max" in e.lower() for e in result["errors"])

    def test_validate_unclosed_tags(self, renderer):
        result = renderer.validate("Hello {{name")
        assert result["valid"] is False
        assert any("mismatch" in e.lower() for e in result["errors"])

    def test_validate_control_tags_warning(self, renderer):
        result = renderer.validate("{% if x %}incomplete {% endif")
        assert len(result["warnings"]) > 0

    def test_validate_extracts_variables(self, renderer):
        result = renderer.validate("Hello {{name}}, {{role}}")
        assert "name" in result["variables"]
        assert "role" in result["variables"]

    def test_validate_whitespace_only(self, renderer):
        result = renderer.validate("   ")
        assert result["valid"] is False

    # ── Edge Cases ────────────────────────────────────

    def test_render_empty_template(self, renderer):
        result = renderer.render("", {"name": "test"})
        assert result == ""

    def test_render_no_variables_in_template(self, renderer):
        result = renderer.render("Plain text", {"name": "test"})
        assert result == "Plain text"

    def test_render_special_characters(self, renderer):
        result = renderer.render("{{text}}", {"text": "Hello\nWorld\t!"})
        assert result == "Hello\nWorld\t!"

    def test_render_number_value(self, renderer):
        result = renderer.render("Count: {{count}}", {"count": 42})
        assert result == "Count: 42"

    def test_render_boolean_value(self, renderer):
        result = renderer.render("{{flag}}", {"flag": True})
        assert result == "True"

    def test_render_none_value(self, renderer):
        result = renderer.render("{{value}}", {"value": None})
        assert result == "{{value}}"  # None treated as missing


# ============================================================
# TemplateVariable Tests
# ============================================================

class TestTemplateVariable:
    """Tests for TemplateVariable model."""

    def test_create_variable(self):
        v = TemplateVariable(name="user_name", description="User name", required=True)
        assert v.name == "user_name"
        assert v.required is True

    def test_to_dict(self):
        v = TemplateVariable(
            name="count", description="Item count", default_value="0",
            required=False, var_type="number",
        )
        d = v.to_dict()
        assert d["name"] == "count"
        assert d["type"] == "number"
        assert d["default_value"] == "0"
        assert d["required"] is False


# ============================================================
# PromptVersion Tests
# ============================================================

class TestPromptVersion:
    """Tests for PromptVersion model."""

    def test_create_version(self):
        v = PromptVersion(version_number=1, content="Hello {{name}}")
        assert v.version_number == 1
        assert v.version_id is not None

    def test_to_dict(self):
        v = PromptVersion(
            version_number=2, content="Hi {{name}}",
            changelog="Updated greeting", created_by="admin",
        )
        d = v.to_dict()
        assert d["version_number"] == 2
        assert d["content"] == "Hi {{name}}"
        assert d["changelog"] == "Updated greeting"


# ============================================================
# PromptTemplate Tests
# ============================================================

class TestPromptTemplate:
    """Tests for PromptTemplate model."""

    def test_create_template(self):
        t = PromptTemplate(tenant_id="t1", name="greeting")
        assert t.template_id is not None
        assert t.tenant_id == "t1"
        assert t.name == "greeting"
        assert t.is_active is True
        assert t.current_version == 1

    def test_to_dict_basic(self):
        t = PromptTemplate(tenant_id="t1", name="test")
        d = t.to_dict()
        assert d["name"] == "test"
        assert "versions" not in d

    def test_to_dict_include_versions(self):
        t = PromptTemplate(
            tenant_id="t1", name="test",
            versions=[PromptVersion(version_number=1, content="test")],
        )
        d = t.to_dict(include_versions=True)
        assert "versions" in d
        assert len(d["versions"]) == 1

    def test_get_current_version(self):
        v1 = PromptVersion(version_number=1, content="v1")
        v2 = PromptVersion(version_number=2, content="v2")
        t = PromptTemplate(
            tenant_id="t1", name="test",
            current_version=2, versions=[v1, v2],
        )
        assert t.get_current_version().content == "v2"

    def test_get_current_version_none(self):
        t = PromptTemplate(tenant_id="t1", name="test", current_version=999)
        assert t.get_current_version() is None

    def test_get_version(self):
        v1 = PromptVersion(version_number=1, content="v1")
        t = PromptTemplate(tenant_id="t1", name="test", versions=[v1])
        assert t.get_version(1).content == "v1"
        assert t.get_version(999) is None


# ============================================================
# PromptCategory Tests
# ============================================================

class TestPromptCategory:
    """Tests for PromptCategory enum."""

    def test_categories(self):
        assert PromptCategory.SYSTEM.value == "system"
        assert PromptCategory.USER.value == "user"
        assert PromptCategory.CHAIN_OF_THOUGHT.value == "chain_of_thought"
        assert PromptCategory.FEW_SHOT.value == "few_shot"
        assert PromptCategory.RAG_CONTEXT.value == "rag_context"
        assert PromptCategory.CUSTOM.value == "custom"


# ============================================================
# PromptManager Tests
# ============================================================

class TestPromptManager:
    """Tests for PromptManager - template CRUD, versioning, tenant isolation."""

    @pytest.fixture
    def manager(self):
        mgr = PromptManager()
        mgr._templates.clear()
        return mgr

    async def _create_template(self, manager):
        return await manager.create_template(
            tenant_id="tenant-1", name="greeting",
            content="Hello {{name}}!", created_by="admin",
        )

    # ── Create Template ───────────────────────────────

    @pytest.mark.asyncio
    async def test_create_template(self, manager):
        tmpl = await manager.create_template(
            tenant_id="tenant-1", name="welcome",
            content="Welcome {{user}} to {{platform}}!",
        )
        assert tmpl.name == "welcome"
        assert tmpl.tenant_id == "tenant-1"
        assert len(tmpl.versions) == 1

    @pytest.mark.asyncio
    async def test_create_template_auto_detect_variables(self, manager):
        tmpl = await manager.create_template(
            tenant_id="tenant-1", name="test",
            content="Hello {{name}}, {{role}}",
        )
        var_names = {v.name for v in tmpl.versions[0].variables}
        assert "name" in var_names
        assert "role" in var_names

    @pytest.mark.asyncio
    async def test_create_template_custom_variables(self, manager):
        custom_vars = [
            TemplateVariable(name="name", required=True),
            TemplateVariable(name="age", var_type="number"),
        ]
        tmpl = await manager.create_template(
            tenant_id="tenant-1", name="test",
            content="{{name}} is {{age}}",
            variables=custom_vars,
        )
        assert len(tmpl.versions[0].variables) == 2
        assert tmpl.versions[0].variables[0].required is True

    @pytest.mark.asyncio
    async def test_create_template_empty_name(self, manager):
        with pytest.raises(ValidationException):
            await manager.create_template(
                tenant_id="tenant-1", name="", content="test",
            )

    @pytest.mark.asyncio
    async def test_create_template_empty_content(self, manager):
        with pytest.raises(ValidationException):
            await manager.create_template(
                tenant_id="tenant-1", name="test", content="",
            )

    @pytest.mark.asyncio
    async def test_create_template_duplicate_name(self, manager):
        await manager.create_template(
            tenant_id="tenant-1", name="greeting", content="Hello",
        )
        with pytest.raises(ConflictException):
            await manager.create_template(
                tenant_id="tenant-1", name="greeting", content="Hi",
            )

    @pytest.mark.asyncio
    async def test_create_template_duplicate_name_different_tenant(self, manager):
        await manager.create_template(
            tenant_id="tenant-1", name="greeting", content="Hello",
        )
        # Should work in different tenant
        tmpl = await manager.create_template(
            tenant_id="tenant-2", name="greeting", content="Hi",
        )
        assert tmpl.tenant_id == "tenant-2"

    @pytest.mark.asyncio
    async def test_create_template_with_tags(self, manager):
        tmpl = await manager.create_template(
            tenant_id="tenant-1", name="tagged",
            content="test", tags=["welcome", "onboarding"],
        )
        assert "welcome" in tmpl.tags
        assert "onboarding" in tmpl.tags

    @pytest.mark.asyncio
    async def test_create_template_invalid_content(self, manager):
        with pytest.raises(ValidationException):
            await manager.create_template(
                tenant_id="tenant-1", name="bad", content="a" * 20000,
            )

    # ── Get Template ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_template(self, manager):
        template = await self._create_template(manager)
        fetched = await manager.get_template(template.template_id)
        assert fetched.name == "greeting"

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, manager):
        with pytest.raises(NotFoundException):
            await manager.get_template("nonexistent-id")

    @pytest.mark.asyncio
    async def test_get_template_by_name(self, manager):
        template = await self._create_template(manager)
        fetched = await manager.get_template_by_name("tenant-1", "greeting")
        assert fetched is not None
        assert fetched.name == "greeting"

    @pytest.mark.asyncio
    async def test_get_template_by_name_not_found(self, manager):
        result = await manager.get_template_by_name("tenant-1", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_template_by_name_case_insensitive(self, manager):
        template = await self._create_template(manager)
        result = await manager.get_template_by_name("tenant-1", "GREETING")
        assert result is not None

    # ── List Templates ────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_templates(self, manager):
        await manager.create_template(
            tenant_id="tenant-1", name="a", content="test",
        )
        await manager.create_template(
            tenant_id="tenant-1", name="b", content="test",
        )
        results = await manager.list_templates("tenant-1")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_list_templates_filter_category(self, manager):
        await manager.create_template(
            tenant_id="tenant-1", name="sys", content="test",
            category=PromptCategory.SYSTEM.value,
        )
        await manager.create_template(
            tenant_id="tenant-1", name="usr", content="test",
            category=PromptCategory.USER.value,
        )
        results = await manager.list_templates(
            "tenant-1", category=PromptCategory.SYSTEM.value,
        )
        assert len(results) == 1
        assert results[0].name == "sys"

    @pytest.mark.asyncio
    async def test_list_templates_filter_tags(self, manager):
        await manager.create_template(
            tenant_id="tenant-1", name="a", content="test", tags=["tag1"],
        )
        await manager.create_template(
            tenant_id="tenant-1", name="b", content="test", tags=["tag2"],
        )
        results = await manager.list_templates("tenant-1", tags=["tag1"])
        assert len(results) == 1
        assert results[0].name == "a"

    @pytest.mark.asyncio
    async def test_list_templates_tenant_isolation(self, manager):
        await manager.create_template(
            tenant_id="tenant-1", name="a", content="test",
        )
        await manager.create_template(
            tenant_id="tenant-2", name="b", content="test",
        )
        assert len(await manager.list_templates("tenant-1")) == 1
        assert len(await manager.list_templates("tenant-2")) == 1

    @pytest.mark.asyncio
    async def test_list_templates_pagination(self, manager):
        for i in range(10):
            await manager.create_template(
                tenant_id="tenant-1", name=f"t{i}", content="test",
            )
        results = await manager.list_templates("tenant-1", limit=5, offset=3)
        assert len(results) == 5

    # ── Update Template ───────────────────────────────

    @pytest.mark.asyncio
    async def test_update_template_name(self, manager):
        template = await self._create_template(manager)
        await manager.update_template(template.template_id, name="new_name")
        assert template.name == "new_name"

    @pytest.mark.asyncio
    async def test_update_template_description(self, manager):
        template = await self._create_template(manager)
        await manager.update_template(template.template_id, description="New desc")
        assert template.description == "New desc"

    @pytest.mark.asyncio
    async def test_update_template_tags(self, manager):
        template = await self._create_template(manager)
        await manager.update_template(template.template_id, tags=["a", "b"])
        assert template.tags == ["a", "b"]

    @pytest.mark.asyncio
    async def test_update_template_is_active(self, manager):
        template = await self._create_template(manager)
        await manager.update_template(template.template_id, is_active=False)
        assert template.is_active is False

    @pytest.mark.asyncio
    async def test_update_template_not_found(self, manager):
        with pytest.raises(NotFoundException):
            await manager.update_template("nonexistent", name="x")

    @pytest.mark.asyncio
    async def test_update_template_empty_name(self, manager):
        template = await self._create_template(manager)
        with pytest.raises(ValidationException):
            await manager.update_template(template.template_id, name="")

    # ── Delete Template ───────────────────────────────

    @pytest.mark.asyncio
    async def test_delete_template(self, manager):
        template = await self._create_template(manager)
        result = await manager.delete_template(template.template_id)
        assert result is True
        with pytest.raises(NotFoundException):
            await manager.get_template(template.template_id)

    @pytest.mark.asyncio
    async def test_delete_template_not_found(self, manager):
        with pytest.raises(NotFoundException):
            await manager.delete_template("nonexistent")

    # ── Version Management ────────────────────────────

    @pytest.mark.asyncio
    async def test_create_version(self, manager):
        template = await self._create_template(manager)
        v2 = await manager.create_version(
            template.template_id, content="Hi {{name}}!",
            changelog="Changed greeting",
        )
        assert v2.version_number == 2
        assert template.current_version == 2

    @pytest.mark.asyncio
    async def test_create_version_auto_detect_variables(self, manager):
        template = await self._create_template(manager)
        v2 = await manager.create_version(
            template.template_id, content="{{greeting}} {{name}}!",
        )
        var_names = {v.name for v in v2.variables}
        assert "greeting" in var_names
        assert "name" in var_names

    @pytest.mark.asyncio
    async def test_create_version_max_limit(self, manager):
        template = await self._create_template(manager)
        cfg = get_config().prompt
        for i in range(cfg.max_versions_per_template - 1):
            await manager.create_version(
                template.template_id, content=f"v{i}: {{name}}",
            )
        with pytest.raises(ValidationException):
            await manager.create_version(
                template.template_id, content="one more: {{name}}",
            )

    @pytest.mark.asyncio
    async def test_get_version(self, manager):
        template = await self._create_template(manager)
        v = await manager.get_version(template.template_id, 1)
        assert v.version_number == 1

    @pytest.mark.asyncio
    async def test_get_version_not_found(self, manager):
        template = await self._create_template(manager)
        with pytest.raises(NotFoundException):
            await manager.get_version(template.template_id, 999)

    @pytest.mark.asyncio
    async def test_rollback_version(self, manager):
        template = await self._create_template(manager)
        await manager.create_version(
            template.template_id, content="v2: {{name}}",
        )
        await manager.rollback_version(template.template_id, 1)
        assert template.current_version == 1

    @pytest.mark.asyncio
    async def test_rollback_version_not_found(self, manager):
        template = await self._create_template(manager)
        with pytest.raises(NotFoundException):
            await manager.rollback_version(template.template_id, 999)

    @pytest.mark.asyncio
    async def test_list_versions(self, manager):
        template = await self._create_template(manager)
        await manager.create_version(
            template.template_id, content="v2: {{name}}",
        )
        versions = await manager.list_versions(template.template_id)
        assert len(versions) == 2
        assert versions[0].version_number == 2  # latest first

    @pytest.mark.asyncio
    async def test_delete_version(self, manager):
        template = await self._create_template(manager)
        await manager.create_version(
            template.template_id, content="v2: {{name}}",
        )
        await manager.delete_version(template.template_id, 2)
        assert template.get_version(2) is None
        assert template.current_version == 1

    @pytest.mark.asyncio
    async def test_delete_version_only_version(self, manager):
        template = await self._create_template(manager)
        with pytest.raises(ValidationException):
            await manager.delete_version(template.template_id, 1)

    @pytest.mark.asyncio
    async def test_delete_version_updates_current(self, manager):
        template = await self._create_template(manager)
        await manager.create_version(
            template.template_id, content="v2: {{name}}",
        )
        await manager.create_version(
            template.template_id, content="v3: {{name}}",
        )
        # Current is v3, delete v3
        await manager.delete_version(template.template_id, 3)
        assert template.current_version == 2

    # ── Render ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_render(self, manager):
        template = await self._create_template(manager)
        result = await manager.render(template.template_id, {"name": "World"})
        assert result["rendered"] == "Hello World!"
        assert result["version"] == 1

    @pytest.mark.asyncio
    async def test_render_specific_version(self, manager):
        template = await self._create_template(manager)
        await manager.create_version(
            template.template_id, content="Hi {{name}}!",
        )
        result = await manager.render(
            template.template_id, {"name": "Bob"}, version_number=1,
        )
        assert result["rendered"] == "Hello Bob!"

    @pytest.mark.asyncio
    async def test_render_inactive_template(self, manager):
        template = await self._create_template(manager)
        await manager.update_template(template.template_id, is_active=False)
        with pytest.raises(ValidationException, match="not active"):
            await manager.render(template.template_id, {"name": "test"})

    @pytest.mark.asyncio
    async def test_render_missing_required_variable(self, manager):
        tmpl = await manager.create_template(
            tenant_id="tenant-1", name="req",
            content="Hello {{name}}!",
            variables=[TemplateVariable(name="name", required=True)],
        )
        with pytest.raises(ValidationException, match="Missing required"):
            await manager.render(tmpl.template_id, {})

    @pytest.mark.asyncio
    async def test_render_required_variable_with_default(self, manager):
        tmpl = await manager.create_template(
            tenant_id="tenant-1", name="req",
            content="Hello {{name}}!",
            variables=[
                TemplateVariable(
                    name="name", required=True, default_value="Guest",
                ),
            ],
        )
        result = await manager.render(tmpl.template_id, {})
        assert result["rendered"] == "Hello Guest!"

    @pytest.mark.asyncio
    async def test_render_preview(self, manager):
        result = await manager.render_preview(
            "Preview: {{test}}", {"test": "hello"},
        )
        assert result["rendered"] == "Preview: hello"

    # ── Validate & Extract ────────────────────────────

    @pytest.mark.asyncio
    async def test_validate_template(self, manager):
        result = await manager.validate_template("Hello {{name}}!")
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_extract_variables(self, manager):
        vars_list = await manager.extract_variables("{{a}} {{b}} {{a}}")
        assert vars_list == ["a", "b"]

    # ── Stats ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_stats(self, manager):
        template = await self._create_template(manager)
        stats = await manager.get_stats("tenant-1")
        assert stats["total_templates"] == 1
        assert stats["active_templates"] == 1
        assert stats["tenant_id"] == "tenant-1"

    @pytest.mark.asyncio
    async def test_get_stats_empty_tenant(self, manager):
        stats = await manager.get_stats("nonexistent")
        assert stats["total_templates"] == 0

    @pytest.mark.asyncio
    async def test_health_check(self, manager):
        hc = await manager.health_check()
        assert hc["status"] == "healthy"


# ============================================================
# Prompt Service Tests
# ============================================================

class TestPromptService:
    """Tests for PromptService - wraps PromptManager with events."""

    @pytest.fixture
    def svc(self):
        svc = PromptService()
        svc._manager._templates.clear()
        return svc

    async def _create_template(self, svc):
        result = await svc.create_template(
            tenant_id="tenant-1", name="greeting",
            content="Hello {{name}}!", created_by="admin",
        )
        return result

    # ── CRUD ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_template(self, svc):
        result = await svc.create_template(
            tenant_id="tenant-1", name="test",
            content="Hello {{name}}!", tags=["welcome"],
        )
        assert result["name"] == "test"
        assert "template_id" in result
        assert "versions" in result

    @pytest.mark.asyncio
    async def test_create_template_with_variables(self, svc):
        result = await svc.create_template(
            tenant_id="tenant-1", name="test",
            content="{{name}} is {{age}}",
            variables=[
                {"name": "name", "required": True},
                {"name": "age", "type": "number"},
            ],
        )
        assert result["versions"][0]["variables"][0]["required"] is True

    @pytest.mark.asyncio
    async def test_create_template_validation_error(self, svc):
        with pytest.raises(ValidationException):
            await svc.create_template(
                tenant_id="tenant-1", name="", content="test",
            )

    @pytest.mark.asyncio
    async def test_get_template(self, svc):
        template = await self._create_template(svc)
        result = await svc.get_template(template["template_id"])
        assert result["name"] == "greeting"

    @pytest.mark.asyncio
    async def test_get_template_with_versions(self, svc):
        template = await self._create_template(svc)
        await svc.create_version(
            template["template_id"], content="Hi {{name}}!",
        )
        result = await svc.get_template(template["template_id"], include_versions=True)
        assert "versions" in result
        assert len(result["versions"]) == 2

    @pytest.mark.asyncio
    async def test_get_template_by_name(self, svc):
        template = await self._create_template(svc)
        result = await svc.get_template_by_name("tenant-1", "greeting")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_templates(self, svc):
        template = await self._create_template(svc)
        results = await svc.list_templates("tenant-1")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_update_template(self, svc):
        template = await self._create_template(svc)
        result = await svc.update_template(
            template["template_id"], description="Updated",
        )
        assert result["description"] == "Updated"

    @pytest.mark.asyncio
    async def test_delete_template(self, svc):
        template = await self._create_template(svc)
        result = await svc.delete_template(template["template_id"])
        assert result["deleted"] is True

    # ── Version Management ────────────────────────────

    @pytest.mark.asyncio
    async def test_create_version(self, svc):
        template = await self._create_template(svc)
        result = await svc.create_version(
            template["template_id"], content="Hi {{name}}!",
            changelog="Changed greeting",
        )
        assert result["version_number"] == 2

    @pytest.mark.asyncio
    async def test_get_version(self, svc):
        template = await self._create_template(svc)
        result = await svc.get_version(template["template_id"], 1)
        assert result["version_number"] == 1

    @pytest.mark.asyncio
    async def test_rollback_version(self, svc):
        template = await self._create_template(svc)
        await svc.create_version(
            template["template_id"], content="Hi {{name}}!",
        )
        result = await svc.rollback_version(template["template_id"], 1)
        assert result["current_version"] == 1

    @pytest.mark.asyncio
    async def test_list_versions(self, svc):
        template = await self._create_template(svc)
        await svc.create_version(
            template["template_id"], content="Hi {{name}}!",
        )
        versions = await svc.list_versions(template["template_id"])
        assert len(versions) == 2

    @pytest.mark.asyncio
    async def test_delete_version(self, svc):
        template = await self._create_template(svc)
        await svc.create_version(
            template["template_id"], content="Hi {{name}}!",
        )
        result = await svc.delete_version(template["template_id"], 2)
        assert result["deleted"] is True

    # ── Render ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_render(self, svc):
        template = await self._create_template(svc)
        result = await svc.render(template["template_id"], {"name": "World"})
        assert result["rendered"] == "Hello World!"

    @pytest.mark.asyncio
    async def test_render_preview(self, svc):
        result = await svc.render_preview("{{test}}", {"test": "hello"})
        assert result["rendered"] == "hello"

    @pytest.mark.asyncio
    async def test_validate(self, svc):
        result = await svc.validate("Hello {{name}}!")
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_extract_variables(self, svc):
        vars_list = await svc.extract_variables("{{a}} {{b}}")
        assert vars_list == ["a", "b"]

    # ── Stats ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_stats(self, svc):
        template = await self._create_template(svc)
        stats = await svc.get_stats("tenant-1")
        assert stats["total_templates"] == 1

    @pytest.mark.asyncio
    async def test_health_check(self, svc):
        hc = await svc.health_check()
        assert hc["status"] == "healthy"


# ============================================================
# Singleton Tests
# ============================================================

class TestSingletons:
    """Tests for singleton accessor functions."""

    def test_get_renderer_singleton(self):
        r1 = get_renderer()
        r2 = get_renderer()
        assert r1 is r2

    def test_get_prompt_manager_singleton(self):
        m1 = get_prompt_manager()
        m2 = get_prompt_manager()
        assert m1 is m2

    def test_get_prompt_service_singleton(self):
        s1 = get_prompt_service()
        s2 = get_prompt_service()
        assert s1 is s2


# ============================================================
# Config Tests
# ============================================================

class TestPromptConfig:
    """Tests for PromptConfig defaults."""

    def test_prompt_config_defaults(self):
        cfg = get_config().prompt
        assert cfg.max_template_length == 10000
        assert cfg.max_variables == 50
        assert cfg.max_versions_per_template == 20
        assert cfg.default_category == "general"
        assert cfg.cache_enabled is True
        assert cfg.cache_ttl_seconds == 300

    def test_prompt_config_in_app_config(self):
        cfg = get_config()
        assert isinstance(cfg.prompt, PromptConfig)