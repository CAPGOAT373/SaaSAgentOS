"""
Agent OS V6.0 - Auth Service
Authentication, authorization, token management
"""
from typing import Optional, Dict, Any
from agent_os.core_platform.identity import get_iam_service, IAMService, Role, Permission
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.exceptions import AuthenticationException, ValidationException


class AuthService(BaseService):
    """Authentication Service - wraps IAM for API consumption"""

    def __init__(self):
        super().__init__()
        self._iam = get_iam_service()

    async def register(
        self, tenant_id: str, username: str, email: str, password: str,
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        identity = await self._iam.create_identity(
            tenant_id=tenant_id, username=username, email=email, password=password, ctx=ctx
        )
        return identity.to_dict(safe=True)

    async def login(
        self, tenant_id: str, email: str, password: str,
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        return await self._iam.authenticate(tenant_id=tenant_id, email=email, password=password, ctx=ctx)

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        return self._iam.decode_jwt(token)

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        identity = await self._iam.get_identity(user_id)
        return identity.to_dict(safe=True)

    async def create_api_key(self, user_id: str) -> str:
        return await self._iam.create_api_key(user_id)

    async def health_check(self) -> Dict[str, Any]:
        return await self._iam.health_check()


_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service