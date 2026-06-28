"""AI Agent Observability Platform - Configuration."""
import os


class Config:
    """Central configuration with environment variable overrides."""
    # Server
    HOST: str = os.getenv("OBS_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("OBS_PORT", "9100"))
    DEBUG: bool = os.getenv("OBS_DEBUG", "true").lower() == "true"

    # Storage
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")  # empty = in-memory
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # Kafka (event stream simulation)
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    # OpenTelemetry / Jaeger
    JAEGER_ENDPOINT: str = os.getenv("JAEGER_ENDPOINT", "http://localhost:14268/api/traces")
    OTEL_ENABLED: bool = os.getenv("OTEL_ENABLED", "true").lower() == "true"

    # Multi-tenancy
    DEFAULT_TENANT: str = os.getenv("DEFAULT_TENANT", "default")
    MAX_TRACES: int = int(os.getenv("MAX_TRACES", "5000"))

    # Security
    SECURITY_AUTO_BLOCK_THRESHOLD: int = int(os.getenv("SECURITY_AUTO_BLOCK_THRESHOLD", "70"))


config = Config()
