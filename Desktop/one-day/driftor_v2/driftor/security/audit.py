"""
Enterprise audit logging system for compliance and security monitoring.
Implements immutable audit trails with structured logging.
"""
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
import structlog
from sqlalchemy import Column, String, DateTime, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base

logger = structlog.get_logger(__name__)

Base = declarative_base()


class AuditEventType(str, Enum):
    """Types of auditable events."""
    
    # Authentication events
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_LOGIN_FAILED = "user.login.failed"
    PASSWORD_CHANGED = "user.password.changed"
    
    # Authorization events
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_DENIED = "permission.denied"
    ROLE_ASSIGNED = "role.assigned"
    ROLE_REMOVED = "role.removed"
    
    # Data access events
    DATA_READ = "data.read"
    DATA_CREATED = "data.created"
    DATA_UPDATED = "data.updated"
    DATA_DELETED = "data.deleted"
    DATA_EXPORTED = "data.exported"
    
    # Integration events
    INTEGRATION_CONNECTED = "integration.connected"
    INTEGRATION_DISCONNECTED = "integration.disconnected"
    WEBHOOK_RECEIVED = "webhook.received"
    API_CALL_MADE = "api.call.made"
    
    # Analysis events
    TICKET_ANALYZED = "ticket.analyzed"
    CODE_SCANNED = "code.scanned"
    SUGGESTION_GENERATED = "suggestion.generated"
    NOTIFICATION_SENT = "notification.sent"
    
    # Configuration events
    SETTINGS_CHANGED = "settings.changed"
    TENANT_CREATED = "tenant.created"
    TENANT_DELETED = "tenant.deleted"
    
    # Security events
    SUSPICIOUS_ACTIVITY = "security.suspicious"
    RATE_LIMIT_EXCEEDED = "security.rate_limit"
    ENCRYPTION_ERROR = "security.encryption.error"
    ACCESS_DENIED = "security.access.denied"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuditEvent(BaseModel):
    """Structured audit event model."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.LOW
    
    # Context information
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Event details
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    
    # Additional context
    details: Dict[str, Any] = Field(default_factory=dict)
    
    # Security classification
    sensitive_data: bool = False
    compliance_relevant: bool = True
    
    class Config:
        use_enum_values = True


class AuditLog(Base):
    """Database model for audit logs."""
    
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    
    # Tenant isolation
    tenant_id = Column(String(100), nullable=True, index=True)
    
    # User context
    user_id = Column(String(100), nullable=True, index=True)
    session_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    
    # Resource information
    resource_type = Column(String(100), nullable=True, index=True)
    resource_id = Column(String(100), nullable=True, index=True)
    action = Column(String(100), nullable=True)
    
    # Event details (encrypted if sensitive)
    details = Column(JSONB, nullable=True)
    
    # Metadata
    sensitive_data = Column(Boolean, default=False, nullable=False)
    compliance_relevant = Column(Boolean, default=True, nullable=False)
    hash_digest = Column(String(64), nullable=False)  # For integrity verification
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_audit_tenant_timestamp', 'tenant_id', 'timestamp'),
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_event_type_timestamp', 'event_type', 'timestamp'),
        Index('idx_audit_compliance_timestamp', 'compliance_relevant', 'timestamp'),
    )


class AuditLogger:
    """Enterprise audit logging manager."""
    
    def __init__(self, db_session=None, encryption_manager=None):
        self.db_session = db_session
        self.encryption_manager = encryption_manager
        self.structured_logger = structlog.get_logger("audit")
    
    async def log_event(self, event: AuditEvent) -> str:
        """Log an audit event to both structured logs and database."""
        try:
            # Log to structured logger first (immediate)
            self.structured_logger.info(
                "Audit event",
                event_id=event.id,
                event_type=event.event_type,
                severity=event.severity,
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                action=event.action,
                ip_address=event.ip_address,
                sensitive=event.sensitive_data,
                compliance=event.compliance_relevant,
                details=event.details if not event.sensitive_data else "[REDACTED]"
            )
            
            # Store in database if session available
            if self.db_session:
                await self._store_audit_record(event)
            
            return event.id
            
        except Exception as e:
            logger.error(
                "Failed to log audit event",
                event_type=event.event_type,
                error=str(e),
                exc_info=True
            )
            # Never fail the main operation due to audit logging
            return event.id
    
    async def _store_audit_record(self, event: AuditEvent) -> None:
        """Store audit event in database with encryption if needed."""
        details = event.details
        
        # Encrypt sensitive details
        if event.sensitive_data and self.encryption_manager and event.tenant_id:
            details = {
                "encrypted": True,
                "data": self.encryption_manager.encrypt_data(
                    event.tenant_id, 
                    json.dumps(event.details)
                )
            }
        
        # Calculate integrity hash
        hash_content = f"{event.timestamp.isoformat()}{event.event_type}{event.tenant_id}{event.user_id}"
        hash_digest = hashlib.sha256(hash_content.encode()).hexdigest()
        
        audit_record = AuditLog(
            id=uuid.UUID(event.id),
            timestamp=event.timestamp,
            event_type=event.event_type,
            severity=event.severity,
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            session_id=event.session_id,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            action=event.action,
            details=details,
            sensitive_data=event.sensitive_data,
            compliance_relevant=event.compliance_relevant,
            hash_digest=hash_digest
        )
        
        self.db_session.add(audit_record)
        await self.db_session.commit()
    
    async def query_audit_logs(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Query audit logs with filters."""
        if not self.db_session:
            return []
        
        query = self.db_session.query(AuditLog).filter(
            AuditLog.tenant_id == tenant_id
        )
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        if event_types:
            query = query.filter(AuditLog.event_type.in_([et.value for et in event_types]))
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        
        records = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
        
        # Convert to AuditEvent objects
        events = []
        for record in records:
            details = record.details or {}
            
            # Decrypt sensitive details if needed
            if (record.sensitive_data and 
                isinstance(details, dict) and 
                details.get("encrypted") and 
                self.encryption_manager):
                try:
                    decrypted_data = self.encryption_manager.decrypt_data(
                        tenant_id, 
                        details["data"]
                    )
                    details = json.loads(decrypted_data)
                except Exception as e:
                    logger.warning("Failed to decrypt audit details", error=str(e))
                    details = {"error": "Failed to decrypt"}
            
            event = AuditEvent(
                id=str(record.id),
                timestamp=record.timestamp,
                event_type=AuditEventType(record.event_type),
                severity=AuditSeverity(record.severity),
                tenant_id=record.tenant_id,
                user_id=record.user_id,
                session_id=record.session_id,
                ip_address=record.ip_address,
                user_agent=record.user_agent,
                resource_type=record.resource_type,
                resource_id=record.resource_id,
                action=record.action,
                details=details,
                sensitive_data=record.sensitive_data,
                compliance_relevant=record.compliance_relevant
            )
            events.append(event)
        
        return events


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    
    return _audit_logger


async def audit(
    event_type: AuditEventType,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    severity: AuditSeverity = AuditSeverity.LOW,
    details: Optional[Dict[str, Any]] = None,
    sensitive_data: bool = False,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None
) -> str:
    """Convenience function to log audit events."""
    event = AuditEvent(
        event_type=event_type,
        severity=severity,
        tenant_id=tenant_id,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        details=details or {},
        sensitive_data=sensitive_data,
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id
    )
    
    audit_logger = get_audit_logger()
    return await audit_logger.log_event(event)


import hashlib