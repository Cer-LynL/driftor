"""
Enterprise rate limiting system with tenant isolation and abuse protection.
"""
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple
import redis.asyncio as redis
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import structlog

from driftor.core.config import get_settings
from driftor.security.audit import audit, AuditEventType, AuditSeverity

logger = structlog.get_logger(__name__)


class RateLimitType(str, Enum):
    """Types of rate limits."""
    API_CALLS = "api_calls"
    JIRA_REQUESTS = "jira_requests"
    GITHUB_REQUESTS = "github_requests"
    SLACK_MESSAGES = "slack_messages"
    TEAMS_MESSAGES = "teams_messages"
    WEBHOOK_CALLS = "webhook_calls"
    LOGIN_ATTEMPTS = "login_attempts"


class RateLimitWindow(str, Enum):
    """Rate limit time windows."""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


@dataclass
class RateLimit:
    """Rate limit configuration."""
    limit: int
    window: RateLimitWindow
    burst_limit: Optional[int] = None  # Allow bursts up to this limit
    
    def get_window_seconds(self) -> int:
        """Get window duration in seconds."""
        if self.window == RateLimitWindow.SECOND:
            return 1
        elif self.window == RateLimitWindow.MINUTE:
            return 60
        elif self.window == RateLimitWindow.HOUR:
            return 3600
        elif self.window == RateLimitWindow.DAY:
            return 86400
        return 60


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None


class RateLimiter:
    """Redis-based distributed rate limiter with tenant isolation."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.settings = get_settings()
        self.default_limits = self._get_default_limits()
    
    def _get_default_limits(self) -> Dict[RateLimitType, RateLimit]:
        """Get default rate limits from configuration."""
        return {
            RateLimitType.API_CALLS: RateLimit(1000, RateLimitWindow.HOUR, 100),
            RateLimitType.JIRA_REQUESTS: RateLimit(
                self.settings.security.rate_limit_jira, 
                RateLimitWindow.MINUTE
            ),
            RateLimitType.GITHUB_REQUESTS: RateLimit(
                self.settings.security.rate_limit_github, 
                RateLimitWindow.HOUR
            ),
            RateLimitType.SLACK_MESSAGES: RateLimit(
                self.settings.security.rate_limit_slack, 
                RateLimitWindow.MINUTE
            ),
            RateLimitType.TEAMS_MESSAGES: RateLimit(
                self.settings.security.rate_limit_teams, 
                RateLimitWindow.MINUTE
            ),
            RateLimitType.WEBHOOK_CALLS: RateLimit(200, RateLimitWindow.MINUTE),
            RateLimitType.LOGIN_ATTEMPTS: RateLimit(10, RateLimitWindow.MINUTE),
        }
    
    async def _ensure_redis_connection(self) -> None:
        """Ensure Redis connection is available."""
        if self.redis is None:
            self.redis = redis.from_url(
                self.settings.redis_url,
                password=self.settings.redis_password,
                decode_responses=True
            )
    
    def _get_rate_limit_key(
        self, 
        rate_limit_type: RateLimitType, 
        identifier: str, 
        window_start: int
    ) -> str:
        """Generate rate limit key for Redis."""
        return f"rate_limit:{rate_limit_type.value}:{identifier}:{window_start}"
    
    async def check_rate_limit(
        self,
        rate_limit_type: RateLimitType,
        identifier: str,
        tenant_id: Optional[str] = None,
        custom_limit: Optional[RateLimit] = None
    ) -> RateLimitResult:
        """Check if request is within rate limits."""
        await self._ensure_redis_connection()
        
        # Get rate limit configuration
        rate_limit = custom_limit or self.default_limits.get(rate_limit_type)
        if not rate_limit:
            return RateLimitResult(allowed=True, remaining=999999, reset_time=0)
        
        now = int(time.time())
        window_seconds = rate_limit.get_window_seconds()
        window_start = (now // window_seconds) * window_seconds
        
        # Create Redis key with tenant isolation
        if tenant_id:
            key = self._get_rate_limit_key(rate_limit_type, f"{tenant_id}:{identifier}", window_start)
        else:
            key = self._get_rate_limit_key(rate_limit_type, identifier, window_start)
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()
            
            current_count = results[0]
            reset_time = window_start + window_seconds
            
            # Check against burst limit first (if configured)
            if rate_limit.burst_limit and current_count > rate_limit.burst_limit:
                remaining = 0
                retry_after = reset_time - now
                
                # Log rate limit violation
                await audit(
                    event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
                    tenant_id=tenant_id,
                    severity=AuditSeverity.MEDIUM,
                    details={
                        "rate_limit_type": rate_limit_type.value,
                        "identifier": identifier,
                        "current_count": current_count,
                        "burst_limit": rate_limit.burst_limit,
                        "window": rate_limit.window.value
                    }
                )
                
                return RateLimitResult(
                    allowed=False,
                    remaining=remaining,
                    reset_time=reset_time,
                    retry_after=retry_after
                )
            
            # Check against regular limit
            if current_count > rate_limit.limit:
                remaining = 0
                retry_after = reset_time - now
                
                # Log rate limit violation
                await audit(
                    event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
                    tenant_id=tenant_id,
                    severity=AuditSeverity.MEDIUM,
                    details={
                        "rate_limit_type": rate_limit_type.value,
                        "identifier": identifier,
                        "current_count": current_count,
                        "limit": rate_limit.limit,
                        "window": rate_limit.window.value
                    }
                )
                
                return RateLimitResult(
                    allowed=False,
                    remaining=remaining,
                    reset_time=reset_time,
                    retry_after=retry_after
                )
            
            # Request allowed
            remaining = max(0, rate_limit.limit - current_count)
            
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_time=reset_time
            )
            
        except Exception as e:
            logger.error(
                "Rate limit check failed",
                error=str(e),
                rate_limit_type=rate_limit_type.value,
                identifier=identifier,
                tenant_id=tenant_id,
                exc_info=True
            )
            # Fail open - allow request if Redis is down
            return RateLimitResult(allowed=True, remaining=999999, reset_time=0)
    
    async def reset_rate_limit(
        self,
        rate_limit_type: RateLimitType,
        identifier: str,
        tenant_id: Optional[str] = None
    ) -> None:
        """Reset rate limit for a specific identifier."""
        await self._ensure_redis_connection()
        
        # Find and delete all keys for this identifier
        pattern = f"rate_limit:{rate_limit_type.value}:{tenant_id}:{identifier}:*" if tenant_id else f"rate_limit:{rate_limit_type.value}:{identifier}:*"
        
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
                
            logger.info(
                "Rate limit reset",
                rate_limit_type=rate_limit_type.value,
                identifier=identifier,
                tenant_id=tenant_id,
                keys_deleted=len(keys)
            )
            
        except Exception as e:
            logger.error(
                "Failed to reset rate limit",
                error=str(e),
                rate_limit_type=rate_limit_type.value,
                identifier=identifier,
                tenant_id=tenant_id,
                exc_info=True
            )
    
    async def get_current_usage(
        self,
        rate_limit_type: RateLimitType,
        identifier: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Get current usage statistics."""
        await self._ensure_redis_connection()
        
        rate_limit = self.default_limits.get(rate_limit_type)
        if not rate_limit:
            return {}
        
        now = int(time.time())
        window_seconds = rate_limit.get_window_seconds()
        window_start = (now // window_seconds) * window_seconds
        
        if tenant_id:
            key = self._get_rate_limit_key(rate_limit_type, f"{tenant_id}:{identifier}", window_start)
        else:
            key = self._get_rate_limit_key(rate_limit_type, identifier, window_start)
        
        try:
            current_count = await self.redis.get(key) or 0
            return {
                "current_count": int(current_count),
                "limit": rate_limit.limit,
                "remaining": max(0, rate_limit.limit - int(current_count)),
                "reset_time": window_start + window_seconds,
                "window": rate_limit.window.value
            }
        except Exception as e:
            logger.error("Failed to get usage stats", error=str(e), exc_info=True)
            return {}


class RateLimitMiddleware:
    """FastAPI middleware for automatic rate limiting."""
    
    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter
    
    async def __call__(self, request: Request, call_next):
        """Apply rate limiting to requests."""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        
        # Extract tenant and user info
        tenant_id = request.headers.get("X-Tenant-ID")
        user_id = None
        
        # Try to extract user from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from driftor.core.auth import get_auth_manager
                auth_manager = get_auth_manager()
                token = auth_header.split(" ")[1]
                token_payload = auth_manager.verify_token(token)
                user_id = token_payload.sub
                tenant_id = token_payload.tenant_id
            except:
                pass  # Invalid token, continue with IP-based limiting
        
        # Use IP address as fallback identifier
        client_ip = request.client.host if request.client else "unknown"
        identifier = user_id or client_ip
        
        # Check API rate limit
        result = await self.rate_limiter.check_rate_limit(
            RateLimitType.API_CALLS,
            identifier,
            tenant_id
        )
        
        if not result.allowed:
            # Log suspicious activity for excessive requests
            if identifier == client_ip:  # IP-based limiting triggered
                await audit(
                    event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
                    severity=AuditSeverity.HIGH,
                    details={
                        "reason": "excessive_api_requests",
                        "ip_address": client_ip,
                        "path": request.url.path,
                        "remaining": result.remaining
                    },
                    ip_address=client_ip
                )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests",
                    "retry_after": result.retry_after,
                    "reset_time": result.reset_time
                },
                headers={
                    "X-RateLimit-Limit": str(self.rate_limiter.default_limits[RateLimitType.API_CALLS].limit),
                    "X-RateLimit-Remaining": str(result.remaining),
                    "X-RateLimit-Reset": str(result.reset_time),
                    "Retry-After": str(result.retry_after) if result.retry_after else "60"
                }
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.default_limits[RateLimitType.API_CALLS].limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_time)
        
        return response


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


async def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    
    return _rate_limiter


async def check_rate_limit(
    rate_limit_type: RateLimitType,
    identifier: str,
    tenant_id: Optional[str] = None,
    custom_limit: Optional[RateLimit] = None
) -> RateLimitResult:
    """Convenience function to check rate limits."""
    rate_limiter = await get_rate_limiter()
    return await rate_limiter.check_rate_limit(
        rate_limit_type, identifier, tenant_id, custom_limit
    )