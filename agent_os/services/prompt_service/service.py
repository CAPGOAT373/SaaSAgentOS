"""
Agent OS V6.0 - Prompt Service
Template management, versioning, rendering, tenant isolation
"""
from typing import Optional, Dict, Any, List

from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.exceptions import NotFoundException, ValidationException
from agent_os.core_platform.prompt_center.manager import get_prompt_manager, PromptManager
from agent_os.core_platform.prompt_center.template import (
    PromptTemplate, PromptVersion, TemplateVariable, PromptCategory,
    get_renderer,
)
from agent_os.config import get_config


class PromptService(BaseService):
    """
    Prompt Service: template CRUD, version management, rendering, tenant isolation.

    API:
    - create_template / get_template / update_template / delete_template
    - create_version / rollback_version / list_versions
    - render / render_preview / validate
    - list_templates / get_stats
    """

    def __init__(self):
        super().__init__()
        self._manager = get_prompt_manager()
        self._renderer = get_renderer()
        self._config = get_config().prompt

    # ── Template CRUD ─────────────────────────────────

    async def create_template(
        self, tenant_id: str, name: str, content: str,
        description: str = "", category: str = PromptCategory.CUSTOM.value,
        tags: Optional[List[str]] = None,
        variables: Optional[List[Dict[str, Any]]] = None,
        created_by: str = "",
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Create a new prompt template."""
        var_objs = None
        if variables:
            var_objs = [
                TemplateVariable(
                    name=v.get("name", ""),
                    description=v.get("description", ""),
                    default_value=v.get("default_value", ""),
                    required=v.get("required", False),
                    var_type=v.get("type", "string"),
                )
                for v in variables
            ]

        template = await self._manager.create_template(
            tenant_id=tenant_id, name=name, content=content,
            description=description, category=category, tags=tags,
            variables=var_objs, created_by=created_by,
        )

        await self.emit_event("prompt.template.created", {
            "template_id": template.template_id,
            "tenant_id": tenant_id,
            "name": name,
        }, ctx)

        self.log("info", f"Created template '{name}' in tenant {tenant_id}", ctx)
        return template.to_dict(include_versions=True)

    async def get_template(
        self, template_id: str, include_versions: bool = False,
    ) -> Dict[str, Any]:
        """Get a template by ID."""
        template = await self._manager.get_template(template_id)
        return template.to_dict(include_versions=include_versions)

    async def get_template_by_name(
        self, tenant_id: str, name: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a template by name within a tenant."""
        template = await self._manager.get_template_by_name(tenant_id, name)
        return template.to_dict() if template else None

    async def list_templates(
        self, tenant_id: str, category: str = "",
        tags: Optional[List[str]] = None,
        limit: int = 50, offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List templates for a tenant."""
        templates = await self._manager.list_templates(
            tenant_id=tenant_id, category=category, tags=tags,
            limit=limit, offset=offset,
        )
        return [t.to_dict() for t in templates]

    async def update_template(
        self, template_id: str, name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Update template metadata."""
        template = await self._manager.update_template(
            template_id=template_id, name=name, description=description,
            category=category, tags=tags, is_active=is_active,
        )

        await self.emit_event("prompt.template.updated", {
            "template_id": template_id,
        }, ctx)

        self.log("info", f"Updated template {template_id}", ctx)
        return template.to_dict()

    async def delete_template(
        self, template_id: str,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Delete a template."""
        await self._manager.delete_template(template_id)

        await self.emit_event("prompt.template.deleted", {
            "template_id": template_id,
        }, ctx)

        self.log("info", f"Deleted template {template_id}", ctx)
        return {"deleted": True, "template_id": template_id}

    # ── Version Management ────────────────────────────

    async def create_version(
        self, template_id: str, content: str,
        changelog: str = "", created_by: str = "",
        variables: Optional[List[Dict[str, Any]]] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Create a new version of a template."""
        var_objs = None
        if variables:
            var_objs = [
                TemplateVariable(
                    name=v.get("name", ""),
                    description=v.get("description", ""),
                    default_value=v.get("default_value", ""),
                    required=v.get("required", False),
                    var_type=v.get("type", "string"),
                )
                for v in variables
            ]

        version = await self._manager.create_version(
            template_id=template_id, content=content,
            changelog=changelog, created_by=created_by,
            variables=var_objs,
        )

        await self.emit_event("prompt.version.created", {
            "template_id": template_id,
            "version_number": version.version_number,
        }, ctx)

        self.log("info", f"Created version {version.version_number} for {template_id}", ctx)
        return version.to_dict()

    async def get_version(
        self, template_id: str, version_number: int,
    ) -> Dict[str, Any]:
        """Get a specific version of a template."""
        version = await self._manager.get_version(template_id, version_number)
        return version.to_dict()

    async def rollback_version(
        self, template_id: str, version_number: int,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Rollback to a previous version."""
        template = await self._manager.rollback_version(template_id, version_number)

        await self.emit_event("prompt.version.rolled_back", {
            "template_id": template_id,
            "version_number": version_number,
        }, ctx)

        self.log("info", f"Rolled back {template_id} to v{version_number}", ctx)
        return template.to_dict(include_versions=True)

    async def list_versions(self, template_id: str) -> List[Dict[str, Any]]:
        """List all versions of a template."""
        versions = await self._manager.list_versions(template_id)
        return [v.to_dict() for v in versions]

    async def delete_version(
        self, template_id: str, version_number: int,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Delete a specific version."""
        await self._manager.delete_version(template_id, version_number)

        self.log("info", f"Deleted version {version_number} from {template_id}", ctx)
        return {"deleted": True, "template_id": template_id, "version": version_number}

    # ── Render ────────────────────────────────────────

    async def render(
        self, template_id: str, variables: Dict[str, Any],
        version_number: Optional[int] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Render a template with variables."""
        result = await self._manager.render(
            template_id=template_id, variables=variables,
            version_number=version_number,
        )

        self.log("info", f"Rendered template {template_id}", ctx)
        return result

    async def render_preview(
        self, content: str, variables: Dict[str, Any],
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Preview render a template string."""
        result = await self._manager.render_preview(content, variables)
        self.log("info", "Preview rendered template", ctx)
        return result

    async def validate(self, content: str) -> Dict[str, Any]:
        """Validate a template string."""
        return await self._manager.validate_template(content)

    async def extract_variables(self, content: str) -> List[str]:
        """Extract variables from a template string."""
        return await self._manager.extract_variables(content)

    # ── Statistics ────────────────────────────────────

    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get prompt statistics for a tenant."""
        return await self._manager.get_stats(tenant_id)

    async def health_check(self) -> Dict[str, Any]:
        stats = await self._manager.health_check()
        return {
            "status": "healthy",
            "service": "PromptService",
            "total_templates": stats["total_templates"],
        }


_prompt_service: Optional[PromptService] = None


def get_prompt_service() -> PromptService:
    global _prompt_service
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service