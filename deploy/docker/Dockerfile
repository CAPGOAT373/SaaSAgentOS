# ============================================================
# Agent OS V6.0 - Production Multi-Stage Dockerfile
# Capital Grade AI Agent Economy Platform
# ============================================================

# ── Stage 1: Builder ──────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install with pip
COPY agent_os/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────
FROM python:3.11-slim AS runtime

# Create non-root user
RUN groupadd -r agentos && useradd -r -g agentos -d /app -s /sbin/nologin agentos

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /usr/local

# Copy application code
COPY agent_os/ ./agent_os/

# Set ownership
RUN chown -R agentos:agentos /app

# Switch to non-root user
USER agentos

# Expose ports
# 8000 - HTTP API
# 9090 - Prometheus metrics
# 50051 - gRPC
# 9100 - MCP Server
EXPOSE 8000 9090 50051 9100

# Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8000/health || exit 1

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEPLOYMENT_MODE=production

# Run
CMD ["python", "-m", "agent_os.main"]