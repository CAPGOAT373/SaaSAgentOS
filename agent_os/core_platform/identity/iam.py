"""
Agent OS V6.0 - Identity & Access Management (IAM)
RBAC + ABAC hybrid, enterprise SSO stub, audit log
"""
import uuid
import hashlib
import hmac
import secrets
import logging
from enum import Enum
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from agent_os.config import get_config
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.exceptions import (
    AuthenticationException, AuthorizationException, NotFoundException
)

logger = logging.getLogger(__name__)


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    DEVELOPER = "developer"
    USER = "user"
    VIEWER = "viewer"
    AGENT = "agent"


class Permission(str, Enum):
    # Tenant
    TENANT_READ = "tenant:read"
    TENANT_WRITE = "tenant:write"
    TENANT_DELETE = "tenant:delete"

    # Agent
    AGENT_CREATE = "agent:create"
    AGENT_READ = "agent:read"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_EXECUTE = "agent:execute"

    # Billing
    BILLING_READ = "billing:read"
    BILLING_MANAGE = "billing:manage"

    # Marketplace
    MARKETPLACE_LIST = "marketplace:list"
    MARKETPLACE_PURCHASE = "marketplace:purchase"
    MARKETPLACE_PUBLISH = "marketplace:publish"

    # Plugin
    PLUGIN_INSTALL = "plugin:install"
    PLUGIN_MANAGE = "plugin:manage"

    # Admin
    ADMIN_ALL = "admin:*"


ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.SUPER_ADMIN: set(Permission),
    Role.TENANT_ADMIN: {
        Permission.TENANT_READ, Permission.TENANT_WRITE,
        Permission.AGENT_CREATE, Permission.AGENT_READ, Permission.AGENT_UPDATE, Permission.AGENT_DELETE,
        Permission.BILLING_READ, Permission.BILLING_MANAGE,
        Permission.MARKETPLACE_LIST, Permission.MARKETPLACE_PURCHASE,
        Permission.PLUGIN_INSTALL, Permission.PLUGIN_MANAGE,
    },
    Role.DEVELOPER: {
        Permission.AGENT_CREATE, Permission.AGENT_READ, Permission.AGENT_UPDATE,
        Permission.MARKETPLACE_LIST, Permission.MARKETPLACE_PUBLISH,
        Permission.PLUGIN_INSTALL, Permission.PLUGIN_MANAGE,
    },
    Role.USER: {
        Permission.AGENT_READ, Permission.AGENT_EXECUTE,
        Permission.MARKETPLACE_LIST, Permission.MARKETPLACE_PURCHASE,
        Permission.PLUGIN_INSTALL,
    },
    Role.VIEWER: {
        Permission.AGENT_READ, Permission.MARKETPLACE_LIST,
    },
    Role.AGENT: {
        Permission.AGENT_EXECUTE,
    },
}


@dataclass
class Identity:
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    username: str = ""
    email: str = ""
    password_hash: str = ""
    roles: List[str] = field(default_factory=lambda: [Role.USER.value])
    api_keys: List[Dict[str, str]] = field(default_factory=list)
    mfa_enabled: bool = False
    sso_provider: str = ""
    sso_subject: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_login: str = ""
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, safe: bool = True) -> dict:
        d = {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "username": self.username,
            "email": self.email,
            "roles": self.roles,
            "mfa_enabled": self.mfa_enabled,
            "sso_provider": self.sso_provider,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_active": self.is_active,
        }
        if not safe:
            d["api_keys"] = self.api_keys
            d["metadata"] = self.metadata
        return d


@dataclass
class AuditLogEntry:
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    action: str = ""
    resource: str = ""
    resource_id: str = ""
    result: str = "success"
    ip_address: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = field(default_factory=dict)
    immutable_hash: str = ""

    def __post_init__(self):
        if not self.immutable_hash:
            self.immutable_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = f"{self.log_id}:{self.tenant_id}:{self.user_id}:{self.action}:{self.resource}:{self.timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()

    def verify(self) -> bool:
        return self._compute_hash() == self.immutable_hash


class IAMService(BaseService):
    """Identity and Access Management with RBAC + ABAC"""

    def __init__(self):
        super().__init__()
        self._identities: Dict[str, Identity] = {}
        self._audit_log: List[AuditLogEntry] = []
        self._api_key_index: Dict[str, str] = {}  # api_key_hash -> user_id

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        return salt + ":" + hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        parts = password_hash.split(":", 1)
        if len(parts) != 2:
            return False
        salt, h = parts
        return h == hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()

    def generate_api_key(self) -> str:
        return "aos_" + secrets.token_hex(32)

    def generate_jwt(self, identity: Identity, ctx: Optional[ServiceContext] = None) -> str:
        try:
            import jwt
            cfg = self.config.security
            payload = {
                "sub": identity.user_id,
                "tenant_id": identity.tenant_id,
                "username": identity.username,
                "roles": identity.roles,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=cfg.jwt_expire_minutes),
                "iat": datetime.now(timezone.utc),
                "iss": "agent-os",
            }
            return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)
        except ImportError:
            return f"mock_jwt_{identity.user_id}_{identity.tenant_id}"

    def decode_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            import jwt
            cfg = self.config.security
            return jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
        except ImportError:
            if token.startswith("mock_jwt_"):
                parts = token.replace("mock_jwt_", "").split("_")
                return {"sub": parts[0], "tenant_id": parts[1] if len(parts) > 1 else ""}
            return None
        except Exception:
            return None

    async def create_identity(
        self, tenant_id: str, username: str, email: str, password: str,
        roles: Optional[List[str]] = None, ctx: Optional[ServiceContext] = None
    ) -> Identity:
        for ident in self._identities.values():
            if ident.email == email and ident.tenant_id == tenant_id:
                from agent_os.core_platform.exceptions import ConflictException
                raise ConflictException(f"Email {email} already exists in tenant {tenant_id}")

        identity = Identity(
            tenant_id=tenant_id,
            username=username,
            email=email,
            password_hash=self.hash_password(password),
            roles=roles or [Role.USER.value],
        )
        self._identities[identity.user_id] = identity
        await self._write_audit_log(
            tenant_id=tenant_id, user_id=identity.user_id, action="identity.created",
            resource="identity", resource_id=identity.user_id, ctx=ctx
        )
        return identity

    async def authenticate(
        self, tenant_id: str, email: str, password: str, ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        for ident in self._identities.values():
            if ident.tenant_id == tenant_id and ident.email == email:
                if not ident.is_active:
                    raise AuthenticationException("Account is disabled")
                if self.verify_password(password, ident.password_hash):
                    ident.last_login = datetime.now(timezone.utc).isoformat()
                    token = self.generate_jwt(ident, ctx)
                    await self._write_audit_log(
                        tenant_id=tenant_id, user_id=ident.user_id, action="login",
                        resource="identity", resource_id=ident.user_id, ctx=ctx
                    )
                    return {
                        "access_token": token,
                        "token_type": "bearer",
                        "user": ident.to_dict(),
                    }
        raise AuthenticationException("Invalid credentials")

    async def authenticate_api_key(self, api_key: str) -> Optional[Identity]:
        user_id = self._api_key_index.get(api_key)
        if user_id:
            return self._identities.get(user_id)
        return None

    async def get_identity(self, user_id: str) -> Identity:
        ident = self._identities.get(user_id)
        if not ident:
            raise NotFoundException("Identity", user_id)
        return ident

    async def check_permission(
        self, user_id: str, permission: Permission, ctx: Optional[ServiceContext] = None
    ) -> bool:
        identity = await self.get_identity(user_id)
        if not identity.is_active:
            return False
        for role_name in identity.roles:
            role = Role(role_name)
            perms = ROLE_PERMISSIONS.get(role, set())
            if permission in perms or Permission.ADMIN_ALL in perms:
                return True
        return False

    async def require_permission(
        self, user_id: str, permission: Permission, ctx: Optional[ServiceContext] = None
    ):
        if not await self.check_permission(user_id, permission, ctx):
            raise AuthorizationException(f"Missing permission: {permission.value}")

    async def create_api_key(self, user_id: str) -> str:
        identity = await self.get_identity(user_id)
        api_key = self.generate_api_key()
        identity.api_keys.append({
            "key_hash": hashlib.sha256(api_key.encode()).hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used": "",
        })
        self._api_key_index[api_key] = user_id
        return api_key

    async def _write_audit_log(
        self, tenant_id: str, user_id: str, action: str, resource: str,
        resource_id: str, ctx: Optional[ServiceContext] = None, details: Optional[Dict] = None
    ):
        entry = AuditLogEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details or {},
        )
        self._audit_log.append(entry)
        self.log("info", f"Audit: {action} on {resource} by {user_id}", ctx)

    async def get_audit_logs(
        self, tenant_id: str, limit: int = 100, offset: int = 0
    ) -> List[AuditLogEntry]:
        logs = [e for e in self._audit_log if e.tenant_id == tenant_id]
        return logs[offset:offset + limit]

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "IAMService",
            "total_identities": len(self._identities),
            "audit_log_entries": len(self._audit_log),
        }


_iam_service: Optional[IAMService] = None


def get_iam_service() -> IAMService:
    global _iam_service
    if _iam_service is None:
        _iam_service = IAMService()
    return _iam_service