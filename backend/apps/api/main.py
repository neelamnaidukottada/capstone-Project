"""Autonomous Campaign Manager — FastAPI entry point."""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add API root to sys.path for app.* imports
api_root = Path(__file__).parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.errors import install_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import limiter
from app.core.security import JWTAuthMiddleware
from app.routers import agents, auth, campaigns, health, ws_campaigns

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    configure_logging()
    logger.info("api_startup", environment=settings.ENVIRONMENT)
    yield
    # Shutdown
    logger.info("api_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Autonomous Campaign Manager API",
        version="0.1.0",
        description="Backend API for orchestrating autonomous multi-agent campaign workflows.",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    install_exception_handlers(app)

    # Security middleware
    app.add_middleware(JWTAuthMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts_list,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Routers
    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["campaigns"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
    app.include_router(ws_campaigns.router, tags=["realtime"])

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development",
    )
