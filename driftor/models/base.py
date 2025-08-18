"""
Enterprise multi-tenant database models with encryption and audit support.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import Column, String, DateTime, Boolean, Text, event
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import Session
import structlog

from driftor.security.encryption import get_encryption_manager
from driftor.security.audit import audit, AuditEventType, AuditSeverity

logger = structlog.get_logger(__name__)

Base = declarative_base()


class TenantMixin:
    """Mixin for multi-tenant models with automatic tenant isolation."""
    
    @declared_attr
    def tenant_id(cls):
        return Column(String(100), nullable=False, index=True)
    
    @declared_attr
    def __table_args__(cls):
        # Add RLS (Row Level Security) policy for tenant isolation
        return (
            {'postgresql_row_level_security': True},
        )


class AuditMixin:
    """Mixin for automatic audit trail creation."""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    @declared_attr
    def updated_at(cls):
        return Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), 
                     onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    @declared_attr
    def created_by(cls):
        return Column(String(100), nullable=True)
    
    @declared_attr
    def updated_by(cls):
        return Column(String(100), nullable=True)


class EncryptedFieldMixin:
    """Mixin for models with encrypted fields."""
    
    def encrypt_field(self, field_name: str, value: str) -> str:
        """Encrypt a field value using tenant-specific encryption."""
        if not value or not hasattr(self, 'tenant_id'):
            return value
        
        encryption_manager = get_encryption_manager()
        return encryption_manager.encrypt_data(self.tenant_id, value)
    
    def decrypt_field(self, field_name: str, encrypted_value: str) -> str:
        """Decrypt a field value using tenant-specific encryption."""
        if not encrypted_value or not hasattr(self, 'tenant_id'):
            return encrypted_value
        
        encryption_manager = get_encryption_manager()
        try:
            return encryption_manager.decrypt_data(self.tenant_id, encrypted_value)
        except Exception as e:
            logger.warning(
                "Failed to decrypt field, assuming plaintext",
                field=field_name,
                tenant_id=getattr(self, 'tenant_id', None),
                error=str(e)
            )
            return encrypted_value


class BaseModel(Base, TenantMixin, AuditMixin):
    """Base model with tenant isolation and audit trail."""
    
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Soft delete support
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(100), nullable=True)
    
    def soft_delete(self, user_id: Optional[str] = None) -> None:
        """Soft delete the record."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = user_id
    
    def restore(self, user_id: Optional[str] = None) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.updated_by = user_id
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert model to dictionary, optionally excluding sensitive fields."""
        result = {}
        
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            
            # Handle UUID serialization
            if isinstance(value, uuid.UUID):
                value = str(value)
            
            # Handle datetime serialization
            elif isinstance(value, datetime):
                value = value.isoformat()
            
            # Exclude sensitive fields unless explicitly requested
            if not include_sensitive and 'password' in column.name.lower():
                continue
            if not include_sensitive and 'secret' in column.name.lower():
                continue
            if not include_sensitive and 'token' in column.name.lower():
                continue
            
            result[column.name] = value
        
        return result
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the table name for this model."""
        return cls.__tablename__


# Audit event listeners for automatic audit trail
@event.listens_for(BaseModel, 'after_insert', propagate=True)
def audit_insert(mapper, connection, target):
    """Audit record creation."""
    # Skip if already in audit table to prevent recursion
    if hasattr(target, '__tablename__') and target.__tablename__ == 'audit_logs':
        return
    
    # Use a separate session for audit to avoid transaction conflicts
    try:
        from driftor.core.database import get_audit_session
        audit_session = get_audit_session()
        
        # Create audit event asynchronously
        import asyncio
        asyncio.create_task(audit(
            event_type=AuditEventType.DATA_CREATED,
            tenant_id=getattr(target, 'tenant_id', None),
            user_id=getattr(target, 'created_by', None),
            resource_type=target.__class__.__name__,
            resource_id=str(target.id),
            action="CREATE",
            details={
                "table": target.__tablename__,
                "fields_changed": list(target.to_dict().keys())
            }
        ))
    except Exception as e:
        logger.warning("Failed to create audit record for insert", error=str(e))


@event.listens_for(BaseModel, 'after_update', propagate=True)
def audit_update(mapper, connection, target):
    """Audit record updates."""
    # Skip if already in audit table to prevent recursion
    if hasattr(target, '__tablename__') and target.__tablename__ == 'audit_logs':
        return
    
    try:
        # Determine which fields changed
        changed_fields = []
        for attr in mapper.attrs:
            hist = getattr(target, attr.key + '_history', None)
            if hist and hist.has_changes():
                changed_fields.append(attr.key)
        
        if changed_fields:
            import asyncio
            asyncio.create_task(audit(
                event_type=AuditEventType.DATA_UPDATED,
                tenant_id=getattr(target, 'tenant_id', None),
                user_id=getattr(target, 'updated_by', None),
                resource_type=target.__class__.__name__,
                resource_id=str(target.id),
                action="UPDATE",
                details={
                    "table": target.__tablename__,
                    "fields_changed": changed_fields
                }
            ))
    except Exception as e:
        logger.warning("Failed to create audit record for update", error=str(e))


@event.listens_for(BaseModel, 'after_delete', propagate=True)
def audit_delete(mapper, connection, target):
    """Audit record deletion."""
    # Skip if already in audit table to prevent recursion
    if hasattr(target, '__tablename__') and target.__tablename__ == 'audit_logs':
        return
    
    try:
        import asyncio
        asyncio.create_task(audit(
            event_type=AuditEventType.DATA_DELETED,
            tenant_id=getattr(target, 'tenant_id', None),
            resource_type=target.__class__.__name__,
            resource_id=str(target.id),
            action="DELETE",
            details={
                "table": target.__tablename__,
                "soft_delete": getattr(target, 'is_deleted', False)
            },
            severity=AuditSeverity.MEDIUM
        ))
    except Exception as e:
        logger.warning("Failed to create audit record for delete", error=str(e))