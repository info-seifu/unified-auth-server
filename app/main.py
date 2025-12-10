"""Main FastAPI application"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
import logging
import secrets

from app.config import settings
from app.routes import auth, proxy, audit
from app.models.schemas import HealthCheckResponse, ServiceInfoResponse

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if settings.log_format != 'json' else None
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Unified Auth Server",
    description="統合認証サーバー - Google OAuth認証とJWTトークン発行",
    version="1.0.0",
    debug=settings.debug
)

# Add session middleware for OAuth state management
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret_key or secrets.token_urlsafe(32),
    session_cookie="auth_session",
    max_age=3600,  # 1 hour
    same_site="lax",
    https_only=settings.is_production
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)


@app.on_event("startup")
async def startup_event():
    """Application startup"""
    logger.info(f"Starting Unified Auth Server in {settings.environment} mode")
    logger.info(f"CORS origins: {settings.cors_origins}")
    logger.info(f"Allowed domains: {settings.allowed_domains}")
    if settings.use_local_config:
        logger.info("Using local project configurations")
    else:
        logger.info("Using Firestore for project configurations")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown"""
    logger.info("Shutting down Unified Auth Server")


@app.get(
    "/",
    response_model=ServiceInfoResponse,
    summary="Service information",
    description="Get service information and available endpoints"
)
async def root():
    """Root endpoint - returns service information"""
    return ServiceInfoResponse(
        service="Unified Auth Server",
        version="1.0.0",
        status="running",
        environment=settings.environment,
        endpoints={
            "login": "/login/{project_id}",
            "callback": "/callback/{project_id}",
            "verify": "/api/verify",
            "refresh": "/api/refresh",
            "proxy": "/api/proxy",
            "logout": "/logout",
            "health": "/health"
        }
    )


@app.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="Check if the service is healthy and running"
)
async def health_check():
    """Health check endpoint"""
    return HealthCheckResponse(
        status="healthy",
        environment=settings.environment,
        debug=settings.debug
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "NOT_FOUND",
            "message": f"Path {request.url.path} not found",
            "path": str(request.url.path)
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred"
        }
    )


# Include routers
app.include_router(auth.router, tags=["Authentication"])
app.include_router(proxy.router, tags=["API Proxy"])
app.include_router(audit.router, tags=["Audit Logs"])


# Development endpoints (only in development mode)
if settings.is_development:
    @app.get("/api/config")
    async def get_config():
        """Get current configuration (development only)"""
        from app.config import LOCAL_PROJECT_CONFIGS
        return {
            "environment": settings.environment,
            "allowed_domains": settings.allowed_domains,
            "cors_origins": settings.cors_origins,
            "projects": list(LOCAL_PROJECT_CONFIGS.keys()),
            "use_local_config": settings.use_local_config
        }

    @app.get("/api/projects")
    async def list_projects():
        """List all projects (development only)"""
        from app.core.project_config import project_config_manager
        projects = await project_config_manager.list_projects()
        return projects

    @app.get("/api/projects/{project_id}")
    async def get_project(project_id: str):
        """Get project configuration (development only)"""
        from app.core.project_config import project_config_manager
        config = await project_config_manager.get_project_config(project_id)
        return config