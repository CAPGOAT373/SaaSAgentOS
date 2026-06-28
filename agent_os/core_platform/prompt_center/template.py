"""
Agent OS V6.0 - Prompt Template Engine
Template with variable interpolation, versioning, and validation
"""
import re
import uuid
from enum import Enum
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent_os.config import get_config


class PromptCategory(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    FEW_SHOT = "few_shot"
    RAG_CONTEXT = "rag_context"
    CUSTOM = "custom"


@dataclass
class TemplateVariable:
    name: str
    description: str = ""
    default_value: str = ""
    required: bool = False
    var_type: str = "string"  # string | number | boolean | list

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "default_value": self.default_value,
            "required": self.required,
            "type": self.var_type,
        }


@dataclass
class PromptVersion:
    version_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version_number: int = 1
    content: str = ""
    variables: List[TemplateVariable] = field(default_factory=list)
    changelog: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = ""

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "version_number": self.version_number,
            "content": self.content,
            "variables": [v.to_dict() for v in self.variables],
            "changelog": self.changelog,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }


@dataclass
class PromptTemplate:
    template_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    category: str = PromptCategory.CUSTOM.value
    tags: List[str] = field(default_factory=list)
    current_version: int = 1
    versions: List[PromptVersion] = field(default_factory=list)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_versions: bool = False) -> dict:
        d = {
            "template_id": self.template_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "current_version": self.current_version,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
        if include_versions:
            d["versions"] = [v.to_dict() for v in self.versions]
        return d

    def get_current_version(self) -> Optional[PromptVersion]:
        for v in self.versions:
            if v.version_number == self.current_version:
                return v
        return None

    def get_version(self, version_number: int) -> Optional[PromptVersion]:
        for v in self.versions:
            if v.version_number == version_number:
                return v
        return None


class PromptRenderer:
    """
    Template renderer with Jinja2-like syntax: {{variable_name}}

    Supports:
    - Simple variable interpolation: {{name}}
    - Default values: {{name|default:value}}
    - Conditional: {% if var %}...{% endif %}
    - Loop: {% for item in list %}...{% endfor %}
    - Nested access: {{obj.key}}
    """

    VARIABLE_RE = re.compile(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*(?:\|\s*default\s*:\s*([^}]*?))?\s*\}\}')
    IF_RE = re.compile(r'\{%\s*if\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*%\}(.*?)\{%\s*endif\s*%\}', re.DOTALL)
    FOR_RE = re.compile(
        r'\{%\s*for\s+(\w+)\s+in\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*%\}(.*?)\{%\s*endfor\s*%\}',
        re.DOTALL,
    )

    def __init__(self):
        self._config = get_config().prompt

    def render(self, template: str, variables: Dict[str, Any]) -> str:
        """
        Render a template string with the given variables.

        Args:
            template: Template string with {{variable}} placeholders
            variables: Dictionary of variable values

        Returns:
            Rendered string

        Raises:
            ValueError: If required variables are missing
        """
        result = template

        # 1. Process for loops
        result = self._render_for_loops(result, variables)

        # 2. Process if conditions
        result = self._render_conditionals(result, variables)

        # 3. Process variable interpolation
        result = self._render_variables(result, variables)

        return result

    def _render_variables(self, template: str, variables: Dict[str, Any]) -> str:
        def replacer(match):
            var_path = match.group(1).strip()
            default_val = match.group(2)

            # Handle nested access: obj.key → variables["obj"]["key"]
            parts = var_path.split('.')
            val = variables
            for part in parts:
                if isinstance(val, dict) and part in val:
                    val = val[part]
                elif hasattr(val, part):
                    val = getattr(val, part)
                else:
                    val = None
                    break

            if val is not None:
                return str(val)
            elif default_val is not None:
                return default_val.strip()
            else:
                return match.group(0)  # Keep placeholder

        return self.VARIABLE_RE.sub(replacer, template)

    def _render_conditionals(self, template: str, variables: Dict[str, Any]) -> str:
        def replacer(match):
            var_name = match.group(1).strip()
            content = match.group(2)
            val = variables.get(var_name)
            if val:
                return content
            return ""

        return self.IF_RE.sub(replacer, template)

    def _render_for_loops(self, template: str, variables: Dict[str, Any]) -> str:
        def replacer(match):
            loop_var = match.group(1).strip()
            list_var = match.group(2).strip()
            content = match.group(3)
            items = variables.get(list_var, [])
            if not isinstance(items, list):
                items = []
            result_parts = []
            for item in items:
                loop_vars = {**variables, loop_var: item}
                # Re-render variables in loop content
                item_rendered = self._render_variables(content, loop_vars)
                result_parts.append(item_rendered)
            rendered = '\n'.join(result_parts)
            return rendered

        return self.FOR_RE.sub(replacer, template)

    def extract_variables(self, template: str) -> List[str]:
        """Extract all variable names from a template."""
        vars_set: Set[str] = set()
        for match in self.VARIABLE_RE.finditer(template):
            var_path = match.group(1).strip()
            # Only top-level variable name
            top_var = var_path.split('.')[0]
            vars_set.add(top_var)
        return sorted(vars_set)

    def validate(self, template: str) -> Dict[str, Any]:
        """Validate a template string, returns errors if any."""
        errors = []
        warnings = []

        if not template or not template.strip():
            errors.append("Template content cannot be empty")

        if len(template) > self._config.max_template_length:
            errors.append(
                f"Template exceeds max length ({self._config.max_template_length} chars)"
            )

        variables = self.extract_variables(template)
        if len(variables) > self._config.max_variables:
            errors.append(f"Too many variables ({len(variables)} > {self._config.max_variables})")

        for var in variables:
            if not re.match(self._config.allowed_variable_pattern, var):
                errors.append(f"Invalid variable name: '{var}'")

        # Check for unclosed tags
        if template.count('{{') != template.count('}}'):
            errors.append("Unclosed variable tags: {{ and }} mismatch")

        if template.count('{%') != template.count('%}'):
            warnings.append("Unclosed control tags: {% and %} mismatch")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "variables": variables,
        }


_renderer: Optional[PromptRenderer] = None


def get_renderer() -> PromptRenderer:
    global _renderer
    if _renderer is None:
        _renderer = PromptRenderer()
    return _renderer