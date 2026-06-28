"""
Agent OS V6.0 - LLM Gateway
Multi-provider adapter: OpenAI, Claude, Local, Custom Models
No mock data in production - only real LLM calls
"""
import uuid
import time
import json
import logging
from enum import Enum
from typing import Optional, Dict, Any, List, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from agent_os.config import get_config, LLMConfig
from agent_os.core_platform.base import BaseService, ServiceContext

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    CUSTOM = "custom"
    AZURE = "azure"
    GOOGLE = "google"


@dataclass
class LLMRequest:
    prompt: str = ""
    system_prompt: str = ""
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    provider: str = LLMProvider.OPENAI.value
    messages: List[Dict[str, str]] = field(default_factory=list)
    stream: bool = False
    functions: Optional[List[Dict]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_messages(self) -> List[Dict[str, str]]:
        if self.messages:
            return self.messages
        msgs = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.append({"role": "user", "content": self.prompt})
        return msgs


@dataclass
class LLMResponse:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    model: str = ""
    provider: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    tokens_prompt: int = 0
    tokens_completion: int = 0
    cost: float = 0.0
    raw_response: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id, "content": self.content,
            "model": self.model, "provider": self.provider,
            "usage": self.usage, "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms, "tokens_prompt": self.tokens_prompt,
            "tokens_completion": self.tokens_completion, "cost": self.cost,
            "timestamp": self.timestamp,
        }


class LLMUnavailableException(Exception):
    """Raised when LLM is unavailable and mock is not allowed"""
    def __init__(self, provider: str, reason: str):
        super().__init__(f"LLM provider '{provider}' unavailable: {reason}")
        self.provider = provider
        self.reason = reason


class LLMAdapter:
    """Base LLM adapter"""

    async def chat(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        raise NotImplementedError

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        return 0.0


class OpenAIAdapter(LLMAdapter):
    """OpenAI API adapter - real LLM calls only"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.api_base,
                )
            except ImportError:
                raise LLMUnavailableException(
                    LLMProvider.OPENAI.value,
                    "openai package not installed. Run: pip install openai"
                )
        return self._client

    async def chat(self, request: LLMRequest) -> LLMResponse:
        start = time.time()
        if not self.config.api_key and not self.config.allow_mock:
            raise LLMUnavailableException(
                LLMProvider.OPENAI.value,
                "No API key configured. Set LLM_API_KEY env var or allow_mock=True for dev"
            )

        client = await self._get_client()

        try:
            resp = await client.chat.completions.create(
                model=request.model or self.config.default_model,
                messages=request.to_messages(),
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
            choice = resp.choices[0]
            usage = resp.usage
            return LLMResponse(
                content=choice.message.content or "",
                model=resp.model,
                provider=LLMProvider.OPENAI.value,
                usage={
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                } if usage else {},
                finish_reason=choice.finish_reason or "stop",
                latency_ms=(time.time() - start) * 1000,
                tokens_prompt=usage.prompt_tokens if usage else 0,
                tokens_completion=usage.completion_tokens if usage else 0,
                cost=self.estimate_cost(
                    request.model,
                    usage.prompt_tokens if usage else 0,
                    usage.completion_tokens if usage else 0,
                ),
            )
        except Exception as e:
            if self.config.allow_mock:
                logger.warning(f"OpenAI API failed, using mock (dev mode): {e}")
                return LLMResponse(
                    content=f"[DEV] Response to: {request.prompt[:100]}...",
                    model=request.model or self.config.default_model,
                    provider=LLMProvider.OPENAI.value,
                    latency_ms=(time.time() - start) * 1000,
                    tokens_prompt=len(request.prompt.split()),
                    tokens_completion=50,
                    cost=0.0,
                )
            raise LLMUnavailableException(LLMProvider.OPENAI.value, str(e))

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        if not self.config.api_key and not self.config.allow_mock:
            raise LLMUnavailableException(
                LLMProvider.OPENAI.value,
                "No API key configured. Set LLM_API_KEY env var"
            )

        client = await self._get_client()
        try:
            stream = await client.chat.completions.create(
                model=request.model or self.config.default_model,
                messages=request.to_messages(),
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            if self.config.allow_mock:
                logger.warning(f"OpenAI stream failed, using mock: {e}")
                for word in request.prompt[:200].split():
                    yield word + " "
                    import asyncio
                    await asyncio.sleep(0.05)
            else:
                raise LLMUnavailableException(LLMProvider.OPENAI.value, str(e))

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        if "gpt-4" in model:
            return (prompt_tokens * 0.03 + completion_tokens * 0.06) / 1000
        return (prompt_tokens * 0.0015 + completion_tokens * 0.002) / 1000


class ClaudeAdapter(LLMAdapter):
    """Anthropic Claude adapter"""

    def __init__(self, config: LLMConfig):
        self.config = config

    async def chat(self, request: LLMRequest) -> LLMResponse:
        start = time.time()
        if not self.config.api_key and not self.config.allow_mock:
            raise LLMUnavailableException(
                LLMProvider.ANTHROPIC.value,
                "No API key configured. Set LLM_API_KEY env var"
            )
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.config.api_key)
            resp = await client.messages.create(
                model=request.model or "claude-sonnet-4-20250514",
                max_tokens=request.max_tokens,
                system=request.system_prompt,
                messages=[{"role": "user", "content": request.prompt}],
            )
            return LLMResponse(
                content=resp.content[0].text,
                model=resp.model,
                provider=LLMProvider.ANTHROPIC.value,
                usage={"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
                latency_ms=(time.time() - start) * 1000,
                tokens_prompt=resp.usage.input_tokens,
                tokens_completion=resp.usage.output_tokens,
            )
        except ImportError:
            if self.config.allow_mock:
                return LLMResponse(
                    content=f"[DEV] Response to: {request.prompt[:100]}...",
                    model=request.model or "claude-sonnet-4-20250514",
                    provider=LLMProvider.ANTHROPIC.value,
                    latency_ms=(time.time() - start) * 1000,
                )
            raise LLMUnavailableException(
                LLMProvider.ANTHROPIC.value,
                "anthropic package not installed. Run: pip install anthropic"
            )
        except Exception as e:
            raise LLMUnavailableException(LLMProvider.ANTHROPIC.value, str(e))

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        if not self.config.api_key and not self.config.allow_mock:
            raise LLMUnavailableException(LLMProvider.ANTHROPIC.value, "No API key configured")
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.config.api_key)
            async with client.messages.stream(
                model=request.model or "claude-sonnet-4-20250514",
                max_tokens=request.max_tokens,
                system=request.system_prompt,
                messages=[{"role": "user", "content": request.prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except ImportError:
            raise LLMUnavailableException(LLMProvider.ANTHROPIC.value, "anthropic package not installed")
        except Exception as e:
            raise LLMUnavailableException(LLMProvider.ANTHROPIC.value, str(e))


class LocalAdapter(LLMAdapter):
    """Local model adapter (Ollama, vLLM compatible)"""

    def __init__(self, config: LLMConfig):
        self.config = config

    async def chat(self, request: LLMRequest) -> LLMResponse:
        start = time.time()
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config.api_base}/chat/completions",
                    json={
                        "model": request.model or "llama3",
                        "messages": request.to_messages(),
                        "max_tokens": request.max_tokens,
                        "temperature": request.temperature,
                    },
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    data = await resp.json()
                    choice = data["choices"][0]
                    return LLMResponse(
                        content=choice["message"]["content"],
                        model=request.model or "llama3",
                        provider=LLMProvider.LOCAL.value,
                        latency_ms=(time.time() - start) * 1000,
                    )
        except ImportError:
            raise LLMUnavailableException(LLMProvider.LOCAL.value, "aiohttp package not installed")
        except Exception as e:
            raise LLMUnavailableException(LLMProvider.LOCAL.value, str(e))

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config.api_base}/chat/completions",
                    json={
                        "model": request.model or "llama3",
                        "messages": request.to_messages(),
                        "max_tokens": request.max_tokens,
                        "temperature": request.temperature,
                        "stream": True,
                    },
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    async for line in resp.content:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data: ") and line != "data: [DONE]":
                            try:
                                chunk = json.loads(line[6:])
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                if delta.get("content"):
                                    yield delta["content"]
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            raise LLMUnavailableException(LLMProvider.LOCAL.value, str(e))


class LLMGateway(BaseService):
    """LLM Gateway: multi-provider routing, fallback, cost tracking, streaming"""

    def __init__(self):
        super().__init__()
        self._adapters: Dict[str, LLMAdapter] = {}
        self._init_adapters()

    def _init_adapters(self):
        cfg = self.config.llm
        self._adapters[LLMProvider.OPENAI.value] = OpenAIAdapter(cfg)
        self._adapters[LLMProvider.ANTHROPIC.value] = ClaudeAdapter(cfg)
        self._adapters[LLMProvider.LOCAL.value] = LocalAdapter(cfg)

    def get_adapter(self, provider: str) -> Optional[LLMAdapter]:
        return self._adapters.get(provider)

    async def chat(
        self, request: LLMRequest, ctx: Optional[ServiceContext] = None
    ) -> LLMResponse:
        provider = request.provider or self.config.llm.provider
        adapter = self.get_adapter(provider)
        if not adapter:
            adapter = self.get_adapter(LLMProvider.OPENAI.value)

        self.log("info", f"LLM request: {request.prompt[:50]}... via {provider}", ctx)
        response = await adapter.chat(request)
        self.log("info", f"LLM response: {response.latency_ms:.0f}ms, {response.tokens_completion} tokens", ctx)
        return response

    async def chat_stream(
        self, request: LLMRequest, ctx: Optional[ServiceContext] = None
    ) -> AsyncIterator[str]:
        """Stream chat tokens from LLM provider"""
        provider = request.provider or self.config.llm.provider
        adapter = self.get_adapter(provider)
        if not adapter:
            adapter = self.get_adapter(LLMProvider.OPENAI.value)
        async for chunk in adapter.chat_stream(request):
            yield chunk

    async def chat_with_fallback(
        self, request: LLMRequest, ctx: Optional[ServiceContext] = None
    ) -> LLMResponse:
        """Try primary provider, fallback on failure"""
        providers = [request.provider] + self.config.llm.fallback_providers
        last_error = None
        for provider in providers:
            adapter = self.get_adapter(provider)
            if not adapter:
                continue
            try:
                response = await adapter.chat(request)
                if response.finish_reason != "error":
                    return response
            except LLMUnavailableException as e:
                last_error = e
                self.log("warn", f"LLM provider {provider} failed: {e}", ctx)
                continue
            except Exception as e:
                last_error = e
                self.log("warn", f"LLM provider {provider} failed: {e}", ctx)
                continue

        if last_error:
            raise LLMUnavailableException("all", f"All providers failed. Last error: {last_error}")
        return LLMResponse(content="All LLM providers failed", finish_reason="error")

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "service": "LLMGateway",
            "providers": list(self._adapters.keys()),
            "allow_mock": self.config.llm.allow_mock,
        }


_llm_gateway: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    global _llm_gateway
    if _llm_gateway is None:
        _llm_gateway = LLMGateway()
    return _llm_gateway