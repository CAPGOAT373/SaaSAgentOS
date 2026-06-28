"""
Agent OS V6.0 - Unified Configuration System
Supports multi-region, multi-environment, env-var injection
"""
import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from enum import Enum


class Region(str, Enum):
    US_EAST = "us-east-1"
    US_WEST = "us-west-1"
    EU_WEST = "eu-west-1"
    AP_SOUTHEAST = "ap-southeast-1"
    AP_NORTHEAST = "ap-northeast-1"


class DeploymentMode(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"
    ENTERPRISE = "enterprise"


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    user: str = "agentos"
    password: str = "agentos"
    database: str = "agent_os"
    pool_size: int = 20
    max_overflow: int = 10
    ssl_mode: str = "prefer"

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    cluster_mode: bool = False
    cluster_nodes: List[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        prefix = "rediss" if self.password else "redis"
        return f"{prefix}://:{self.password}@{self.host}:{self.port}/{self.db}"


@dataclass
class KafkaConfig:
    bootstrap_servers: str = "localhost:9092"
    consumer_group: str = "agent-os"
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = True
    topics: Dict[str, str] = field(default_factory=lambda: {
        "agent_events": "agent_os.agent.events",
        "workflow_events": "agent_os.workflow.events",
        "billing_events": "agent_os.billing.events",
        "plugin_events": "agent_os.plugin.events",
        "tenant_events": "agent_os.tenant.events",
        "marketplace_events": "agent_os.marketplace.events",
        "system_events": "agent_os.system.events",
    })


@dataclass
class LLMConfig:
    provider: str = "openai"
    api_key: str = ""
    api_base: str = "https://api.openai.com/v1"
    default_model: str = "gpt-4"
    max_tokens: int = 4096
    temperature: float = 0.7
    fallback_providers: List[str] = field(default_factory=lambda: ["claude", "local"])
    allow_mock: bool = False  # 生产环境必须为False，不允许mock数据


@dataclass
class ObservabilityConfig:
    prometheus_port: int = 9090
    tracing_enabled: bool = True
    tracing_backend: str = "jaeger"
    tracing_endpoint: str = "http://localhost:14268/api/traces"
    log_level: str = "INFO"
    log_format: str = "json"


@dataclass
class RegionConfig:
    region: Region = Region.US_EAST
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)


@dataclass
class BillingConfig:
    platform_fee_percent: float = 15.0
    default_currency: str = "USD"
    subscription_tiers: Dict[str, Dict] = field(default_factory=lambda: {
        "free": {"price": 0, "agents_limit": 3, "calls_per_month": 1000},
        "pro": {"price": 49, "agents_limit": 20, "calls_per_month": 50000},
        "business": {"price": 299, "agents_limit": 100, "calls_per_month": 500000},
        "enterprise": {"price": 999, "agents_limit": -1, "calls_per_month": -1},
    })
    agent_revenue_share: Dict[str, float] = field(default_factory=lambda: {
        "creator": 70.0,
        "platform": 15.0,
        "affiliate": 15.0,
    })
    plugin_revenue_share: Dict[str, float] = field(default_factory=lambda: {
        "developer": 75.0,
        "platform": 25.0,
    })


@dataclass
class SecurityConfig:
    jwt_secret: str = "agent-os-dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 7
    api_key_header: str = "X-API-Key"
    tenant_id_header: str = "X-Tenant-ID"
    region_header: str = "X-Region"


@dataclass
class RAGConfig:
    embedding_dim: int = 256
    embedding_provider: str = "hash"  # hash | openai | sentence_transformer
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5
    similarity_threshold: float = 0.3
    vector_store_backend: str = "memory"  # memory | chroma | qdrant | pinecone
    rerank_enabled: bool = True
    hybrid_search_weight: float = 0.5  # 0=keyword only, 1=vector only
    max_context_length: int = 8000


@dataclass
class PromptConfig:
    max_template_length: int = 10000
    max_variables: int = 50
    max_versions_per_template: int = 20
    default_category: str = "general"
    render_timeout_ms: int = 5000
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    allowed_variable_pattern: str = r"^[a-zA-Z_][a-zA-Z0-9_]*$"


@dataclass
class MCPConfig:
    max_tools: int = 100
    max_tool_name_length: int = 128
    max_description_length: int = 1024
    sandbox_timeout_ms: int = 30000
    sandbox_mode: str = "process"  # process | restricted | docker
    max_input_size_bytes: int = 1048576  # 1MB
    max_output_size_bytes: int = 1048576  # 1MB
    allowed_origins: List[str] = field(default_factory=lambda: ["*"])
    server_port: int = 9100
    server_host: str = "0.0.0.0"
    cache_enabled: bool = True
    cache_ttl_seconds: int = 60


@dataclass
class MemoryConfig:
    working_memory_capacity: int = 20  # max entries in working memory
    episodic_memory_capacity: int = 1000  # max entries per session
    semantic_memory_capacity: int = 10000  # max entries in semantic store
    embedding_dim: int = 128  # dimension for semantic memory vectors
    max_context_window: int = 10  # entries to retrieve from working memory
    session_ttl_seconds: int = 3600  # session timeout
    cache_ttl_seconds: int = 300  # cache TTL for memory entries
    consolidation_threshold: int = 5  # number of accesses before consolidating to semantic
    backend: str = "memory"  # memory | redis
    similarity_threshold: float = 0.3  # min similarity for semantic retrieval
    top_k_semantic: int = 5  # number of semantic results to retrieve


@dataclass
class GuardrailConfig:
    enabled: bool = True
    injection_detection: bool = True  # prompt injection detection
    output_filtering: bool = True  # output safety filtering
    default_action: str = "warn"  # allow | warn | block | redact
    max_prompt_length: int = 32768  # max prompt length in chars
    max_output_length: int = 16384  # max output length in chars
    block_on_high_severity: bool = True  # auto-block high/critical severity
    allow_on_low_severity: bool = True  # auto-allow low severity
    # Injection detection patterns (regex)
    injection_patterns: List[str] = field(default_factory=lambda: [
        r"(?i)ignore\s+(all\s+)?(previous|above|before)\s+(instructions?|prompts?|directions?)",
        r"(?i)you\s+are\s+now\s+(a\s+)?(DAN|jailbreak|evil|unfiltered|unrestricted)",
        r"(?i)(system\s*(prompt|message|instruction))",
        r"(?i)forget\s+(everything|all)\s+(you\s+(know|were\s+told))",
        r"(?i)(pretend|act|roleplay)\s+(as\s+)?(if\s+you\s+are|a\s+different|you\s+are)",
        r"(?i)new\s+(instructions?|rules?)\s*[:：]",
        r"(?i)override\s+(your\s+)?(instructions?|rules?|programming)",
        r"(?i)you\s+must\s+(always\s+)?(respond|answer|comply)",
        r"(?i)do\s+not\s+(follow|obey)\s+(your\s+)?(instructions?|rules?)",
        r"(?i)reveal\s+(your\s+)?(system\s+)?(prompt|instructions?|rules?)",
        r"(?i)\[INST\].*\[/INST\]",
        r"(?i)<\|im_start\|>.*<\|im_end\|>",
        r"(?i)<<SYS>>.*<<\/SYS>>",
        r"(?i)begin\s+by\s+(ignoring|disregarding)",
        r"(?i)reply\s+as\s+(if\s+)?(you\s+are|a\s+different)",
    ])
    # Content moderation categories
    content_categories: List[str] = field(default_factory=lambda: [
        "hate_speech", "violence", "sexual_content", "self_harm",
        "harassment", "illegal_activity", "misinformation",
    ])
    # Sensitive data patterns (PII, secrets, etc.)
    sensitive_data_patterns: List[str] = field(default_factory=lambda: [
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b\d{16}\b",  # Credit card
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
        r"\b(?:\+?86)?1[3-9]\d{9}\b",  # Chinese phone
        r"\b(?:sk-[A-Za-z0-9]{32,})\b",  # API keys
        r"\b(?:AKIA[0-9A-Z]{16})\b",  # AWS access key
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",  # UUID (potential token)
    ])
    # Audit logging
    audit_log_enabled: bool = True
    audit_log_retention_days: int = 90
    # Rate limiting for guardrail checks
    max_checks_per_minute: int = 1000
    # Cache for rule evaluation results
    cache_enabled: bool = True
    cache_ttl_seconds: int = 60


@dataclass
class WorkflowConfig:
    max_nodes_per_workflow: int = 100
    max_parallel_branches: int = 20
    max_nesting_depth: int = 5
    default_node_timeout_seconds: int = 300
    max_node_timeout_seconds: int = 3600
    max_retries: int = 3
    max_retry_delay_seconds: int = 60
    dag_validation_enabled: bool = True
    visualization_format: str = "mermaid"  # mermaid | graphviz | both
    condition_sandbox_enabled: bool = True
    condition_max_expression_length: int = 500
    parallel_execution_enabled: bool = True
    parallel_max_concurrency: int = 50
    fan_out_max_branches: int = 10
    execution_history_retention: int = 1000
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 60


@dataclass
class AppConfig:
    app_name: str = "Agent OS"
    version: str = "6.0.0"
    region: Region = Region.US_EAST
    deployment: DeploymentMode = DeploymentMode.DEV
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    billing: BillingConfig = field(default_factory=BillingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    guardrail: GuardrailConfig = field(default_factory=GuardrailConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)

    regions: Dict[str, RegionConfig] = field(default_factory=dict)
    gprc_port: int = 50051

    def get_region_config(self, region: Region) -> RegionConfig:
        return self.regions.get(region.value, RegionConfig(region=region))

    @classmethod
    def from_env(cls) -> "AppConfig":
        config = cls()
        config.region = Region(os.getenv("AGENT_OS_REGION", config.region.value))
        config.deployment = DeploymentMode(os.getenv("DEPLOYMENT_MODE", config.deployment.value))
        config.debug = os.getenv("DEBUG", "true").lower() == "true"
        config.port = int(os.getenv("PORT", config.port))

        config.db.host = os.getenv("DB_HOST", config.db.host)
        config.db.port = int(os.getenv("DB_PORT", config.db.port))
        config.db.user = os.getenv("DB_USER", config.db.user)
        config.db.password = os.getenv("DB_PASSWORD", config.db.password)
        config.db.database = os.getenv("DB_NAME", config.db.database)

        config.redis.host = os.getenv("REDIS_HOST", config.redis.host)
        config.redis.port = int(os.getenv("REDIS_PORT", config.redis.port))
        config.redis.password = os.getenv("REDIS_PASSWORD", config.redis.password)

        config.kafka.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", config.kafka.bootstrap_servers)

        config.llm.api_key = os.getenv("LLM_API_KEY", config.llm.api_key)
        config.llm.default_model = os.getenv("LLM_DEFAULT_MODEL", config.llm.default_model)

        config.security.jwt_secret = os.getenv("JWT_SECRET", config.security.jwt_secret)

        return config

    def to_dict(self) -> dict:
        d = asdict(self)
        d["region"] = self.region.value
        d["deployment"] = self.deployment.value
        return d


# Singleton config instance
_config_instance: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _config_instance
    if _config_instance is None:
        _config_instance = AppConfig.from_env()
    return _config_instance


def set_config(config: AppConfig):
    global _config_instance
    _config_instance = config