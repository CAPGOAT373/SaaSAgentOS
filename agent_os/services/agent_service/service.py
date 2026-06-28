"""
Agent OS V6.0 - Agent Service
Agent lifecycle management, execution, monitoring
"""
from typing import Optional, Dict, Any, List
from agent_os.core_platform.agent_economy import (
    get_agent_economy, AgentAsset, AgentPricing, AgentLicense, AgentStatus, PriceModel, LicenseType
)
from agent_os.ai_layer.agent_runtime_v3 import (
    get_agent_runtime, AgentConfig, AgentType, ToolDefinition, AgentExecution
)
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.exceptions import NotFoundException, ValidationException


class AgentService(BaseService):
    """Agent Service: manage agent lifecycle, execution, and marketplace integration"""

    def __init__(self):
        super().__init__()
        self._economy = get_agent_economy()
        self._runtime = get_agent_runtime()

    async def register_agent(
        self, tenant_id: str, owner_id: str, name: str, description: str,
        agent_type: str = "chat", system_prompt: str = "",
        price_model: str = "free", price: float = 0.0,
        tags: Optional[List[str]] = None, category: str = "",
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        # Register in economy
        pricing = AgentPricing(price_model=price_model, price=price)
        license_info = AgentLicense(license_type=LicenseType.COMMERCIAL.value)
        asset = await self._economy.register_agent(
            tenant_id=tenant_id, owner_id=owner_id, name=name,
            description=description, pricing=pricing, license_info=license_info,
            tags=tags, category=category, ctx=ctx,
        )

        # Create runtime config
        config = AgentConfig(
            agent_id=asset.agent_id, tenant_id=tenant_id,
            name=name, agent_type=agent_type,
            system_prompt=system_prompt or f"You are {name}, a helpful AI agent.",
        )
        await self._runtime.create_agent(config, ctx)

        return asset.to_dict()

    async def get_agent(self, agent_id: str) -> Dict[str, Any]:
        asset = await self._economy.get_agent(agent_id)
        return asset.to_dict()

    async def list_agents(
        self, tenant_id: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        agents = await self._economy.list_agents(tenant_id=tenant_id, limit=limit, offset=offset)
        return [a.to_dict() for a in agents]

    async def execute_agent(
        self, agent_id: str, user_input: str, user_id: str = "",
        tenant_id: str = "", ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        execution = await self._runtime.execute_agent(
            agent_id=agent_id, user_input=user_input,
            user_id=user_id, tenant_id=tenant_id, ctx=ctx,
        )
        return execution.to_dict()

    async def get_execution(self, execution_id: str) -> Dict[str, Any]:
        execution = await self._runtime.get_execution(execution_id)
        return execution.to_dict()

    async def list_executions(
        self, agent_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        executions = await self._runtime.list_executions(agent_id, limit=limit)
        return [e.to_dict() for e in executions]

    async def add_tool(self, name: str, description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        tool = ToolDefinition(name=name, description=description, parameters=parameters)
        self._runtime.register_tool(tool)
        return tool.to_dict()

    async def list_tools(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._runtime.list_tools()]

    async def publish_agent(self, agent_id: str, ctx: Optional[ServiceContext] = None) -> Dict[str, Any]:
        asset = await self._economy.publish_agent(agent_id, ctx)
        return asset.to_dict()

    async def purchase_agent(
        self, agent_id: str, buyer_tenant_id: str, buyer_user_id: str,
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        return await self._economy.purchase_agent(
            agent_id=agent_id, buyer_tenant_id=buyer_tenant_id,
            buyer_user_id=buyer_user_id, ctx=ctx,
        )

    async def add_review(
        self, agent_id: str, tenant_id: str, user_id: str,
        rating: int, comment: str, ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        review = await self._economy.add_review(
            agent_id=agent_id, tenant_id=tenant_id, user_id=user_id,
            rating=rating, comment=comment, ctx=ctx,
        )
        return review.to_dict()

    async def get_reviews(self, agent_id: str) -> List[Dict[str, Any]]:
        reviews = await self._economy.get_reviews(agent_id)
        return [r.to_dict() for r in reviews]

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "AgentService",
        }


_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service