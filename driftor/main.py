"""
Driftor Enterprise - Main application entry point with security-first design.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
import structlog
import uvicorn

from driftor.core.config import get_settings
from driftor.core.database import init_database, cleanup_database, health_check
from driftor.core.rate_limiter import RateLimitMiddleware, get_rate_limiter
from driftor.security.audit import audit, AuditEventType, AuditSeverity

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Driftor Enterprise...")
    
    try:
        # Initialize database
        await init_database()
        
        # Initialize rate limiter
        rate_limiter = await get_rate_limiter()
        
        # Setup periodic tasks
        cleanup_task = asyncio.create_task(periodic_cleanup())
        
        logger.info("Driftor Enterprise started successfully")
        
        yield
        
    except Exception as e:
        logger.error("Failed to start application", error=str(e), exc_info=True)
        raise
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down Driftor Enterprise...")
        
        # Cancel periodic tasks
        if 'cleanup_task' in locals():
            cleanup_task.cancel()
        
        # Cleanup database connections
        await cleanup_database()
        
        logger.info("Driftor Enterprise shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Driftor Enterprise",
    description="AI-powered bug analysis and resolution assistant for enterprise teams",
    version="1.0.0",
    docs_url="/docs" if get_settings().debug else None,
    redoc_url="/redoc" if get_settings().debug else None,
    openapi_url="/openapi.json" if get_settings().debug else None,
    lifespan=lifespan
)

settings = get_settings()

# Security middleware
security = HTTPBearer()

# Add security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    
    # Remove server information
    response.headers.pop("Server", None)
    
    return response


# CORS middleware with restricted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Request-ID"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

# Trusted host middleware
if settings.is_production():
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.driftor.dev", "localhost", "127.0.0.1"]
    )

# Rate limiting middleware
if settings.security.enable_rate_limiting:
    @app.on_event("startup")
    async def setup_rate_limiting():
        rate_limiter = await get_rate_limiter()
        app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with security audit."""
    # Audit security-related errors
    if exc.status_code in [401, 403, 429]:
        await audit(
            event_type=AuditEventType.ACCESS_DENIED,
            severity=AuditSeverity.MEDIUM,
            details={
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
                "detail": exc.detail
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": asyncio.get_event_loop().time()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    # Audit critical errors
    await audit(
        event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
        severity=AuditSeverity.CRITICAL,
        details={
            "error_type": type(exc).__name__,
            "path": request.url.path,
            "method": request.method,
            "error_message": str(exc)[:500]
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred" if settings.is_production() else str(exc),
            "status_code": 500,
            "timestamp": asyncio.get_event_loop().time()
        }
    )


# Health check endpoints
@app.get("/health")
async def health_endpoint():
    """Health check endpoint for load balancers."""
    try:
        db_health = await health_check()
        
        return {
            "status": "healthy",
            "version": "1.0.0",
            "database": db_health,
            "timestamp": asyncio.get_event_loop().time()
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e), exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }
        )


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check for monitoring systems."""
    # This endpoint requires authentication in production
    if settings.is_production():
        # TODO: Add authentication check
        pass
    
    try:
        db_health = await health_check()
        
        # Check other services
        services_health = {
            "database": db_health,
            "redis": {"status": "checking"},  # TODO: Implement Redis health check
            "ollama": {"status": "checking"},  # TODO: Implement Ollama health check
            "integrations": {"status": "checking"}  # TODO: Implement integration health checks
        }
        
        overall_healthy = all(
            service.get("status") == "healthy" 
            for service in services_health.values()
        )
        
        return {
            "status": "healthy" if overall_healthy else "degraded",
            "version": "1.0.0",
            "services": services_health,
            "uptime": asyncio.get_event_loop().time(),
            "environment": settings.environment,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        logger.error("Detailed health check failed", error=str(e), exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }
        )


# Metrics endpoint for Prometheus
@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    # TODO: Implement Prometheus metrics collection
    return JSONResponse(
        content={"message": "Metrics endpoint - implement Prometheus integration"},
        status_code=200
    )


# API Routes (will be added in subsequent implementations)
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Driftor Enterprise API",
        "version": "1.0.0",
        "description": "AI-powered bug analysis and resolution assistant",
        "environment": settings.environment,
        "features": {
            "multi_tenant": True,
            "enterprise_security": True,
            "gdpr_compliant": True,
            "audit_logging": True,
            "rate_limiting": settings.security.enable_rate_limiting
        },
        "links": {
            "health": "/health",
            "docs": "/docs" if settings.debug else None,
            "metrics": "/metrics"
        }
    }


# Periodic maintenance tasks
async def periodic_cleanup():
    """Run periodic maintenance tasks."""
    while True:
        try:
            # Run every hour
            await asyncio.sleep(3600)
            
            logger.info("Running periodic maintenance tasks...")
            
            # TODO: Implement data retention cleanup 
            # TODO: Implement cache cleanup
            # TODO: Implement metric aggregation
            
            logger.info("Periodic maintenance tasks completed")
            
        except asyncio.CancelledError:
            logger.info("Periodic cleanup task cancelled")
            break
        except Exception as e:
            logger.error("Periodic cleanup task failed", error=str(e), exc_info=True)


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "driftor.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
        access_log=True,
        server_header=False,  # Security: don't expose server info
        date_header=False     # Security: don't expose date info
    )