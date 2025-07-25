"""
Jira webhook event processing and validation.
"""
import hashlib
import hmac
from typing import Dict, Any, Optional
import logging

from app.models.ticket import TicketStatus, TicketPriority
from app.schemas.ticket import TicketCreate

logger = logging.getLogger(__name__)


class JiraWebhookProcessor:
    """Process and validate Jira webhook events."""
    
    def __init__(self, webhook_secret: Optional[str] = None):
        self.webhook_secret = webhook_secret
    
    def validate_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Validate webhook signature if secret is configured."""
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping signature validation")
            return True
        
        try:
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Jira sends signature as "sha256=<hash>"
            if signature.startswith('sha256='):
                signature = signature[7:]
            
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Error validating webhook signature: {e}")
            return False
    
    def is_ticket_assignment_event(self, webhook_data: Dict[str, Any]) -> bool:
        """Check if the webhook event is a ticket assignment."""
        try:    
            webhook_event = webhook_data.get('webhookEvent', '')
            
            # Check for issue_updated event with assignee change
            if webhook_event == 'jira:issue_updated':
                changelog = webhook_data.get('changelog', {})
                items = changelog.get('items', [])
                
                # Look for assignee field changes
                for item in items:
                    if item.get('field') == 'assignee' and item.get('to'):
                        return True
            
            # Check for issue_created event with assignee
            elif webhook_event == 'jira:issue_created':
                issue = webhook_data.get('issue', {})
                assignee = issue.get('fields', {}).get('assignee')
                return assignee is not None
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking ticket assignment event: {e}")
            return False
    
    def is_bug_ticket(self, webhook_data: Dict[str, Any]) -> bool:
        """Check if the ticket is a bug type."""
        try:
            issue = webhook_data.get('issue', {})
            issue_type = issue.get('fields', {}).get('issuetype', {})
            issue_type_name = issue_type.get('name', '').lower()
            
            # Common bug type names
            bug_types = ['bug', 'defect', 'incident', 'problem', 'error', 'issue']
            
            return any(bug_type in issue_type_name for bug_type in bug_types)
            
        except Exception as e:
            logger.error(f"Error checking bug ticket type: {e}")
            return False
    
    def extract_ticket_data(self, webhook_data: Dict[str, Any]) -> Optional[TicketCreate]:
        """Extract ticket information from webhook payload."""
        try:
            issue = webhook_data.get('issue', {})
            fields = issue.get('fields', {})
            
            # Basic ticket information
            jira_id = issue.get('id')
            jira_key = issue.get('key')
            
            if not jira_id or not jira_key:
                logger.error("Missing required ticket ID or key")
                return None
            
            # Extract project information
            project = fields.get('project', {})
            project_key = project.get('key')
            
            if not project_key:
                logger.error("Missing project key")
                return None
            
            # Extract ticket details
            title = fields.get('summary', '')
            description = fields.get('description', {})
            
            # Handle description based on format (ADF or plain text)
            if isinstance(description, dict):
                description_text = self._extract_text_from_adf(description)
            else:
                description_text = str(description) if description else ''
            
            # Extract issue type
            issue_type = fields.get('issuetype', {})
            ticket_type = issue_type.get('name', 'Unknown')
            
            # Extract status
            status = fields.get('status', {})
            status_name = status.get('name', '').lower()
            ticket_status = self._map_jira_status(status_name)
            
            # Extract priority
            priority = fields.get('priority')
            ticket_priority = None
            if priority:
                priority_name = priority.get('name', '').lower()
                ticket_priority = self._map_jira_priority(priority_name)
            
            # Extract assignee information
            assignee = fields.get('assignee')
            assignee_email = None
            assignee_name = None
            if assignee:
                assignee_email = assignee.get('emailAddress')
                assignee_name = assignee.get('displayName')
            
            # Extract reporter information
            reporter = fields.get('reporter')
            reporter_email = None
            reporter_name = None
            if reporter:
                reporter_email = reporter.get('emailAddress')
                reporter_name = reporter.get('displayName')
            
            return TicketCreate(
                jira_id=jira_id,
                jira_key=jira_key,
                project_key=project_key,
                title=title,
                description=description_text,
                ticket_type=ticket_type,
                status=ticket_status,
                priority=ticket_priority,
                assignee_email=assignee_email,
                assignee_name=assignee_name,
                reporter_email=reporter_email,
                reporter_name=reporter_name,
                raw_data=webhook_data
            )
            
        except Exception as e:
            logger.error(f"Error extracting ticket data: {e}")
            return None
    
    def _extract_text_from_adf(self, adf_content: Dict[str, Any]) -> str:
        """Extract plain text from Atlassian Document Format (ADF)."""
        try:
            def extract_text_recursive(node):
                text = ""
                if isinstance(node, dict):
                    if node.get('type') == 'text':
                        text += node.get('text', '')
                    elif 'content' in node:
                        for child in node['content']:
                            text += extract_text_recursive(child)
                elif isinstance(node, list):
                    for item in node:
                        text += extract_text_recursive(item)
                return text
            
            return extract_text_recursive(adf_content).strip()
        except Exception as e:
            logger.error(f"Error extracting text from ADF: {e}")
            return ""
    
    def _map_jira_status(self, status_name: str) -> TicketStatus:
        """Map Jira status to internal status enum."""
        status_mapping = {
            'open': TicketStatus.OPEN,
            'to do': TicketStatus.OPEN,
            'backlog': TicketStatus.OPEN,
            'in progress': TicketStatus.IN_PROGRESS,
            'in development': TicketStatus.IN_PROGRESS,
            'in review': TicketStatus.IN_PROGRESS,
            'testing': TicketStatus.IN_PROGRESS,
            'resolved': TicketStatus.RESOLVED,
            'done': TicketStatus.RESOLVED,
            'fixed': TicketStatus.RESOLVED,
            'closed': TicketStatus.CLOSED,
            'cancelled': TicketStatus.CLOSED,
            'reopened': TicketStatus.REOPENED,
        }
        
        return status_mapping.get(status_name.lower(), TicketStatus.OPEN)
    
    def _map_jira_priority(self, priority_name: str) -> TicketPriority:
        """Map Jira priority to internal priority enum."""
        priority_mapping = {
            'lowest': TicketPriority.LOWEST,
            'low': TicketPriority.LOW,
            'medium': TicketPriority.MEDIUM,
            'normal': TicketPriority.MEDIUM,
            'high': TicketPriority.HIGH,
            'highest': TicketPriority.HIGHEST,
            'critical': TicketPriority.HIGHEST,
            'blocker': TicketPriority.HIGHEST,
        }
        
        return priority_mapping.get(priority_name.lower(), TicketPriority.MEDIUM)