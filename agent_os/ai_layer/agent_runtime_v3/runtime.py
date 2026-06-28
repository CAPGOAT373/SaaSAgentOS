"""
Agent OS V6.0 - Agent Runtime Engine V3
Enterprise-grade: streaming, RAG, MCP tools, memory, events, cost tracking
"""
import uuid
import time
import json
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Awaitable, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.config import get_config
from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.event_bus import EventTypes
from agent_os.core_platform.exceptions import NotFoundException, ValidationException

logger = logging.getLogger(__name__)


class AgentExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(str, Enum):
    CHAT = "chat"
    TASK = "task"
    WORKFLOW = "workflow"
    TOOL = "tool"
    ROUTER = "router"
    HYBRID = "hybrid"


@dataclass
class ToolDefinition:
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable[..., Awaitable[Any]]] = None
    is_async: bool = True
    timeout_seconds: int = 30
    cost_per_call: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": self.parameters, "is_async": self.is_async,
            "timeout_seconds": self.timeout_seconds, "cost_per_call": self.cost_per_call,
        }

    def to_openai_function(self) -> dict:
        """Convert to OpenAI function calling format"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters.get("properties", {}),
                "required": self.parameters.get("required", []),
            },
        }


@dataclass
class AgentConfig:
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    agent_type: str = AgentType.CHAT.value
    system_prompt: str = "You are a helpful AI agent."
    model: str = "gpt-4"
    provider: str = "openai"
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: List[ToolDefinition] = field(default_factory=list)
    memory_enabled: bool = True
    memory_limit: int = 100
    rag_enabled: bool = False
    rag_top_k: int = 5
    chain_agents: List[str] = field(default_factory=list)
    cost_limit: float = 10.0
    max_iterations: int = 10
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id, "tenant_id": self.tenant_id,
            "name": self.name, "agent_type": self.agent_type,
            "system_prompt": self.system_prompt, "model": self.model,
            "provider": self.provider, "temperature": self.temperature,
            "tools": [t.to_dict() for t in self.tools],
            "memory_enabled": self.memory_enabled, "memory_limit": self.memory_limit,
            "rag_enabled": self.rag_enabled, "rag_top_k": self.rag_top_k,
            "chain_agents": self.chain_agents, "cost_limit": self.cost_limit,
            "max_iterations": self.max_iterations,
        }


@dataclass
class AgentExecution:
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    tenant_id: str = ""
    user_id: str = ""
    status: str = AgentExecutionStatus.PENDING.value
    input: str = ""
    output: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    total_cost: float = 0.0
    total_tokens: int = 0
    latency_ms: float = 0.0
    reasoning_trace: List[str] = field(default_factory=list)
    error: str = ""
    started_at: str = ""
    completed_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id, "agent_id": self.agent_id,
            "tenant_id": self.tenant_id, "user_id": self.user_id,
            "status": self.status, "input": self.input[:200],
            "output": self.output[:500], "steps": self.steps,
            "total_cost": self.total_cost, "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms, "reasoning_trace": self.reasoning_trace,
            "error": self.error, "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class AgentRuntimeV3(BaseService):
    """Agent Runtime Engine V3: streaming, RAG, MCP tools, memory, events"""

    def __init__(self):
        super().__init__()
        self._agents: Dict[str, AgentConfig] = {}
        self._executions: Dict[str, AgentExecution] = {}
        self._tool_registry: Dict[str, ToolDefinition] = {}
        self._collaboration_groups: Dict[str, List[str]] = {}
        self._sessions: Dict[str, str] = {}  # session_key -> session_id

    # ── Tool Management ────────────────────────────────

    def register_tool(self, tool: ToolDefinition):
        """Register a tool in the global tool registry"""
        self._tool_registry[tool.name] = tool

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tool_registry.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tool_registry.values())

    def get_tools_as_openai_functions(self) -> List[dict]:
        """Export tools as OpenAI function calling format"""
        return [t.to_openai_function() for t in self._tool_registry.values()]

    # ── Agent Management ───────────────────────────────

    async def create_agent(self, config: AgentConfig, ctx: Optional[ServiceContext] = None) -> AgentConfig:
        self._agents[config.agent_id] = config
        await self.emit_event(EventTypes.AGENT_CREATED, config.to_dict(), ctx)
        return config

    async def get_agent(self, agent_id: str) -> AgentConfig:
        agent = self._agents.get(agent_id)
        if not agent:
            raise NotFoundException("Agent", agent_id)
        return agent

    async def list_agents(self, tenant_id: Optional[str] = None) -> List[AgentConfig]:
        agents = list(self._agents.values())
        if tenant_id:
            agents = [a for a in agents if a.tenant_id == tenant_id]
        return agents

    # ── Core Execution ─────────────────────────────────

    async def execute_agent(
        self, agent_id: str, user_input: str, user_id: str = "",
        tenant_id: str = "", ctx: Optional[ServiceContext] = None
    ) -> AgentExecution:
        """Execute agent - full pipeline: prompt → RAG → memory → LLM → tools → output"""
        agent = await self.get_agent(agent_id)
        execution = AgentExecution(
            agent_id=agent_id, tenant_id=tenant_id or agent.tenant_id,
            user_id=user_id, input=user_input,
            status=AgentExecutionStatus.RUNNING.value,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._executions[execution.execution_id] = execution

        start_time = time.time()

        # Emit execution started
        await self.emit_event(EventTypes.AGENT_EXECUTION_STARTED, {
            "execution_id": execution.execution_id, "agent_id": agent_id,
            "tenant_id": tenant_id, "user_id": user_id,
            "input": user_input[:100],
        }, ctx)

        try:
            # Build messages with system prompt, RAG context, and memory
            messages = await self._build_prompt(agent, user_input, tenant_id, ctx)

            # Execute agent chain or single agent
            if agent.chain_agents:
                result = await self._execute_chain(agent, messages, execution, ctx)
            else:
                result = await self._execute_single(agent, messages, execution, ctx)

            execution.output = result.get("content", "")
            execution.total_cost = result.get("cost", 0.0)
            execution.total_tokens = result.get("tokens", 0)
            execution.status = AgentExecutionStatus.COMPLETED.value
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            execution.latency_ms = (time.time() - start_time) * 1000

            # Save to memory
            if agent.memory_enabled:
                await self._save_memory(agent_id, tenant_id, user_input, execution.output, ctx)

            # Emit execution completed
            await self.emit_event(EventTypes.AGENT_EXECUTION_COMPLETED, {
                "execution_id": execution.execution_id, "agent_id": agent_id,
                "tenant_id": tenant_id, "output": execution.output[:500],
                "total_cost": execution.total_cost, "total_tokens": execution.total_tokens,
                "latency_ms": execution.latency_ms,
            }, ctx)
            await self.emit_event(EventTypes.AGENT_EXECUTED, execution.to_dict(), ctx)

        except Exception as e:
            execution.status = AgentExecutionStatus.FAILED.value
            execution.error = str(e)
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            execution.latency_ms = (time.time() - start_time) * 1000
            await self.emit_event(EventTypes.AGENT_EXECUTION_FAILED, {
                "execution_id": execution.execution_id, "agent_id": agent_id,
                "error": str(e),
            }, ctx)

        return execution

    async def execute_agent_stream(
        self, agent_id: str, user_input: str, user_id: str = "",
        tenant_id: str = "", ctx: Optional[ServiceContext] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute agent with streaming token output"""
        agent = await self.get_agent(agent_id)
        execution = AgentExecution(
            agent_id=agent_id, tenant_id=tenant_id or agent.tenant_id,
            user_id=user_id, input=user_input,
            status=AgentExecutionStatus.RUNNING.value,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._executions[execution.execution_id] = execution

        start_time = time.time()

        # Emit execution started
        await self.emit_event(EventTypes.AGENT_EXECUTION_STARTED, {
            "execution_id": execution.execution_id, "agent_id": agent_id,
            "tenant_id": tenant_id, "user_id": user_id,
        }, ctx)

        yield {"type": "execution_started", "execution_id": execution.execution_id, "agent_id": agent_id}

        try:
            # Build messages
            messages = await self._build_prompt(agent, user_input, tenant_id, ctx)

            yield {"type": "prompt_built", "message_count": len(messages)}

            # Stream LLM response
            from agent_os.ai_layer.llm_gateway import get_llm_gateway, LLMRequest

            llm = get_llm_gateway()
            request = LLMRequest(
                prompt=messages[-1]["content"] if messages else user_input,
                system_prompt=agent.system_prompt,
                model=agent.model,
                provider=agent.provider,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                messages=messages,
                stream=True,
            )

            full_output = ""
            token_count = 0
            async for token in llm.chat_stream(request, ctx):
                full_output += token
                token_count += 1
                yield {"type": "token", "content": token, "token_index": token_count}

            # Estimate tokens
            prompt_tokens = sum(len(m.get("content", "").split()) for m in messages)
            total_tokens = prompt_tokens + token_count

            execution.output = full_output
            execution.total_tokens = total_tokens
            execution.status = AgentExecutionStatus.COMPLETED.value
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            execution.latency_ms = (time.time() - start_time) * 1000

            # Save to memory
            if agent.memory_enabled:
                await self._save_memory(agent_id, tenant_id, user_input, full_output, ctx)

            yield {
                "type": "execution_completed",
                "execution_id": execution.execution_id,
                "output": full_output[:500],
                "total_tokens": total_tokens,
                "latency_ms": execution.latency_ms,
            }

            await self.emit_event(EventTypes.AGENT_EXECUTION_COMPLETED, {
                "execution_id": execution.execution_id, "agent_id": agent_id,
                "output": full_output[:500], "total_tokens": total_tokens,
                "latency_ms": execution.latency_ms,
            }, ctx)

        except Exception as e:
            execution.status = AgentExecutionStatus.FAILED.value
            execution.error = str(e)
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            execution.latency_ms = (time.time() - start_time) * 1000

            yield {"type": "execution_failed", "execution_id": execution.execution_id, "error": str(e)}

            await self.emit_event(EventTypes.AGENT_EXECUTION_FAILED, {
                "execution_id": execution.execution_id, "agent_id": agent_id, "error": str(e),
            }, ctx)

    # ── Prompt Building ────────────────────────────────

    async def _build_prompt(
        self, agent: AgentConfig, user_input: str, tenant_id: str,
        ctx: Optional[ServiceContext] = None
    ) -> List[Dict[str, str]]:
        """Build the complete prompt with system prompt, RAG context, and memory"""
        messages = []

        # 1. System prompt with RAG context injection
        system_content = agent.system_prompt or "You are a helpful AI agent."

        if agent.rag_enabled:
            rag_context = await self._load_rag_context(user_input, tenant_id, agent.rag_top_k, ctx)
            if rag_context:
                system_content += f"\n\n## Relevant Knowledge Base Context:\n{rag_context}"

        messages.append({"role": "system", "content": system_content})

        # 2. Memory injection
        if agent.memory_enabled:
            memory_msgs = await self._load_memory(agent.agent_id, tenant_id, ctx)
            messages.extend(memory_msgs)

        # 3. User input
        messages.append({"role": "user", "content": user_input})

        return messages

    # ── RAG Context Injection ──────────────────────────

    async def _load_rag_context(
        self, query: str, tenant_id: str, top_k: int = 5,
        ctx: Optional[ServiceContext] = None
    ) -> str:
        """Load relevant context from RAG system"""
        try:
            from agent_os.ai_layer.rag.retrieval import get_retrieval_engine
            retrieval = get_retrieval_engine()
            result = await retrieval.search(
                query=query,
                top_k=top_k,
                filters={"tenant_id": tenant_id} if tenant_id else None,
            )
            if result and result.chunks:
                return result.context
        except Exception as e:
            logger.warning(f"RAG context load failed: {e}")
        return ""

    # ── Single Agent Execution ─────────────────────────

    async def _execute_single(
        self, agent: AgentConfig, messages: List[Dict], execution: AgentExecution,
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        """Execute a single agent with tool calling loop"""
        from agent_os.ai_layer.llm_gateway import get_llm_gateway, LLMRequest

        llm = get_llm_gateway()
        total_cost = 0.0
        total_tokens = 0
        iteration = 0

        while iteration < agent.max_iterations:
            iteration += 1
            execution.reasoning_trace.append(f"Iteration {iteration}: calling LLM")

            request = LLMRequest(
                prompt=messages[-1]["content"] if messages else "",
                system_prompt=agent.system_prompt,
                model=agent.model,
                provider=agent.provider,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                messages=messages,
            )

            response = await llm.chat(request, ctx)
            total_cost += response.cost
            total_tokens += response.tokens_prompt + response.tokens_completion

            # Check for tool calls in response
            tool_calls = self._parse_tool_calls(response.content)
            if tool_calls:
                for tc in tool_calls:
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("arguments", {})

                    # Emit tool call started
                    await self.emit_event(EventTypes.TOOL_CALL_STARTED, {
                        "execution_id": execution.execution_id,
                        "tool_name": tool_name, "arguments": tool_args,
                    }, ctx)

                    tool = self.get_tool(tool_name)
                    if tool:
                        execution.reasoning_trace.append(f"Executing tool: {tool_name}")
                        try:
                            tool_result = await tool.handler(**tool_args) if tool.handler else {"result": "no handler"}
                            total_cost += tool.cost_per_call
                            execution.steps.append({
                                "iteration": iteration, "tool": tool_name,
                                "args": tool_args, "result": str(tool_result)[:200],
                            })
                            messages.append({
                                "role": "assistant",
                                "content": f"Tool '{tool_name}' result: {str(tool_result)[:500]}"
                            })

                            await self.emit_event(EventTypes.TOOL_CALL_COMPLETED, {
                                "execution_id": execution.execution_id,
                                "tool_name": tool_name, "success": True,
                                "result": str(tool_result)[:200],
                            }, ctx)
                        except Exception as e:
                            messages.append({
                                "role": "assistant",
                                "content": f"Tool '{tool_name}' error: {e}"
                            })
                            await self.emit_event(EventTypes.TOOL_CALL_FAILED, {
                                "execution_id": execution.execution_id,
                                "tool_name": tool_name, "error": str(e),
                            }, ctx)
                    else:
                        execution.reasoning_trace.append(f"Tool not found: {tool_name}")
                        # Try MCP tool registry
                        mcp_result = await self._execute_mcp_tool(
                            tool_name, tool_args, execution.tenant_id, ctx
                        )
                        if mcp_result:
                            messages.append({
                                "role": "assistant",
                                "content": f"MCP Tool '{tool_name}' result: {str(mcp_result)[:500]}"
                            })
                        else:
                            messages.append({
                                "role": "assistant",
                                "content": f"Tool '{tool_name}' not found in registry or MCP"
                            })
                continue
            else:
                # No tool calls, final response
                messages.append({"role": "assistant", "content": response.content})
                break

            if total_cost >= agent.cost_limit:
                execution.reasoning_trace.append(f"Cost limit reached: {total_cost}")
                break

        return {
            "content": messages[-1]["content"] if messages else "",
            "cost": total_cost,
            "tokens": total_tokens,
        }

    # ── MCP Tool Execution ─────────────────────────────

    async def _execute_mcp_tool(
        self, tool_name: str, arguments: Dict[str, Any], tenant_id: str,
        ctx: Optional[ServiceContext] = None
    ) -> Optional[Any]:
        """Execute a tool via MCP registry"""
        try:
            from agent_os.core_platform.mcp_tool_server.registry import get_tool_registry
            registry = get_tool_registry()
            tool = await registry.get_tool_by_name(tenant_id, tool_name)
            if tool:
                result = await registry.invoke_tool(tool.tool_id, arguments)
                return result.result if result.success else result.error
        except Exception as e:
            logger.warning(f"MCP tool execution failed for {tool_name}: {e}")
        return None

    # ── Chain Execution ────────────────────────────────

    async def _execute_chain(
        self, agent: AgentConfig, messages: List[Dict], execution: AgentExecution,
        ctx: Optional[ServiceContext] = None
    ) -> Dict[str, Any]:
        """Execute agent chain: output of one agent feeds into next"""
        current_input = messages[-1]["content"] if messages else ""
        total_cost = 0.0
        total_tokens = 0

        for chain_agent_id in agent.chain_agents:
            try:
                chain_agent = await self.get_agent(chain_agent_id)
                chain_result = await self._execute_single(chain_agent, [
                    {"role": "system", "content": chain_agent.system_prompt},
                    {"role": "user", "content": current_input},
                ], execution, ctx)
                current_input = chain_result["content"]
                total_cost += chain_result["cost"]
                total_tokens += chain_result["tokens"]
                execution.reasoning_trace.append(
                    f"Chain agent {chain_agent_id}: {current_input[:100]}..."
                )
            except Exception as e:
                execution.reasoning_trace.append(f"Chain agent {chain_agent_id} error: {e}")

        return {"content": current_input, "cost": total_cost, "tokens": total_tokens}

    # ── Tool Call Parsing ──────────────────────────────

    def _parse_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """Parse tool calls from LLM response"""
        tool_calls = []
        if "```tool" in content or "<tool_call>" in content:
            try:
                import re
                matches = re.findall(r'```tool\s*\n(.*?)\n```', content, re.DOTALL)
                for match in matches:
                    tool_calls.append(json.loads(match))
            except Exception:
                pass
        return tool_calls

    # ── Collaboration ──────────────────────────────────

    async def execute_collaboration(
        self, group_id: str, user_input: str, ctx: Optional[ServiceContext] = None
    ) -> List[AgentExecution]:
        """Execute multiple agents in collaboration"""
        agent_ids = self._collaboration_groups.get(group_id, [])
        if not agent_ids:
            raise ValidationException(f"Collaboration group {group_id} not found")

        tasks = [self.execute_agent(aid, user_input, ctx=ctx) for aid in agent_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        executions = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                executions.append(AgentExecution(
                    agent_id=agent_ids[i], status=AgentExecutionStatus.FAILED.value,
                    error=str(result),
                ))
            else:
                executions.append(result)
        return executions

    async def create_collaboration_group(
        self, group_id: str, agent_ids: List[str]
    ) -> Dict[str, Any]:
        for agent_id in agent_ids:
            if agent_id not in self._agents:
                raise NotFoundException("Agent", agent_id)
        self._collaboration_groups[group_id] = agent_ids
        return {"group_id": group_id, "agent_ids": agent_ids}

    # ── Memory System (New MemoryEngine) ────────────────

    async def _get_or_create_session(
        self, agent_id: str, tenant_id: str, user_id: str = ""
    ) -> str:
        """Get or create a memory session for the agent-user pair."""
        from agent_os.core_platform.memory_system.engine import get_memory_engine
        engine = get_memory_engine()
        # Use a stable session key: agent_id + user_id + tenant_id
        session_key = f"agent_session_{agent_id}_{user_id}_{tenant_id}"
        if session_key not in self._sessions:
            try:
                session = await engine.create_session(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    title=f"Agent Session: {agent_id[:8]}",
                )
                self._sessions[session_key] = session.session_id
            except Exception:
                self._sessions[session_key] = session_key
        return self._sessions[session_key]

    async def _load_memory(
        self, agent_id: str, tenant_id: str, ctx: Optional[ServiceContext] = None
    ) -> List[Dict[str, str]]:
        """Load conversation history from new MemoryEngine (working + episodic + semantic)"""
        from agent_os.core_platform.memory_system.engine import get_memory_engine
        engine = get_memory_engine()
        session_id = await self._get_or_create_session(agent_id, tenant_id)
        try:
            context = await engine.assemble_context(
                session_id=session_id,
                query="",
                tenant_id=tenant_id,
                max_working=20,
                max_episodic=5,
                max_semantic=3,
            )
            result = []
            for entry in context.entries[-20:]:  # Last 20 entries
                result.append({"role": entry.role, "content": entry.content})
            return result
        except Exception as e:
            logger.warning(f"Memory load failed: {e}, falling back to old system")
            # Fallback to old memory system
            from agent_os.ai_layer.memory_system.memory import get_memory_system
            memory = get_memory_system()
            entries = await memory.retrieve(agent_id, tenant_id, limit=10)
            return [{"role": e["role"], "content": e["content"]} for e in entries]

    async def _save_memory(
        self, agent_id: str, tenant_id: str, user_input: str, output: str,
        ctx: Optional[ServiceContext] = None
    ):
        """Save conversation to new MemoryEngine (working + auto-to-episodic)"""
        from agent_os.core_platform.memory_system.engine import get_memory_engine
        engine = get_memory_engine()
        session_id = await self._get_or_create_session(agent_id, tenant_id)
        try:
            # Save to working memory (auto-consolidates to episodic)
            await engine.add_to_working(
                session_id=session_id,
                content=user_input,
                role="user",
                tenant_id=tenant_id,
                importance=0.6,
            )
            await engine.add_to_working(
                session_id=session_id,
                content=output,
                role="assistant",
                tenant_id=tenant_id,
                importance=0.7,
            )
            # Periodically auto-consolidate to semantic
            await engine.auto_consolidate(session_id)
        except Exception as e:
            logger.warning(f"Memory save failed: {e}, falling back to old system")
            # Fallback to old memory system
            from agent_os.ai_layer.memory_system.memory import get_memory_system
            memory = get_memory_system()
            await memory.store(agent_id, tenant_id, "user", user_input)
            await memory.store(agent_id, tenant_id, "assistant", output)

    # ── Execution History ──────────────────────────────

    async def get_execution(self, execution_id: str) -> AgentExecution:
        exec_data = self._executions.get(execution_id)
        if not exec_data:
            raise NotFoundException("Execution", execution_id)
        return exec_data

    async def list_executions(
        self, agent_id: str, limit: int = 50
    ) -> List[AgentExecution]:
        executions = [e for e in self._executions.values() if e.agent_id == agent_id]
        return sorted(executions, key=lambda e: e.started_at, reverse=True)[:limit]

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "AgentRuntimeV3",
            "total_agents": len(self._agents),
            "total_executions": len(self._executions),
            "total_tools": len(self._tool_registry),
        }


_agent_runtime: Optional[AgentRuntimeV3] = None


def get_agent_runtime() -> AgentRuntimeV3:
    global _agent_runtime
    if _agent_runtime is None:
        _agent_runtime = AgentRuntimeV3()
    return _agent_runtime