"""
Agent OS V6.0 - API Security
HTTPBearer JWT authentication dependency for FastAPI Swagger UI
"""
from typing import Optional, Dict, Any

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from agent_os.core_platform.identity import get_iam_service

# ─── Security Scheme ───────────────────────────────────
# 这个实例会让 Swagger UI 自动出现 Authorize 按钮
security = HTTPBearer(
    scheme_name="JWT Bearer Token",
    description="Enter your JWT token obtained from /api/v1/auth/login",
    bearerFormat="JWT",
    auto_error=False,  # 不自动报错，由依赖函数处理
)


# ─── Current User Dependency ───────────────────────────
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """
    从 JWT Bearer Token 中解析当前用户信息。
    用于 FastAPI Depends 注入，受保护路由直接使用：
        user: dict = Depends(get_current_user)
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = credentials.credentials
    iam = get_iam_service()
    decoded = iam.decode_jwt(token)

    if decoded is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # 同步写入 request.state，兼容原有 middleware 逻辑
    request.state.user_id = decoded.get("sub", "")
    request.state.tenant_id = decoded.get("tenant_id", "")
    request.state.user_roles = decoded.get("roles", [])

    return {
        "user_id": decoded.get("sub", ""),
        "tenant_id": decoded.get("tenant_id", ""),
        "username": decoded.get("username", ""),
        "roles": decoded.get("roles", []),
    }


# ─── Optional User Dependency ──────────────────────────
async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Dict[str, Any]]:
    """
    可选认证：有 token 就解析，没有也不报错。
    用于同时支持公开和登录用户的路由。
    """
    if credentials is None:
        return None

    token = credentials.credentials
    iam = get_iam_service()
    decoded = iam.decode_jwt(token)

    if decoded is None:
        return None

    request.state.user_id = decoded.get("sub", "")
    request.state.tenant_id = decoded.get("tenant_id", "")
    request.state.user_roles = decoded.get("roles", [])

    return {
        "user_id": decoded.get("sub", ""),
        "tenant_id": decoded.get("tenant_id", ""),
        "username": decoded.get("username", ""),
        "roles": decoded.get("roles", []),
    }