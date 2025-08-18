"""
Enterprise authentication and authorization system with SSO support.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import structlog

from driftor.core.config import get_settings
from driftor.security.audit import audit, AuditEventType, AuditSeverity
from driftor.models.tenant import TenantUser, TenantRole, TenantUserRole, Tenant

logger = structlog.get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token handler
security = HTTPBearer()


class TokenType(str):
    """JWT token types."""
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    WEBHOOK = "webhook"


class AuthenticationError(Exception):
    """Authentication related errors."""
    pass


class AuthorizationError(Exception):
    """Authorization related errors."""
    pass


class TokenPayload(BaseModel):
    """JWT token payload structure."""
    sub: str  # User ID
    tenant_id: str
    token_type: str
    exp: int
    iat: int
    jti: str  # Token ID for revocation
    scopes: List[str] = []
    session_id: Optional[str] = None


class AuthUser(BaseModel):
    """Authenticated user context."""
    id: str
    tenant_id: str
    email: str
    username: Optional[str]
    full_name: Optional[str]
    is_active: bool
    roles: List[str]
    permissions: List[str]
    session_id: Optional[str]
    is_sso_user: bool
    mfa_enabled: bool


class AuthManager:
    """Enterprise authentication manager."""
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.settings = get_settings()
        self._revoked_tokens: set = set()  # In production, use Redis
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def generate_token(
        self,
        user_id: str,
        tenant_id: str,
        token_type: str = TokenType.ACCESS,
        scopes: List[str] = None,
        session_id: Optional[str] = None,
        expires_delta: Optional[timedelta] = None
    ) -> Tuple[str, datetime]:
        """Generate JWT token."""
        now = datetime.now(timezone.utc)
        
        if expires_delta:
            expire = now + expires_delta
        else:
            # Default expiration times
            if token_type == TokenType.ACCESS:
                expire = now + timedelta(hours=self.settings.security.jwt_expiration_hours)
            elif token_type == TokenType.REFRESH:
                expire = now + timedelta(days=30)
            elif token_type == TokenType.API_KEY:
                expire = now + timedelta(days=365)
            else:
                expire = now + timedelta(hours=1)
        
        # Generate unique token ID for revocation support
        jti = secrets.token_urlsafe(32)
        
        payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "token_type": token_type,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
            "jti": jti,
            "scopes": scopes or [],
            "session_id": session_id
        }
        
        token = jwt.encode(
            payload,
            self.settings.security.jwt_secret_key,
            algorithm=self.settings.security.jwt_algorithm
        )
        
        return token, expire
    
    def verify_token(self, token: str) -> TokenPayload:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.settings.security.jwt_secret_key,
                algorithms=[self.settings.security.jwt_algorithm]
            )
            
            # Check if token is revoked
            jti = payload.get("jti")
            if jti in self._revoked_tokens:
                raise AuthenticationError("Token has been revoked")
            
            return TokenPayload(**payload)
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.JWTError as e:
            raise AuthenticationError(f"Invalid token: {e}")
    
    def revoke_token(self, jti: str) -> None:
        """Revoke a token by its JTI."""
        self._revoked_tokens.add(jti)
        # In production, store in Redis with expiration
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
        tenant_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[TenantUser, str]:
        """Authenticate user with email/password."""
        if not self.db_session:
            raise AuthenticationError("Database session not available")
        
        # Find user in tenant
        user = self.db_session.query(TenantUser).filter(
            TenantUser.tenant_id == tenant_id,
            TenantUser.email == email,
            TenantUser.is_active == True,
            TenantUser.is_deleted == False
        ).first()
        
        if not user:
            await audit(
                event_type=AuditEventType.USER_LOGIN_FAILED,
                tenant_id=tenant_id,
                severity=AuditSeverity.MEDIUM,
                details={"email": email, "reason": "user_not_found"},
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise AuthenticationError("Invalid credentials")
        
        # Check if account is locked
        if user.is_locked():
            await audit(
                event_type=AuditEventType.USER_LOGIN_FAILED,
                tenant_id=tenant_id,
                user_id=str(user.id),
                severity=AuditSeverity.HIGH,
                details={"email": email, "reason": "account_locked"},
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise AuthenticationError("Account is locked")
        
        # Verify password
        if not user.password_hash or not self.verify_password(password, user.password_hash):
            # Increment failed attempts
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.lock_account(duration_minutes=30)
                
                await audit(
                    event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
                    tenant_id=tenant_id,
                    user_id=str(user.id),
                    severity=AuditSeverity.HIGH,
                    details={"email": email, "reason": "account_locked_after_failed_attempts"},
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            
            self.db_session.commit()
            
            await audit(
                event_type=AuditEventType.USER_LOGIN_FAILED,
                tenant_id=tenant_id,
                user_id=str(user.id),
                severity=AuditSeverity.MEDIUM,
                details={"email": email, "reason": "invalid_password"},
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise AuthenticationError("Invalid credentials")
        
        # Reset failed attempts on successful password verification
        if user.failed_login_attempts > 0:
            user.failed_login_attempts = 0
        
        # Generate session ID
        session_id = secrets.token_urlsafe(32)
        
        # Update last login
        user.last_login_at = user.encrypt_field(
            'last_login_at',
            datetime.now(timezone.utc).isoformat()
        )
        
        self.db_session.commit()
        
        await audit(
            event_type=AuditEventType.USER_LOGIN,
            tenant_id=tenant_id,
            user_id=str(user.id),
            session_id=session_id,
            details={"email": email, "method": "password"},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return user, session_id
    
    async def get_user_permissions(self, user_id: str, tenant_id: str) -> List[str]:
        """Get all permissions for a user."""
        if not self.db_session:
            return []
        
        # Query user roles and their permissions
        permissions = set()
        
        user_roles = self.db_session.query(TenantUserRole).filter(
            TenantUserRole.tenant_id == tenant_id,
            TenantUserRole.user_id == user_id,
            TenantUserRole.is_deleted == False
        ).all()
        
        for user_role in user_roles:
            role = self.db_session.query(TenantRole).filter(
                TenantRole.id == user_role.role_id,
                TenantRole.tenant_id == tenant_id,
                TenantRole.is_deleted == False
            ).first()
            
            if role and role.permissions:
                permissions.update(role.permissions)
        
        return list(permissions)
    
    async def create_auth_user(self, user: TenantUser, session_id: Optional[str] = None) -> AuthUser:
        """Create AuthUser from TenantUser."""
        permissions = await self.get_user_permissions(str(user.id), user.tenant_id)
        
        # Get role names
        user_roles = self.db_session.query(TenantUserRole).filter(
            TenantUserRole.tenant_id == user.tenant_id,
            TenantUserRole.user_id == str(user.id),
            TenantUserRole.is_deleted == False
        ).all()
        
        role_names = []
        for user_role in user_roles:
            role = self.db_session.query(TenantRole).filter(
                TenantRole.id == user_role.role_id
            ).first()
            if role:
                role_names.append(role.name)
        
        return AuthUser(
            id=str(user.id),
            tenant_id=user.tenant_id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=role_names,
            permissions=permissions,
            session_id=session_id,
            is_sso_user=user.is_sso_user,
            mfa_enabled=user.mfa_enabled
        )


class PermissionChecker:
    """Role-based access control (RBAC) permission checker."""
    
    def __init__(self, required_permissions: List[str]):
        self.required_permissions = required_permissions
    
    def __call__(self, current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
        """Check if user has required permissions."""
        missing_permissions = set(self.required_permissions) - set(current_user.permissions)
        
        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Missing: {', '.join(missing_permissions)}"
            )
        
        return current_user


# Global auth manager
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get global auth manager instance."""
    global _auth_manager
    
    if _auth_manager is None:
        _auth_manager = AuthManager()
    
    return _auth_manager


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthUser:
    """Get current authenticated user from JWT token."""
    try:
        auth_manager = get_auth_manager()
        
        # Verify token
        token_payload = auth_manager.verify_token(credentials.credentials)
        
        # Get user from database
        if not auth_manager.db_session:
            from driftor.core.database import get_db_session
            auth_manager.db_session = next(get_db_session())
        
        user = auth_manager.db_session.query(TenantUser).filter(
            TenantUser.id == token_payload.sub,
            TenantUser.tenant_id == token_payload.tenant_id,
            TenantUser.is_active == True,
            TenantUser.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create auth user
        auth_user = await auth_manager.create_auth_user(user, token_payload.session_id)
        
        # Audit API access
        await audit(
            event_type=AuditEventType.DATA_READ,
            tenant_id=auth_user.tenant_id,
            user_id=auth_user.id,
            session_id=auth_user.session_id,
            resource_type="API",
            resource_id=request.url.path,
            action="ACCESS",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        return auth_user
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error("Authentication error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_active_user(
    current_user: AuthUser = Depends(get_current_user)
) -> AuthUser:
    """Get current active user (additional check for active status)."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_permissions(*permissions: str):
    """Decorator to require specific permissions."""
    return PermissionChecker(list(permissions))


# Common permission checks
require_admin = require_permissions("admin.full_access")
require_user_management = require_permissions("users.manage")
require_integration_management = require_permissions("integrations.manage")
require_analytics_read = require_permissions("analytics.read")