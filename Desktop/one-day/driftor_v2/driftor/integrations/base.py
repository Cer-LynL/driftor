"""
Base integration framework with enterprise security and rate limiting.
"""
import asyncio
import hashlib
import hmac
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import httpx
from pydantic import BaseModel, Field
import structlog

from driftor.core.config import get_settings
from driftor.core.rate_limiter import RateLimitType, check_rate_limit
from driftor.security.audit import audit, AuditEventType, AuditSeverity
from driftor.security.encryption import get_encryption_manager

logger = structlog.get_logger(__name__)


class IntegrationStatus(str, Enum):
    """Integration connection status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"


class IntegrationError(Exception):
    """Base integration error."""
    pass


class RateLimitError(IntegrationError):
    """Rate limit exceeded error."""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded, retry after {retry_after} seconds")


class AuthenticationError(IntegrationError):
    """Authentication failed error."""
    pass


@dataclass
class IntegrationConfig:
    """Base integration configuration."""
    tenant_id: str
    integration_type: str
    api_base_url: str
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 1
    
    # Security
    verify_ssl: bool = True
    allowed_redirects: int = 0
    
    # Rate limiting
    rate_limit_type: Optional[RateLimitType] = None
    custom_rate_limit: Optional[Dict[str, Any]] = None


@dataclass
class WebhookConfig:
    """Webhook configuration for integrations."""
    endpoint_url: str
    secret: str
    events: List[str]
    retry_attempts: int = 3
    timeout_seconds: int = 30


class APIResponse(BaseModel):
    """Standardized API response."""
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[int] = None


class BaseIntegration(ABC):
    """Base class for all external integrations."""
    
    def __init__(self, config: IntegrationConfig, credentials: Dict[str, str]):
        self.config = config
        self.credentials = credentials
        self.settings = get_settings()
        self.encryption_manager = get_encryption_manager()
        
        # HTTP client with enterprise security settings
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            verify=config.verify_ssl,
            follow_redirects=config.allowed_redirects > 0,
            limits=httpx.Limits(max_redirects=config.allowed_redirects)
        )
        
        # Status tracking
        self.status = IntegrationStatus.INACTIVE
        self.last_error: Optional[str] = None
        self.last_successful_call: Optional[datetime] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        await self.client.aclose()
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if integration is working correctly."""
        pass
    
    @abstractmethod
    def get_webhook_config(self) -> Optional[WebhookConfig]:
        """Get webhook configuration for this integration."""
        pass
    
    @abstractmethod
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature for security."""
        pass
    
    def get_credential(self, key: str) -> Optional[str]:
        """Get decrypted credential value."""
        encrypted_value = self.credentials.get(key)
        if not encrypted_value:
            return None
        
        try:
            return self.encryption_manager.decrypt_data(
                self.config.tenant_id, 
                encrypted_value
            )
        except Exception as e:
            logger.error(
                "Failed to decrypt credential",
                key=key,
                tenant_id=self.config.tenant_id,
                error=str(e)
            )
            return None
    
    async def _check_rate_limit(self, identifier: str) -> None:
        """Check rate limits before making API calls."""
        if not self.config.rate_limit_type:
            return
        
        result = await check_rate_limit(
            self.config.rate_limit_type,
            identifier,
            self.config.tenant_id
        )
        
        if not result.allowed:
            self.status = IntegrationStatus.RATE_LIMITED
            raise RateLimitError(result.retry_after or 60)
    
    async def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[bytes] = None,
        identifier: Optional[str] = None
    ) -> APIResponse:
        """Make HTTP request with enterprise security and monitoring."""
        # Check rate limits
        if identifier:
            await self._check_rate_limit(identifier)
        
        # Prepare headers with security defaults
        request_headers = {
            "User-Agent": f"Driftor-Enterprise/1.0 (+https://driftor.dev)",
            "Accept": "application/json",
            "Content-Type": "application/json" if json_data else "application/octet-stream"
        }
        if headers:
            request_headers.update(headers)
        
        start_time = time.time()
        
        for attempt in range(self.config.max_retries + 1):
            try:
                # Log API call for audit
                await audit(
                    event_type=AuditEventType.API_CALL_MADE,
                    tenant_id=self.config.tenant_id,
                    resource_type=self.config.integration_type,
                    resource_id=url,
                    action=method.upper(),
                    details={
                        "attempt": attempt + 1,
                        "max_retries": self.config.max_retries,
                        "timeout": self.config.timeout_seconds
                    }
                )
                
                response = await self.client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json_data,
                    content=data
                )
                
                duration = time.time() - start_time
                
                # Extract rate limit headers
                rate_limit_remaining = None
                rate_limit_reset = None
                
                for header_name, value in response.headers.items():
                    header_lower = header_name.lower()
                    if 'rate' in header_lower and 'remaining' in header_lower:
                        try:
                            rate_limit_remaining = int(value)
                        except ValueError:
                            pass
                    elif 'rate' in header_lower and 'reset' in header_lower:
                        try:
                            rate_limit_reset = int(value)
                        except ValueError:
                            pass
                
                # Handle response
                if response.status_code == 429:  # Too Many Requests
                    retry_after = int(response.headers.get('Retry-After', 60))
                    self.status = IntegrationStatus.RATE_LIMITED
                    
                    await audit(
                        event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
                        tenant_id=self.config.tenant_id,
                        severity=AuditSeverity.MEDIUM,
                        resource_type=self.config.integration_type,
                        details={
                            "url": url,
                            "retry_after": retry_after,
                            "attempt": attempt + 1
                        }
                    )
                    
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise RateLimitError(retry_after)
                
                elif response.status_code in [401, 403]:  # Authentication/Authorization
                    self.status = IntegrationStatus.UNAUTHORIZED
                    self.last_error = f"Authentication failed: {response.status_code}"
                    
                    await audit(
                        event_type=AuditEventType.PERMISSION_DENIED,
                        tenant_id=self.config.tenant_id,
                        severity=AuditSeverity.HIGH,
                        resource_type=self.config.integration_type,
                        details={
                            "url": url,
                            "status_code": response.status_code,
                            "response_text": response.text[:500] if response.text else None
                        }
                    )
                    
                    raise AuthenticationError(
                        f"Authentication failed with status {response.status_code}"
                    )
                
                elif response.status_code >= 500:  # Server errors - retry
                    if attempt < self.config.max_retries:
                        delay = self.config.retry_delay_seconds * (2 ** attempt)  # Exponential backoff
                        await asyncio.sleep(delay)
                        continue
                    else:
                        self.status = IntegrationStatus.ERROR
                        self.last_error = f"Server error: {response.status_code}"
                        
                        return APIResponse(
                            success=False,
                            status_code=response.status_code,
                            error=f"Server error: {response.text[:500] if response.text else 'Unknown error'}"
                        )
                
                # Success case
                self.status = IntegrationStatus.ACTIVE
                self.last_successful_call = datetime.now(timezone.utc)
                self.last_error = None
                
                # Parse JSON response
                response_data = None
                if response.headers.get('content-type', '').startswith('application/json'):
                    try:
                        response_data = response.json()
                    except Exception as e:
                        logger.warning(
                            "Failed to parse JSON response",
                            integration=self.config.integration_type,
                            tenant_id=self.config.tenant_id,
                            error=str(e)
                        )
                
                # Log successful API call
                logger.info(
                    "API call successful",
                    integration=self.config.integration_type,
                    tenant_id=self.config.tenant_id,
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    duration=duration,
                    rate_limit_remaining=rate_limit_remaining
                )
                
                return APIResponse(
                    success=True,
                    status_code=response.status_code,
                    data=response_data,
                    rate_limit_remaining=rate_limit_remaining,
                    rate_limit_reset=rate_limit_reset
                )
                
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as e:
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay_seconds * (2 ** attempt)
                    logger.warning(
                        "API call failed, retrying",
                        integration=self.config.integration_type,
                        tenant_id=self.config.tenant_id,
                        method=method,
                        url=url,
                        attempt=attempt + 1,
                        max_retries=self.config.max_retries,
                        delay=delay,
                        error=str(e)
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    self.status = IntegrationStatus.ERROR
                    self.last_error = str(e)
                    
                    await audit(
                        event_type=AuditEventType.API_CALL_MADE,
                        tenant_id=self.config.tenant_id,
                        severity=AuditSeverity.MEDIUM,
                        resource_type=self.config.integration_type,
                        details={
                            "url": url,
                            "error": str(e),
                            "final_attempt": True
                        }
                    )
                    
                    return APIResponse(
                        success=False,
                        status_code=0,
                        error=f"Network error: {str(e)}"
                    )
        
        # Should never reach here
        return APIResponse(
            success=False,
            status_code=0,
            error="Maximum retries exceeded"
        )
    
    def verify_webhook_signature_hmac(
        self, 
        payload: bytes, 
        signature: str, 
        secret: str,
        algorithm: str = "sha256"
    ) -> bool:
        """Verify HMAC-based webhook signature."""
        try:
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                getattr(hashlib, algorithm)
            ).hexdigest()
            
            # Handle different signature formats
            if signature.startswith(f"{algorithm}="):
                signature = signature[len(f"{algorithm}="):]
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(
                "Webhook signature verification failed",
                integration=self.config.integration_type,
                tenant_id=self.config.tenant_id,
                error=str(e)
            )
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the integration."""
        try:
            is_healthy = await self.test_connection()
            
            return {
                "integration_type": self.config.integration_type,
                "tenant_id": self.config.tenant_id,
                "status": self.status.value,
                "healthy": is_healthy,
                "last_successful_call": self.last_successful_call.isoformat() if self.last_successful_call else None,
                "last_error": self.last_error,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.status = IntegrationStatus.ERROR
            self.last_error = str(e)
            
            return {
                "integration_type": self.config.integration_type,
                "tenant_id": self.config.tenant_id,
                "status": self.status.value,
                "healthy": False,
                "last_error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }