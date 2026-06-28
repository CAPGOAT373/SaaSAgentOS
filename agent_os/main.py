"""
Agent OS V6.0 - Main Entry Point
Capital Grade AI Agent Economy Operating System
"""
import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("agent_os")

import uvicorn
from agent_os.config import get_config


def main():
    """Main entry point for Agent OS V6.0"""
    config = get_config()

    logger.info("=" * 60)
    logger.info(f"  Agent OS V6.0 - Capital Grade AI Agent Economy Platform")
    logger.info(f"  Version: {config.version}")
    logger.info(f"  Region: {config.region.value}")
    logger.info(f"  Deployment: {config.deployment.value}")
    logger.info("=" * 60)

    logger.info(f"Starting API Gateway on {config.host}:{config.port}")
    logger.info(f"Swagger UI: http://localhost:{config.port}/docs")
    logger.info(f"Health Check: http://localhost:{config.port}/health")

    uvicorn.run(
        "agent_os.api_gateway.gateway:app",
        host=config.host,
        port=config.port,
        workers=config.workers if not config.debug else 1,
        reload=config.debug,
        log_level="info" if not config.debug else "debug",
    )


if __name__ == "__main__":
    main()