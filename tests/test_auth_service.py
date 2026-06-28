"""
Agent OS V6.0 - AuthService Tests
Unit tests with mocked IAM + Integration tests with real IAM
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from agent_os.core_platform.identity.iam import Identity, IAMService
from agent_os.core_platform.exceptions import AuthenticationException, NotFoundException, ConflictException
from agent_os.services.auth_service.service import AuthService, get_auth_service


# ============================================================
# Unit Tests (Mocked IAM)
# ============================================================

class TestAuthServiceUnit:
    """Unit tests with mocked IAMService."""

    @pytest.fixture
    def auth_svc(self, mock_iam):
        svc = AuthService()
        svc._iam = mock_iam
        return svc

    # ── register ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_register_success(self, auth_svc, mock_iam, service_context):
        identity = Identity(
            user_id="user-001", tenant_id="test-tenant",
            username="alice", email="alice@test.com",
            password_hash="hashed:abc",
        )
        mock_iam.create_identity.return_value = identity

        result = await auth_svc.register(
            "test-tenant", "alice", "alice@test.com", "secret123",
            ctx=service_context,
        )

        assert result["user_id"] == "user-001"
        assert result["username"] == "alice"
        assert result["email"] == "alice@test.com"
        assert "password_hash" not in result  # safe=True
        mock_iam.create_identity.assert_called_once_with(
            tenant_id="test-tenant", username="alice",
            email="alice@test.com", password="secret123", ctx=service_context,
        )

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, auth_svc, mock_iam, service_context):
        mock_iam.create_identity.side_effect = ConflictException(
            "Email alice@test.com already exists in tenant test-tenant"
        )

        with pytest.raises(ConflictException, match="already exists"):
            await auth_svc.register(
                "test-tenant", "alice", "alice@test.com", "secret123",
                ctx=service_context,
            )

    # ── login ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_login_success(self, auth_svc, mock_iam, service_context):
        mock_iam.authenticate.return_value = {
            "access_token": "mock_jwt_user-001_test-tenant",
            "token_type": "bearer",
            "user": {"user_id": "user-001", "username": "alice"},
        }

        result = await auth_svc.login(
            "test-tenant", "alice@test.com", "secret123",
            ctx=service_context,
        )

        assert result["access_token"].startswith("mock_jwt_")
        assert result["token_type"] == "bearer"
        mock_iam.authenticate.assert_called_once_with(
            tenant_id="test-tenant", email="alice@test.com",
            password="secret123", ctx=service_context,
        )

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, auth_svc, mock_iam, service_context):
        mock_iam.authenticate.side_effect = AuthenticationException("Invalid credentials")

        with pytest.raises(AuthenticationException, match="Invalid credentials"):
            await auth_svc.login(
                "test-tenant", "alice@test.com", "wrong",
                ctx=service_context,
            )

    # ── verify_token ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_verify_token_valid(self, auth_svc, mock_iam):
        mock_iam.decode_jwt.return_value = {
            "sub": "user-001", "tenant_id": "test-tenant", "roles": ["user"],
        }

        result = await auth_svc.verify_token("mock_jwt_user-001_test-tenant")

        assert result["sub"] == "user-001"
        assert result["tenant_id"] == "test-tenant"
        mock_iam.decode_jwt.assert_called_once_with("mock_jwt_user-001_test-tenant")

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, auth_svc, mock_iam):
        mock_iam.decode_jwt.return_value = None

        result = await auth_svc.verify_token("invalid_token")

        assert result is None

    # ── get_user ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_user_success(self, auth_svc, mock_iam):
        identity = Identity(
            user_id="user-001", tenant_id="test-tenant",
            username="alice", email="alice@test.com",
        )
        mock_iam.get_identity.return_value = identity

        result = await auth_svc.get_user("user-001")

        assert result["user_id"] == "user-001"
        assert result["username"] == "alice"
        mock_iam.get_identity.assert_called_once_with("user-001")

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, auth_svc, mock_iam):
        mock_iam.get_identity.side_effect = NotFoundException("Identity", "user-999")

        with pytest.raises(NotFoundException, match="Identity not found"):
            await auth_svc.get_user("user-999")

    # ── create_api_key ────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_api_key(self, auth_svc, mock_iam):
        mock_iam.create_api_key.return_value = "aos_abc123def456"

        result = await auth_svc.create_api_key("user-001")

        assert result == "aos_abc123def456"
        mock_iam.create_api_key.assert_called_once_with("user-001")

    # ── health_check ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_check(self, auth_svc, mock_iam):
        mock_iam.health_check.return_value = {
            "status": "healthy", "service": "IAMService",
            "total_identities": 5, "audit_log_entries": 10,
        }

        result = await auth_svc.health_check()

        assert result["status"] == "healthy"
        assert result["total_identities"] == 5


# ============================================================
# Integration Tests (Real IAM)
# ============================================================

class TestAuthServiceIntegration:
    """Integration tests with real IAMService."""

    @pytest.fixture
    def auth_svc(self, isolated_iam):
        svc = AuthService()
        svc._iam = isolated_iam
        return svc, isolated_iam

    @pytest.mark.asyncio
    async def test_full_auth_flow(self, auth_svc, service_context):
        svc, iam = auth_svc

        # 1. Register
        identity = await svc.register(
            "tenant-001", "bob", "bob@test.com", "password123",
            ctx=service_context,
        )
        user_id = identity["user_id"]
        assert identity["username"] == "bob"
        assert identity["email"] == "bob@test.com"
        assert "password_hash" not in identity

        # 2. Login
        auth_result = await svc.login(
            "tenant-001", "bob@test.com", "password123",
            ctx=service_context,
        )
        assert "access_token" in auth_result
        assert auth_result["token_type"] == "bearer"
        token = auth_result["access_token"]

        # 3. Verify token
        decoded = await svc.verify_token(token)
        assert decoded is not None
        assert decoded["sub"] == user_id

        # 4. Get user
        user = await svc.get_user(user_id)
        assert user["email"] == "bob@test.com"

        # 5. Create API key
        api_key = await svc.create_api_key(user_id)
        assert api_key.startswith("aos_")

    @pytest.mark.asyncio
    async def test_register_duplicate(self, auth_svc, service_context):
        svc, iam = auth_svc

        await svc.register("tenant-001", "carl", "carl@test.com", "pass", ctx=service_context)

        with pytest.raises(ConflictException, match="already exists"):
            await svc.register("tenant-001", "carl2", "carl@test.com", "pass", ctx=service_context)

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, auth_svc, service_context):
        svc, iam = auth_svc

        await svc.register("tenant-001", "dave", "dave@test.com", "correct", ctx=service_context)

        with pytest.raises(AuthenticationException, match="Invalid credentials"):
            await svc.login("tenant-001", "dave@test.com", "wrong", ctx=service_context)

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, auth_svc, service_context):
        svc, iam = auth_svc

        with pytest.raises(AuthenticationException, match="Invalid credentials"):
            await svc.login("tenant-001", "nobody@test.com", "pass", ctx=service_context)

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, auth_svc):
        svc, iam = auth_svc

        result = await svc.verify_token("garbage_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, auth_svc):
        svc, iam = auth_svc

        with pytest.raises(NotFoundException):
            await svc.get_user("nonexistent-user")

    @pytest.mark.asyncio
    async def test_singleton(self):
        svc1 = get_auth_service()
        svc2 = get_auth_service()
        assert svc1 is svc2