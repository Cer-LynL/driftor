"""
Jira webhook processing with enterprise security and event handling.
"""
import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field
import structlog

from driftor.security.audit import audit, AuditEventType, AuditSeverity
from driftor.agents.graph import get_workflow

logger = structlog.get_logger(__name__)


class JiraWebhookEvent(str, Enum):
    """Jira webhook event types."""
    ISSUE_CREATED = "jira:issue_created"
    ISSUE_UPDATED = "jira:issue_updated"
    ISSUE_DELETED = "jira:issue_deleted"
    COMMENT_CREATED = "comment_created"
    COMMENT_UPDATED = "comment_updated"
    COMMENT_DELETED = "comment_deleted"
    WORKLOG_CREATED = "worklog_created"
    WORKLOG_UPDATED = "worklog_updated"
    WORKLOG_DELETED = "worklog_deleted"


class JiraChangelogItem(BaseModel):
    """Jira changelog item."""
    field: str
    fieldtype: str
    from_value: Optional[str] = Field(alias="from")
    from_string: Optional[str] = Field(alias="fromString")
    to_value: Optional[str] = Field(alias="to")
    to_string: Optional[str] = Field(alias="toString")


class JiraWebhookPayload(BaseModel):
    """Jira webhook payload structure."""
    timestamp: int
    webhook_event: str = Field(alias="webhookEvent")
    user: Optional[Dict[str, Any]] = None
    issue: Optional[Dict[str, Any]] = None
    comment: Optional[Dict[str, Any]] = None
    worklog: Optional[Dict[str, Any]] = None
    changelog: Optional[Dict[str, Any]] = None
    
    class Config:
        allow_population_by_field_name = True


class JiraWebhookProcessor:
    """Process Jira webhooks with security and enterprise features."""
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.workflow = get_workflow()
    
    async def process_webhook(
        self,
        request: Request,
        payload: bytes,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Process incoming Jira webhook with security validation."""
        try:
            # Verify webhook signature
            signature = request.headers.get("X-Hub-Signature-256", "")
            if not await self._verify_webhook_signature(payload, signature, tenant_id):
                await audit(
                    event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
                    tenant_id=tenant_id,
                    severity=AuditSeverity.HIGH,
                    details={
                        "reason": "invalid_jira_webhook_signature",
                        "source_ip": request.client.host if request.client else None,
                        "user_agent": request.headers.get("user-agent")
                    },
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent")
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature"
                )
            
            # Parse webhook payload
            try:
                payload_data = json.loads(payload.decode('utf-8'))
                webhook_payload = JiraWebhookPayload(**payload_data)
            except Exception as e:
                logger.error("Failed to parse Jira webhook payload", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid webhook payload"
                )
            
            # Audit webhook receipt
            await audit(
                event_type=AuditEventType.WEBHOOK_RECEIVED,
                tenant_id=tenant_id,
                resource_type="jira_webhook",
                action=webhook_payload.webhook_event,
                details={
                    "issue_key": webhook_payload.issue.get("key") if webhook_payload.issue else None,
                    "user": webhook_payload.user.get("displayName") if webhook_payload.user else None,
                    "timestamp": webhook_payload.timestamp
                },
                ip_address=request.client.host if request.client else None
            )
            
            # Process based on event type
            result = await self._route_webhook_event(webhook_payload, tenant_id)
            
            return {
                "status": "processed",
                "event_type": webhook_payload.webhook_event,
                "result": result
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Webhook processing failed",
                tenant_id=tenant_id,
                error=str(e),
                exc_info=True
            )
            
            await audit(
                event_type=AuditEventType.WEBHOOK_RECEIVED,
                tenant_id=tenant_id,
                severity=AuditSeverity.HIGH,
                details={
                    "error": str(e),
                    "status": "failed"
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook processing failed"
            )
    
    async def _verify_webhook_signature(
        self, 
        payload: bytes, 
        signature: str, 
        tenant_id: str
    ) -> bool:
        """Verify webhook signature for security."""
        try:
            # TODO: Get webhook secret from tenant configuration
            # For now, assume it's available - this will be implemented
            # when we add the integration configuration models
            webhook_secret = "temporary_webhook_secret"  # TODO: Get from DB
            
            if not webhook_secret:
                logger.warning("No webhook secret configured", tenant_id=tenant_id)
                return False
            
            # Compute expected signature
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Handle different signature formats
            if signature.startswith("sha256="):
                signature = signature[7:]
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error("Webhook signature verification failed", error=str(e))
            return False
    
    async def _route_webhook_event(
        self, 
        payload: JiraWebhookPayload, 
        tenant_id: str
    ) -> Dict[str, Any]:
        """Route webhook event to appropriate handler."""
        event_type = JiraWebhookEvent(payload.webhook_event)
        
        if event_type == JiraWebhookEvent.ISSUE_CREATED:
            return await self._handle_issue_created(payload, tenant_id)
        elif event_type == JiraWebhookEvent.ISSUE_UPDATED:
            return await self._handle_issue_updated(payload, tenant_id)
        elif event_type == JiraWebhookEvent.ISSUE_DELETED:
            return await self._handle_issue_deleted(payload, tenant_id)
        elif event_type == JiraWebhookEvent.COMMENT_CREATED:
            return await self._handle_comment_created(payload, tenant_id)
        elif event_type in [
            JiraWebhookEvent.COMMENT_UPDATED,
            JiraWebhookEvent.COMMENT_DELETED,
            JiraWebhookEvent.WORKLOG_CREATED,
            JiraWebhookEvent.WORKLOG_UPDATED,
            JiraWebhookEvent.WORKLOG_DELETED
        ]:
            # These events are logged but not processed
            return {"action": "logged", "message": "Event logged for audit"}
        else:
            logger.warning("Unknown webhook event type", event_type=event_type)
            return {"action": "ignored", "message": "Unknown event type"}
    
    async def _handle_issue_created(
        self, 
        payload: JiraWebhookPayload, 
        tenant_id: str
    ) -> Dict[str, Any]:
        """Handle issue created event."""
        if not payload.issue:
            return {"action": "skipped", "message": "No issue data"}
        
        issue_data = payload.issue
        issue_key = issue_data.get("key", "")
        
        logger.info(
            "Processing new Jira issue",
            issue_key=issue_key,
            tenant_id=tenant_id
        )
        
        # Check if this is a bug that should be analyzed
        if await self._should_analyze_issue(issue_data):
            # Queue for analysis
            return await self._queue_issue_analysis(issue_data, tenant_id)
        
        return {"action": "skipped", "message": "Issue not eligible for analysis"}
    
    async def _handle_issue_updated(
        self, 
        payload: JiraWebhookPayload, 
        tenant_id: str
    ) -> Dict[str, Any]:
        """Handle issue updated event."""
        if not payload.issue or not payload.changelog:
            return {"action": "skipped", "message": "No issue or changelog data"}
        
        issue_data = payload.issue
        changelog = payload.changelog
        issue_key = issue_data.get("key", "")
        
        # Check what changed
        changes = self._analyze_changelog(changelog)
        
        logger.info(
            "Processing Jira issue update",
            issue_key=issue_key,
            changes=list(changes.keys()),
            tenant_id=tenant_id
        )
        
        # Handle assignment changes
        if "assignee" in changes:
            assignee_change = changes["assignee"]
            new_assignee = assignee_change.get("to_user")
            
            if new_assignee and await self._should_analyze_issue(issue_data):
                # Queue for analysis with new assignee
                return await self._queue_issue_analysis(
                    issue_data, 
                    tenant_id, 
                    assignee_id=new_assignee.get("accountId") or new_assignee.get("name")
                )
        
        # Handle status changes
        if "status" in changes:
            status_change = changes["status"]
            new_status = status_change.get("to_string", "")
            
            # If issue was reopened, might need re-analysis
            if new_status.lower() in ["open", "reopened", "to do"]:
                if await self._should_analyze_issue(issue_data):
                    return await self._queue_issue_analysis(issue_data, tenant_id)
        
        return {"action": "logged", "message": "Issue update processed"}
    
    async def _handle_issue_deleted(
        self, 
        payload: JiraWebhookPayload, 
        tenant_id: str
    ) -> Dict[str, Any]:
        """Handle issue deleted event."""
        if not payload.issue:
            return {"action": "skipped", "message": "No issue data"}
        
        issue_key = payload.issue.get("key", "")
        
        logger.info(
            "Jira issue deleted",
            issue_key=issue_key,
            tenant_id=tenant_id
        )
        
        # TODO: Clean up any related analysis data or notifications
        
        return {"action": "logged", "message": "Issue deletion processed"}
    
    async def _handle_comment_created(
        self, 
        payload: JiraWebhookPayload, 
        tenant_id: str
    ) -> Dict[str, Any]:
        """Handle comment created event."""
        if not payload.comment or not payload.issue:
            return {"action": "skipped", "message": "No comment or issue data"}
        
        comment = payload.comment
        issue_data = payload.issue
        issue_key = issue_data.get("key", "")
        comment_body = comment.get("body", "")
        
        logger.info(
            "Processing new Jira comment",
            issue_key=issue_key,
            comment_id=comment.get("id"),
            tenant_id=tenant_id
        )
        
        # Check if comment mentions Driftor or requests analysis
        if self._is_driftor_mention(comment_body):
            # Handle Driftor-specific commands or mentions
            return await self._handle_driftor_mention(comment, issue_data, tenant_id)
        
        return {"action": "logged", "message": "Comment logged"}
    
    async def _should_analyze_issue(self, issue_data: Dict[str, Any]) -> bool:
        """Determine if an issue should be analyzed."""
        fields = issue_data.get("fields", {})
        
        # Check issue type
        issue_type = fields.get("issuetype", {}).get("name", "").lower()
        if "bug" not in issue_type and "defect" not in issue_type:
            return False
        
        # Check if issue has assignee
        assignee = fields.get("assignee")
        if not assignee:
            return False
        
        # Check status - only analyze open/active issues
        status = fields.get("status", {}).get("name", "").lower()
        active_statuses = ["open", "to do", "in progress", "assigned", "new"]
        if not any(active_status in status for active_status in active_statuses):
            return False
        
        # Check priority - skip low priority issues for now
        priority = fields.get("priority", {}).get("name", "").lower()
        if priority in ["lowest", "trivial"]:
            return False
        
        return True
    
    async def _queue_issue_analysis(
        self, 
        issue_data: Dict[str, Any], 
        tenant_id: str,
        assignee_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Queue issue for AI analysis."""
        try:
            fields = issue_data.get("fields", {})
            
            # Get assignee
            if not assignee_id:
                assignee = fields.get("assignee", {})
                assignee_id = assignee.get("accountId") or assignee.get("name")
            
            if not assignee_id:
                return {"action": "skipped", "message": "No assignee found"}
            
            # Prepare ticket data for analysis
            ticket_data = {
                "id": issue_data.get("id"),
                "key": issue_data.get("key"),
                "summary": fields.get("summary", ""),
                "description": fields.get("description", ""),
                "issue_type": fields.get("issuetype", {}).get("name", ""),
                "priority": fields.get("priority", {}).get("name", ""),
                "status": fields.get("status", {}).get("name", ""),
                "project": {
                    "key": fields.get("project", {}).get("key", ""),
                    "name": fields.get("project", {}).get("name", "")
                },
                "assignee": fields.get("assignee", {}),
                "reporter": fields.get("reporter", {}),
                "created": fields.get("created"),
                "updated": fields.get("updated"),
                "url": f"{issue_data.get('self', '').replace('/rest/api/2/issue/', '/browse/')}"
            }
            
            # Queue for analysis workflow
            analysis_input = {
                "tenant_id": tenant_id,
                "ticket_id": issue_data.get("key", ""),
                "ticket_data": ticket_data,
                "assignee_id": assignee_id
            }
            
            # Start analysis workflow asynchronously
            asyncio.create_task(self._run_analysis_workflow(analysis_input))
            
            logger.info(
                "Issue queued for analysis",
                issue_key=issue_data.get("key"),
                assignee=assignee_id,
                tenant_id=tenant_id
            )
            
            return {
                "action": "queued",
                "message": "Issue queued for AI analysis",
                "issue_key": issue_data.get("key")
            }
            
        except Exception as e:
            logger.error(
                "Failed to queue issue analysis",
                issue_key=issue_data.get("key", "unknown"),
                error=str(e),
                exc_info=True
            )
            return {"action": "error", "message": str(e)}
    
    async def _run_analysis_workflow(self, analysis_input: Dict[str, Any]) -> None:
        """Run the analysis workflow asynchronously."""
        try:
            # Set database session for workflow
            if self.db_session:
                workflow = get_workflow()
                workflow.db_session = self.db_session
            
            # Run analysis
            result = await workflow.run_analysis(analysis_input)
            
            logger.info(
                "Analysis workflow completed",
                ticket_id=analysis_input["ticket_id"],
                status=result.get("workflow_status"),
                confidence=result.get("confidence_score"),
                tenant_id=analysis_input["tenant_id"]
            )
            
        except Exception as e:
            logger.error(
                "Analysis workflow failed",
                ticket_id=analysis_input.get("ticket_id", "unknown"),
                error=str(e),
                exc_info=True
            )
    
    def _analyze_changelog(self, changelog: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze changelog to extract meaningful changes."""
        changes = {}
        
        for item in changelog.get("items", []):
            field = item.get("field", "")
            from_value = item.get("fromString")
            to_value = item.get("toString")
            
            if field == "assignee":
                changes["assignee"] = {
                    "from_user": self._parse_user_string(from_value) if from_value else None,
                    "to_user": self._parse_user_string(to_value) if to_value else None
                }
            elif field == "status":
                changes["status"] = {
                    "from_string": from_value,
                    "to_string": to_value
                }
            elif field == "priority":
                changes["priority"] = {
                    "from_string": from_value,
                    "to_string": to_value
                }
            # Add more fields as needed
        
        return changes
    
    def _parse_user_string(self, user_string: str) -> Optional[Dict[str, str]]:
        """Parse user string from changelog."""
        if not user_string:
            return None
        
        # Simple parsing - in production, might need more sophisticated logic
        return {
            "name": user_string,
            "displayName": user_string
        }
    
    def _is_driftor_mention(self, comment_body: str) -> bool:
        """Check if comment mentions Driftor."""
        driftor_keywords = [
            "@driftor", "driftor", "analyze", "fix suggestion", "help"
        ]
        
        comment_lower = comment_body.lower()
        return any(keyword in comment_lower for keyword in driftor_keywords)
    
    async def _handle_driftor_mention(
        self, 
        comment: Dict[str, Any], 
        issue_data: Dict[str, Any], 
        tenant_id: str
    ) -> Dict[str, Any]:
        """Handle mentions of Driftor in comments."""
        comment_body = comment.get("body", "").lower()
        issue_key = issue_data.get("key", "")
        
        # Parse command
        if "analyze" in comment_body or "help" in comment_body:
            # Re-trigger analysis
            return await self._queue_issue_analysis(issue_data, tenant_id)
        elif "status" in comment_body:
            # TODO: Provide status update on analysis
            return {"action": "status_requested", "message": "Status update requested"}
        else:
            # General mention - acknowledge
            return {"action": "mentioned", "message": "Driftor mentioned in comment"}


# Global webhook processor
_webhook_processor: Optional[JiraWebhookProcessor] = None


def get_webhook_processor(db_session=None) -> JiraWebhookProcessor:
    """Get global webhook processor instance."""
    global _webhook_processor
    
    if _webhook_processor is None:
        _webhook_processor = JiraWebhookProcessor(db_session)
    elif db_session and not _webhook_processor.db_session:
        _webhook_processor.db_session = db_session
    
    return _webhook_processor