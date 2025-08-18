"""
Tenant management models for multi-tenant architecture.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from sqlalchemy import Column, String, Boolean, Integer, Text, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel as PydanticModel, Field, validator

from .base import BaseModel, EncryptedFieldMixin


class TenantStatus(str, Enum):
    """Tenant status enumeration."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TenantTier(str, Enum):
    """Tenant pricing tier enumeration."""
    TRIAL = "trial"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class Tenant(BaseModel, EncryptedFieldMixin):
    """Multi-tenant organization model."""
    
    __tablename__ = "tenants"
    
    # Basic information
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    domain = Column(String(255), nullable=True)
    
    # Status and tier
    status = Column(String(20), nullable=False, default=TenantStatus.TRIAL)
    tier = Column(String(20), nullable=False, default=TenantTier.TRIAL)
    
    # Subscription information
    subscription_id = Column(String(100), nullable=True)  # External billing system ID
    trial_ends_at = Column(String(255), nullable=True)  # Encrypted
    subscription_ends_at = Column(String(255), nullable=True)  # Encrypted
    
    # Usage limits based on tier
    max_users = Column(Integer, nullable=False, default=5)
    max_integrations = Column(Integer, nullable=False, default=3)
    max_api_calls_per_month = Column(Integer, nullable=False, default=1000)
    max_storage_gb = Column(Integer, nullable=False, default=5)
    
    # Current usage tracking
    current_users = Column(Integer, nullable=False, default=0)
    current_integrations = Column(Integer, nullable=False, default=0)
    current_api_calls_this_month = Column(Integer, nullable=False, default=0)
    current_storage_gb = Column(Integer, nullable=False, default=0)
    
    # Configuration
    settings = Column(JSONB, nullable=True, default=dict)
    
    # Contact information
    admin_email = Column(String(255), nullable=False)
    admin_name = Column(String(255), nullable=True)
    
    # Security settings
    encryption_key_id = Column(String(100), nullable=True)  # Reference to key in Vault
    require_2fa = Column(Boolean, nullable=False, default=False)
    allowed_ip_ranges = Column(JSONB, nullable=True)  # List of CIDR blocks
    session_timeout_minutes = Column(Integer, nullable=False, default=480)
    
    # Compliance settings
    data_residency_region = Column(String(10), nullable=False, default="US")
    gdpr_compliance_mode = Column(Boolean, nullable=False, default=True)
    audit_retention_days = Column(Integer, nullable=False, default=2555)  # 7 years
    
    # Feature flags
    features_enabled = Column(JSONB, nullable=True, default=dict)
    
    __table_args__ = (
        Index('idx_tenant_status_tier', 'status', 'tier'),
        Index('idx_tenant_domain', 'domain'),
    )
    
    def is_active(self) -> bool:
        """Check if tenant is active."""
        return self.status == TenantStatus.ACTIVE
    
    def is_trial(self) -> bool:
        """Check if tenant is on trial."""
        return self.tier == TenantTier.TRIAL
    
    def has_feature(self, feature_name: str) -> bool:
        """Check if tenant has a specific feature enabled."""
        if not self.features_enabled:
            return False
        return self.features_enabled.get(feature_name, False)
    
    def within_usage_limits(self) -> Dict[str, bool]:
        """Check if tenant is within usage limits."""
        return {
            "users": self.current_users <= self.max_users,
            "integrations": self.current_integrations <= self.max_integrations,
            "api_calls": self.current_api_calls_this_month <= self.max_api_calls_per_month,
            "storage": self.current_storage_gb <= self.max_storage_gb
        }
    
    def increment_usage(self, metric: str, amount: int = 1) -> None:
        """Increment usage counter for a metric."""
        if metric == "users":
            self.current_users += amount
        elif metric == "integrations":
            self.current_integrations += amount
        elif metric == "api_calls":
            self.current_api_calls_this_month += amount
        elif metric == "storage":
            self.current_storage_gb += amount
    
    def reset_monthly_usage(self) -> None:
        """Reset monthly usage counters."""
        self.current_api_calls_this_month = 0


class TenantUser(BaseModel):
    """Users within a tenant."""
    
    __tablename__ = "tenant_users"
    
    # User identification
    email = Column(String(255), nullable=False, index=True)
    username = Column(String(100), nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    
    # Authentication
    password_hash = Column(String(255), nullable=True)  # Nullable for SSO-only users
    is_sso_user = Column(Boolean, nullable=False, default=False)
    sso_provider = Column(String(50), nullable=True)
    sso_subject_id = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    last_login_at = Column(String(255), nullable=True)  # Encrypted
    
    # Security
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    mfa_secret = Column(String(255), nullable=True)  # Encrypted TOTP secret
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(String(255), nullable=True)  # Encrypted timestamp
    
    # Profile
    timezone = Column(String(50), nullable=False, default="UTC")
    language = Column(String(10), nullable=False, default="en")
    preferences = Column(JSONB, nullable=True, default=dict)
    
    __table_args__ = (
        Index('idx_tenant_user_email', 'tenant_id', 'email', unique=True),
        Index('idx_tenant_user_username', 'tenant_id', 'username'),
        Index('idx_tenant_user_sso', 'sso_provider', 'sso_subject_id'),
    )
    
    def has_mfa_enabled(self) -> bool:
        """Check if user has MFA enabled."""
        return self.mfa_enabled and self.mfa_secret is not None
    
    def is_locked(self) -> bool:
        """Check if user account is locked."""
        if not self.locked_until:
            return False
        
        # Decrypt and check timestamp
        try:
            locked_until_str = self.decrypt_field('locked_until', self.locked_until)
            locked_until = datetime.fromisoformat(locked_until_str)
            return datetime.now(timezone.utc) < locked_until
        except:
            return False
    
    def lock_account(self, duration_minutes: int = 30) -> None:
        """Lock user account for specified duration."""
        locked_until = datetime.now(timezone.utc).replace(
            microsecond=0
        ) + datetime.timedelta(minutes=duration_minutes)
        
        self.locked_until = self.encrypt_field(
            'locked_until', 
            locked_until.isoformat()
        )
    
    def unlock_account(self) -> None:
        """Unlock user account."""
        self.locked_until = None
        self.failed_login_attempts = 0


class TenantRole(BaseModel):
    """Roles within a tenant for RBAC."""
    
    __tablename__ = "tenant_roles"
    
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(JSONB, nullable=False, default=list)  # List of permission strings
    is_system_role = Column(Boolean, nullable=False, default=False)
    
    __table_args__ = (
        Index('idx_tenant_role_name', 'tenant_id', 'name', unique=True),
    )


class TenantUserRole(BaseModel):
    """Many-to-many relationship between users and roles."""
    
    __tablename__ = "tenant_user_roles"
    
    user_id = Column(String(100), nullable=False, index=True)
    role_id = Column(String(100), nullable=False, index=True)
    
    # Assignment metadata
    assigned_by = Column(String(100), nullable=True)
    assigned_at = Column(String(255), nullable=True)  # Encrypted
    expires_at = Column(String(255), nullable=True)  # Encrypted, for temporary roles
    
    __table_args__ = (
        Index('idx_tenant_user_role', 'tenant_id', 'user_id', 'role_id', unique=True),
    )


# Pydantic models for API serialization
class TenantCreate(PydanticModel):
    """Tenant creation model."""
    
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, regex=r'^[a-z0-9-_]+$')
    domain: Optional[str] = Field(None, max_length=255)
    admin_email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    admin_name: Optional[str] = Field(None, max_length=255)
    tier: TenantTier = TenantTier.TRIAL
    
    @validator('slug')
    def validate_slug(cls, v):
        """Ensure slug is URL-safe."""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Slug must contain only letters, numbers, hyphens, and underscores')
        return v.lower()


class TenantResponse(PydanticModel):
    """Tenant response model."""
    
    id: str
    name: str
    slug: str
    domain: Optional[str]
    status: TenantStatus
    tier: TenantTier
    max_users: int
    current_users: int
    features_enabled: Dict[str, bool]
    created_at: datetime
    
    class Config:
        from_attributes = True


class TenantUserCreate(PydanticModel):
    """Tenant user creation model."""
    
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=12)
    is_sso_user: bool = False
    timezone: str = "UTC"
    language: str = "en"
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if v is None:
            return v
            
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters long')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v)
        
        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(
                'Password must contain uppercase, lowercase, digit, and special character'
            )
        
        return v


class TenantUserResponse(PydanticModel):
    """Tenant user response model."""
    
    id: str
    email: str
    username: Optional[str]
    full_name: Optional[str]
    is_active: bool
    email_verified: bool
    is_sso_user: bool
    mfa_enabled: bool
    timezone: str
    language: str
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True