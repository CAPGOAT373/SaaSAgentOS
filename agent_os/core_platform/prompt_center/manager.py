"""
Agent OS V6.0 - Prompt Manager
Template CRUD, version management, tenant isolation
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from agent_os.config import get_config
from agent_os.core_platform.exceptions import NotFoundException, ValidationException, ConflictException
from agent_os.core_platform.prompt_center.template import (
    PromptTemplate, PromptVersion, TemplateVariable, PromptCategory,
    PromptRenderer, get_renderer,
)


class PromptManager:
    """
    Prompt Template Manager: CRUD + Versioning + Tenant Isolation.

    Features:
    - Tenant-scoped template storage
    - Version history with rollback support
    - Template validation and variable extraction
    - Render preview with variable substitution
    - Category and tag-based organization
    """

    def __init__(self):
        self._templates: Dict[str, PromptTemplate] = {}  # template_id → PromptTemplate
        self._renderer = get_renderer()
        self._config = get_config().prompt

    # ── Template CRUD ─────────────────────────────────

    async def create_template(
        self, tenant_id: str, name: str, content: str,
        description: str = "", category: str = PromptCategory.CUSTOM.value,
        tags: Optional[List[str]] = None,
        variables: Optional[List[TemplateVariable]] = None,
        created_by: str = "",
    ) -> PromptTemplate:
        """Create a new prompt template with initial version."""
        # Validate
        if not name or not name.strip():
            raise ValidationException("Template name cannot be empty")
        if not content or not content.strip():
            raise ValidationException("Template content cannot be empty")

        # Check duplicate name within tenant
        for t in self._templates.values():
            if t.tenant_id == tenant_id and t.name.lower() == name.lower():
                raise ConflictException(
                    f"Template '{name}' already exists in tenant {tenant_id}"
                )

        validation = self._renderer.validate(content)
        if not validation["valid"]:
            raise ValidationException(
                f"Template validation failed: {'; '.join(validation['errors'])}"
            )

        # Auto-detect variables if not provided
        if variables is None:
            detected = self._renderer.extract_variables(content)
            variables = [
                TemplateVariable(name=v, description=f"Auto-detected variable: {v}")
                for v in detected
            ]
        else:
            variables = list(variables)

        version = PromptVersion(
            version_number=1,
            content=content,
            variables=variables,
            changelog="Initial version",
            created_by=created_by,
        )

        template = PromptTemplate(
            tenant_id=tenant_id,
            name=name,
            description=description,
            category=category,
            tags=tags or [],
            current_version=1,
            versions=[version],
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._templates[template.template_id] = template
        return template

    async def get_template(self, template_id: str) -> PromptTemplate:
        """Get a template by ID."""
        tmpl = self._templates.get(template_id)
        if not tmpl:
            raise NotFoundException("PromptTemplate", template_id)
        return tmpl

    async def get_template_by_name(self, tenant_id: str, name: str) -> Optional[PromptTemplate]:
        """Get a template by name within a tenant."""
        for t in self._templates.values():
            if t.tenant_id == tenant_id and t.name.lower() == name.lower():
                return t
        return None

    async def list_templates(
        self, tenant_id: str, category: str = "",
        tags: Optional[List[str]] = None,
        limit: int = 50, offset: int = 0,
    ) -> List[PromptTemplate]:
        """List templates for a tenant, with optional filtering."""
        results = [
            t for t in self._templates.values()
            if t.tenant_id == tenant_id
        ]

        if category:
            results = [t for t in results if t.category == category]

        if tags:
            results = [t for t in results if any(tag in t.tags for tag in tags)]

        results.sort(key=lambda t: t.updated_at or t.created_at, reverse=True)
        return results[offset:offset + limit]

    async def update_template(
        self, template_id: str, name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
    ) -> PromptTemplate:
        """Update template metadata (not content)."""
        tmpl = await self.get_template(template_id)

        if name is not None:
            if not name.strip():
                raise ValidationException("Template name cannot be empty")
            tmpl.name = name

        if description is not None:
            tmpl.description = description

        if category is not None:
            tmpl.category = category

        if tags is not None:
            tmpl.tags = tags

        if is_active is not None:
            tmpl.is_active = is_active

        tmpl.updated_at = datetime.now(timezone.utc).isoformat()
        return tmpl

    async def delete_template(self, template_id: str) -> bool:
        """Delete a template and all its versions."""
        if template_id not in self._templates:
            raise NotFoundException("PromptTemplate", template_id)
        del self._templates[template_id]
        return True

    # ── Version Management ────────────────────────────

    async def create_version(
        self, template_id: str, content: str,
        changelog: str = "", created_by: str = "",
        variables: Optional[List[TemplateVariable]] = None,
    ) -> PromptVersion:
        """Create a new version of an existing template."""
        tmpl = await self.get_template(template_id)

        if len(tmpl.versions) >= self._config.max_versions_per_template:
            raise ValidationException(
                f"Maximum versions ({self._config.max_versions_per_template}) reached"
            )

        validation = self._renderer.validate(content)
        if not validation["valid"]:
            raise ValidationException(
                f"Template validation failed: {'; '.join(validation['errors'])}"
            )

        if variables is None:
            detected = self._renderer.extract_variables(content)
            variables = [
                TemplateVariable(name=v, description=f"Auto-detected: {v}")
                for v in detected
            ]
        else:
            variables = list(variables)

        new_ver_num = len(tmpl.versions) + 1
        version = PromptVersion(
            version_number=new_ver_num,
            content=content,
            variables=variables,
            changelog=changelog or f"Version {new_ver_num}",
            created_by=created_by,
        )

        tmpl.versions.append(version)
        tmpl.current_version = new_ver_num
        tmpl.updated_at = datetime.now(timezone.utc).isoformat()
        return version

    async def get_version(self, template_id: str, version_number: int) -> PromptVersion:
        """Get a specific version of a template."""
        tmpl = await self.get_template(template_id)
        version = tmpl.get_version(version_number)
        if not version:
            raise NotFoundException(
                "PromptVersion", f"{template_id}:v{version_number}"
            )
        return version

    async def rollback_version(self, template_id: str, version_number: int) -> PromptTemplate:
        """Rollback to a previous version (sets it as current)."""
        tmpl = await self.get_template(template_id)
        version = tmpl.get_version(version_number)
        if not version:
            raise NotFoundException(
                "PromptVersion", f"{template_id}:v{version_number}"
            )

        tmpl.current_version = version_number
        tmpl.updated_at = datetime.now(timezone.utc).isoformat()
        return tmpl

    async def list_versions(self, template_id: str) -> List[PromptVersion]:
        """List all versions of a template."""
        tmpl = await self.get_template(template_id)
        return sorted(tmpl.versions, key=lambda v: v.version_number, reverse=True)

    async def delete_version(self, template_id: str, version_number: int) -> bool:
        """Delete a specific version of a template."""
        tmpl = await self.get_template(template_id)
        if len(tmpl.versions) <= 1:
            raise ValidationException("Cannot delete the only version of a template")

        tmpl.versions = [v for v in tmpl.versions if v.version_number != version_number]

        if tmpl.current_version == version_number:
            # Set current to latest version
            tmpl.current_version = max(v.version_number for v in tmpl.versions)

        tmpl.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    # ── Render ────────────────────────────────────────

    async def render(
        self, template_id: str, variables: Dict[str, Any],
        version_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Render a template with variables."""
        tmpl = await self.get_template(template_id)

        if not tmpl.is_active:
            raise ValidationException(f"Template {template_id} is not active")

        version = tmpl.get_version(version_number or tmpl.current_version)
        if not version:
            raise NotFoundException("PromptVersion", f"{template_id}:v{version_number}")

        # Validate required variables
        missing = []
        for var in version.variables:
            if var.required and var.name not in variables:
                if var.default_value:
                    variables[var.name] = var.default_value
                else:
                    missing.append(var.name)

        if missing:
            raise ValidationException(f"Missing required variables: {', '.join(missing)}")

        rendered = self._renderer.render(version.content, variables)
        return {
            "template_id": template_id,
            "version": version_number or tmpl.current_version,
            "rendered": rendered,
            "variables_used": variables,
        }

    async def render_preview(
        self, content: str, variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Preview render a template string without saving."""
        validation = self._renderer.validate(content)
        rendered = self._renderer.render(content, variables)
        return {
            "rendered": rendered,
            "validation": validation,
            "variables_used": variables,
        }

    async def validate_template(self, content: str) -> Dict[str, Any]:
        """Validate a template string."""
        return self._renderer.validate(content)

    async def extract_variables(self, content: str) -> List[str]:
        """Extract variable names from a template string."""
        return self._renderer.extract_variables(content)

    # ── Statistics ────────────────────────────────────

    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get prompt statistics for a tenant."""
        templates = [t for t in self._templates.values() if t.tenant_id == tenant_id]
        total_versions = sum(len(t.versions) for t in templates)

        categories = {}
        for t in templates:
            cat = t.category or "uncategorized"
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "tenant_id": tenant_id,
            "total_templates": len(templates),
            "total_versions": total_versions,
            "active_templates": sum(1 for t in templates if t.is_active),
            "categories": categories,
            "config": {
                "max_template_length": self._config.max_template_length,
                "max_versions_per_template": self._config.max_versions_per_template,
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "PromptManager",
            "total_templates": len(self._templates),
        }


_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager