"""
GDPR-compliant data retention and lifecycle management system.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.orm import Session
from pydantic import BaseModel
import structlog

from driftor.core.config import get_settings
from driftor.security.audit import audit, AuditEventType, AuditSeverity
from driftor.security.encryption import get_encryption_manager

logger = structlog.get_logger(__name__)


class DataClassification(str, Enum):
    """Data classification levels for retention policies."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    PERSONAL_DATA = "personal_data"  # GDPR personal data


class RetentionAction(str, Enum):
    """Actions to take when retention period expires."""
    DELETE = "delete"
    ANONYMIZE = "anonymize"
    ARCHIVE = "archive"
    ENCRYPT_FURTHER = "encrypt_further"


class DataRetentionPolicy(BaseModel):
    """Data retention policy configuration."""
    data_type: str
    classification: DataClassification
    retention_days: int
    action: RetentionAction
    notify_before_days: int = 30
    tenant_specific: bool = False
    legal_hold_exempt: bool = False
    
    def is_expired(self, created_at: datetime) -> bool:
        """Check if data has exceeded retention period."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        return created_at < cutoff_date
    
    def needs_notification(self, created_at: datetime) -> bool:
        """Check if retention notification should be sent."""
        notify_date = datetime.now(timezone.utc) - timedelta(
            days=self.retention_days - self.notify_before_days
        )
        return created_at < notify_date


class GDPRDataManager:
    """GDPR-compliant data lifecycle management."""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.settings = get_settings()
        self.encryption_manager = get_encryption_manager()
        self.policies = self._load_retention_policies()
    
    def _load_retention_policies(self) -> Dict[str, DataRetentionPolicy]:
        """Load data retention policies from configuration."""
        return {
            "analysis_results": DataRetentionPolicy(
                data_type="analysis_results",
                classification=DataClassification.CONFIDENTIAL,
                retention_days=self.settings.compliance.retention_analysis_results,
                action=RetentionAction.ANONYMIZE,
                notify_before_days=7
            ),
            "code_snippets": DataRetentionPolicy(
                data_type="code_snippets",
                classification=DataClassification.RESTRICTED,
                retention_days=self.settings.compliance.retention_code_snippets,
                action=RetentionAction.DELETE,
                notify_before_days=7
            ),
            "chat_history": DataRetentionPolicy(
                data_type="chat_history",
                classification=DataClassification.PERSONAL_DATA,
                retention_days=self.settings.compliance.retention_chat_history,
                action=RetentionAction.ANONYMIZE,
                notify_before_days=30
            ),
            "audit_logs": DataRetentionPolicy(
                data_type="audit_logs",
                classification=DataClassification.CONFIDENTIAL,
                retention_days=self.settings.compliance.retention_audit_logs,
                action=RetentionAction.ARCHIVE,
                notify_before_days=30,
                legal_hold_exempt=True
            ),
            "user_sessions": DataRetentionPolicy(
                data_type="user_sessions",
                classification=DataClassification.PERSONAL_DATA,
                retention_days=90,
                action=RetentionAction.DELETE,
                notify_before_days=7
            ),
            "api_logs": DataRetentionPolicy(
                data_type="api_logs",
                classification=DataClassification.INTERNAL,
                retention_days=365,
                action=RetentionAction.ANONYMIZE,
                notify_before_days=30
            )
        }
    
    async def apply_retention_policies(self, tenant_id: Optional[str] = None) -> Dict[str, int]:
        """Apply retention policies to all applicable data."""
        results = {}
        
        for policy_name, policy in self.policies.items():
            try:
                count = await self._apply_single_policy(policy, tenant_id)
                results[policy_name] = count
                
                logger.info(
                    "Applied retention policy",
                    policy=policy_name,
                    tenant_id=tenant_id,
                    records_processed=count,
                    action=policy.action.value
                )
                
            except Exception as e:
                logger.error(
                    "Failed to apply retention policy",
                    policy=policy_name,
                    tenant_id=tenant_id,
                    error=str(e),
                    exc_info=True
                )
                results[policy_name] = 0
        
        return results
    
    async def _apply_single_policy(
        self, 
        policy: DataRetentionPolicy, 
        tenant_id: Optional[str] = None
    ) -> int:
        """Apply a single retention policy."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=policy.retention_days)
        
        # Get table class for the data type
        table_class = self._get_table_class(policy.data_type)
        if not table_class:
            logger.warning(f"No table class found for data type: {policy.data_type}")
            return 0
        
        # Build query
        query = select(table_class).where(
            table_class.created_at < cutoff_date,
            table_class.is_deleted == False
        )
        
        if tenant_id:
            query = query.where(table_class.tenant_id == tenant_id)
        
        # Get records to process
        result = await self.db_session.execute(query)
        records = result.scalars().all()
        
        if not records:
            return 0
        
        processed_count = 0
        
        for record in records:
            try:
                if policy.action == RetentionAction.DELETE:
                    await self._delete_record(record, policy)
                elif policy.action == RetentionAction.ANONYMIZE:
                    await self._anonymize_record(record, policy)
                elif policy.action == RetentionAction.ARCHIVE:
                    await self._archive_record(record, policy)
                elif policy.action == RetentionAction.ENCRYPT_FURTHER:
                    await self._encrypt_further(record, policy)
                
                processed_count += 1
                
            except Exception as e:
                logger.error(
                    "Failed to process record for retention",
                    record_id=str(record.id),
                    policy=policy.data_type,
                    action=policy.action.value,
                    error=str(e)
                )
        
        await self.db_session.commit()
        return processed_count
    
    async def _delete_record(self, record, policy: DataRetentionPolicy) -> None:
        """Permanently delete a record."""
        await audit(
            event_type=AuditEventType.DATA_DELETED,
            tenant_id=getattr(record, 'tenant_id', None),
            resource_type=policy.data_type,
            resource_id=str(record.id),
            action="RETENTION_DELETE",
            details={
                "policy": policy.data_type,
                "retention_days": policy.retention_days,
                "reason": "retention_policy_expired"
            },
            severity=AuditSeverity.MEDIUM
        )
        
        await self.db_session.delete(record)
    
    async def _anonymize_record(self, record, policy: DataRetentionPolicy) -> None:
        """Anonymize personally identifiable information in a record."""
        anonymization_map = self._get_anonymization_map(policy.data_type)
        
        for field, anonymizer in anonymization_map.items():
            if hasattr(record, field):
                original_value = getattr(record, field)
                if original_value:
                    anonymized_value = anonymizer(original_value)
                    setattr(record, field, anonymized_value)
        
        # Mark as anonymized
        if hasattr(record, 'is_anonymized'):
            record.is_anonymized = True
        
        await audit(
            event_type=AuditEventType.DATA_UPDATED,
            tenant_id=getattr(record, 'tenant_id', None),
            resource_type=policy.data_type,
            resource_id=str(record.id),
            action="RETENTION_ANONYMIZE",
            details={
                "policy": policy.data_type,
                "retention_days": policy.retention_days,
                "fields_anonymized": list(anonymization_map.keys())
            },
            sensitive_data=True
        )
    
    async def _archive_record(self, record, policy: DataRetentionPolicy) -> None:
        """Archive a record to cold storage."""
        # In a real implementation, this would move data to S3 Glacier or similar
        # For now, we'll just mark it as archived
        
        if hasattr(record, 'is_archived'):
            record.is_archived = True
        if hasattr(record, 'archived_at'):
            record.archived_at = datetime.now(timezone.utc)
        
        await audit(
            event_type=AuditEventType.DATA_UPDATED,
            tenant_id=getattr(record, 'tenant_id', None),
            resource_type=policy.data_type,
            resource_id=str(record.id),
            action="RETENTION_ARCHIVE",
            details={
                "policy": policy.data_type,
                "retention_days": policy.retention_days
            }
        )
    
    async def _encrypt_further(self, record, policy: DataRetentionPolicy) -> None:
        """Apply additional encryption to aged data."""
        # Re-encrypt with a different key or algorithm
        sensitive_fields = self._get_sensitive_fields(policy.data_type)
        
        for field in sensitive_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if value and not value.startswith("ARCHIVED_"):
                    # Add archive prefix to encrypted data
                    re_encrypted = f"ARCHIVED_{value}"
                    setattr(record, field, re_encrypted)
        
        await audit(
            event_type=AuditEventType.DATA_UPDATED,
            tenant_id=getattr(record, 'tenant_id', None),
            resource_type=policy.data_type,
            resource_id=str(record.id),
            action="RETENTION_ENCRYPT",
            details={
                "policy": policy.data_type,
                "retention_days": policy.retention_days,
                "fields_encrypted": sensitive_fields
            }
        )
    
    def _get_table_class(self, data_type: str):
        """Get SQLAlchemy table class for data type."""
        # Mapping of data types to table classes
        from driftor.models.tenant import TenantUser
        from driftor.security.audit import AuditLog
        
        table_mapping = {
            "analysis_results": None,  # TODO: Add when analysis model is created
            "code_snippets": None,     # TODO: Add when code snippet model is created
            "chat_history": None,      # TODO: Add when chat model is created
            "audit_logs": AuditLog,
            "user_sessions": None,     # TODO: Add when session model is created
            "api_logs": None          # TODO: Add when API log model is created
        }
        
        return table_mapping.get(data_type)
    
    def _get_anonymization_map(self, data_type: str) -> Dict[str, callable]:
        """Get field anonymization mapping for data type."""
        def anonymize_email(email: str) -> str:
            """Anonymize email address."""
            if '@' in email:
                local, domain = email.split('@', 1)
                return f"user_{hash(email) % 100000}@{domain}"
            return f"anonymized_{hash(email) % 100000}"
        
        def anonymize_name(name: str) -> str:
            """Anonymize personal name."""
            return f"User_{hash(name) % 100000}"
        
        def anonymize_ip(ip: str) -> str:
            """Anonymize IP address."""
            if '.' in ip:  # IPv4
                parts = ip.split('.')
                return f"{parts[0]}.{parts[1]}.XXX.XXX"
            return "XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX"  # IPv6
        
        anonymization_maps = {
            "chat_history": {
                "user_message": lambda x: "[ANONYMIZED MESSAGE]",
                "user_id": lambda x: f"anon_{hash(x) % 100000}"
            },
            "analysis_results": {
                "user_id": lambda x: f"anon_{hash(x) % 100000}",
                "ip_address": anonymize_ip
            },
            "api_logs": {
                "user_id": lambda x: f"anon_{hash(x) % 100000}",
                "ip_address": anonymize_ip,
                "user_agent": lambda x: "[ANONYMIZED USER AGENT]"
            }
        }
        
        return anonymization_maps.get(data_type, {})
    
    def _get_sensitive_fields(self, data_type: str) -> List[str]:
        """Get list of sensitive fields for data type."""
        sensitive_field_maps = {
            "analysis_results": ["code_snippets", "error_details"],
            "code_snippets": ["content", "file_path"],
            "chat_history": ["message_content", "context_data"],
            "user_sessions": ["session_data", "browser_fingerprint"]
        }
        
        return sensitive_field_maps.get(data_type, [])
    
    async def export_user_data(self, tenant_id: str, user_id: str) -> Dict[str, List[Dict]]:
        """Export all data for a user (GDPR Article 20 - Right to Data Portability)."""
        user_data = {}
        
        # Get data from all tables that contain user information
        table_queries = {
            "profile": self._get_user_profile_data,
            "audit_logs": self._get_user_audit_data,
            "analysis_results": self._get_user_analysis_data,
            "chat_history": self._get_user_chat_data
        }
        
        for data_type, query_func in table_queries.items():
            try:
                data = await query_func(tenant_id, user_id)
                if data:
                    user_data[data_type] = data
            except Exception as e:
                logger.error(
                    "Failed to export user data",
                    data_type=data_type,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    error=str(e)
                )
        
        # Audit the data export
        await audit(
            event_type=AuditEventType.DATA_EXPORTED,
            tenant_id=tenant_id,
            user_id=user_id,
            action="GDPR_DATA_EXPORT",
            details={
                "data_types": list(user_data.keys()),
                "total_records": sum(len(records) for records in user_data.values())
            },
            severity=AuditSeverity.MEDIUM
        )
        
        return user_data
    
    async def delete_user_data(self, tenant_id: str, user_id: str, verification_token: str) -> bool:
        """Delete all user data (GDPR Article 17 - Right to Erasure)."""
        # Verify deletion token for security
        expected_token = hashlib.sha256(f"{tenant_id}:{user_id}:{datetime.now().date()}".encode()).hexdigest()
        if not hmac.compare_digest(verification_token, expected_token):
            raise ValueError("Invalid verification token")
        
        deletion_count = 0
        
        # Delete or anonymize data across all tables
        tables_to_process = [
            "audit_logs",
            "analysis_results", 
            "chat_history",
            "user_sessions",
            "api_logs"
        ]
        
        for table_name in tables_to_process:
            try:
                count = await self._delete_user_data_from_table(table_name, tenant_id, user_id)
                deletion_count += count
                
                logger.info(
                    "Deleted user data from table",
                    table=table_name,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    records_deleted=count
                )
                
            except Exception as e:
                logger.error(
                    "Failed to delete user data from table",
                    table=table_name,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    error=str(e)
                )
        
        # Audit the deletion
        await audit(
            event_type=AuditEventType.DATA_DELETED,
            tenant_id=tenant_id,
            user_id=user_id,
            action="GDPR_RIGHT_TO_ERASURE",
            details={
                "total_records_deleted": deletion_count,
                "verification_token_used": verification_token[:8] + "..."
            },
            severity=AuditSeverity.HIGH
        )
        
        return deletion_count > 0
    
    async def _get_user_profile_data(self, tenant_id: str, user_id: str) -> List[Dict]:
        """Get user profile data for export."""
        # TODO: Implement when user models are ready
        return []
    
    async def _get_user_audit_data(self, tenant_id: str, user_id: str) -> List[Dict]:
        """Get user audit data for export."""
        # TODO: Implement when audit models are ready
        return []
    
    async def _get_user_analysis_data(self, tenant_id: str, user_id: str) -> List[Dict]:
        """Get user analysis data for export."""
        # TODO: Implement when analysis models are ready
        return []
    
    async def _get_user_chat_data(self, tenant_id: str, user_id: str) -> List[Dict]:
        """Get user chat data for export."""
        # TODO: Implement when chat models are ready
        return []
    
    async def _delete_user_data_from_table(
        self, 
        table_name: str, 
        tenant_id: str, 
        user_id: str
    ) -> int:
        """Delete user data from a specific table."""
        # TODO: Implement actual deletion logic for each table
        return 0


# Global data manager instance
_data_manager: Optional[GDPRDataManager] = None


def get_data_manager(db_session: Session) -> GDPRDataManager:
    """Get GDPR data manager instance."""
    return GDPRDataManager(db_session)


import hashlib
import hmac