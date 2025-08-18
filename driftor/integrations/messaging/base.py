"""
Base messaging platform integration for Teams and Slack.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import structlog

from driftor.integrations.base import BaseIntegration, IntegrationConfig
from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class MessagePlatform(str, Enum):
    """Supported messaging platforms."""
    TEAMS = "teams"
    SLACK = "slack"


class MessageType(str, Enum):
    """Types of messages."""
    ANALYSIS_NOTIFICATION = "analysis_notification"
    ERROR_NOTIFICATION = "error_notification"
    STATUS_UPDATE = "status_update"
    INTERACTIVE_RESPONSE = "interactive_response"


class ButtonAction(str, Enum):
    """Interactive button actions."""
    ELABORATE_FIX = "elaborate_fix"
    CHAT_WITH_DRIFTOR = "chat_with_driftor"
    MARK_HELPFUL = "mark_helpful"
    MARK_UNHELPFUL = "mark_unhelpful"
    VIEW_SIMILAR_TICKETS = "view_similar_tickets"
    VIEW_DOCUMENTATION = "view_documentation"


@dataclass
class InteractiveButton:
    """Interactive button configuration."""
    id: str
    text: str
    action: ButtonAction
    style: str = "default"  # default, primary, danger
    url: Optional[str] = None
    value: Optional[str] = None


@dataclass
class MessageCard:
    """Platform-agnostic message card."""
    title: str
    subtitle: Optional[str] = None
    text: str
    color: str = "good"  # good, warning, attention, accent
    
    # Content sections
    facts: List[Dict[str, str]] = None
    buttons: List[InteractiveButton] = None
    
    # Rich content
    thumbnail_url: Optional[str] = None
    hero_image_url: Optional[str] = None
    
    # Metadata
    correlation_id: Optional[str] = None
    thread_id: Optional[str] = None


class MessageResponse(BaseModel):
    """Response from messaging platform."""
    success: bool
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    error: Optional[str] = None
    platform: str


class BaseMessagingPlatform(BaseIntegration, ABC):
    """Base class for messaging platform integrations."""
    
    def __init__(self, config: IntegrationConfig, credentials: Dict[str, str]):
        super().__init__(config, credentials)
        self.platform = self._get_platform_type()
    
    @abstractmethod
    def _get_platform_type(self) -> MessagePlatform:
        """Get the platform type."""
        pass
    
    @abstractmethod
    async def send_message(
        self, 
        user_id: str, 
        message: str, 
        thread_id: Optional[str] = None
    ) -> MessageResponse:
        """Send a simple text message."""
        pass
    
    @abstractmethod
    async def send_card(
        self, 
        user_id: str, 
        card: MessageCard,
        thread_id: Optional[str] = None
    ) -> MessageResponse:
        """Send an interactive card message."""
        pass
    
    @abstractmethod
    async def handle_interaction(
        self, 
        interaction_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle interactive button clicks."""
        pass
    
    @abstractmethod
    async def start_conversation(
        self, 
        user_id: str, 
        initial_message: str
    ) -> MessageResponse:
        """Start a new conversation thread."""
        pass
    
    async def send_analysis_notification(
        self,
        user_id: str,
        ticket_data: Dict[str, Any],
        analysis_results: Dict[str, Any],
        tenant_id: str
    ) -> MessageResponse:
        """Send analysis notification with interactive elements."""
        try:
            # Create notification card
            card = self._create_analysis_card(ticket_data, analysis_results)
            
            # Send card
            response = await self.send_card(user_id, card)
            
            # Audit notification
            await audit(
                event_type=AuditEventType.NOTIFICATION_SENT,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="analysis_notification",
                resource_id=ticket_data.get("key"),
                details={
                    "platform": self.platform.value,
                    "confidence_score": analysis_results.get("confidence_score"),
                    "message_id": response.message_id,
                    "success": response.success
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(
                "Failed to send analysis notification",
                user_id=user_id,
                ticket_key=ticket_data.get("key"),
                platform=self.platform.value,
                error=str(e)
            )
            return MessageResponse(
                success=False,
                error=str(e),
                platform=self.platform.value
            )
    
    def _create_analysis_card(
        self, 
        ticket_data: Dict[str, Any], 
        analysis_results: Dict[str, Any]
    ) -> MessageCard:
        """Create analysis notification card."""
        ticket_key = ticket_data.get("key", "")
        ticket_summary = ticket_data.get("summary", "")
        ticket_url = ticket_data.get("url", "")
        confidence_score = analysis_results.get("confidence_score", 0.0)
        
        # Determine card color based on confidence
        if confidence_score >= 0.8:
            color = "good"
        elif confidence_score >= 0.6:
            color = "warning"
        else:
            color = "attention"
        
        # Create title and text
        title = f"🔍 Analysis Complete: {ticket_key}"
        
        text_parts = [
            f"**{ticket_summary}**",
            "",
            f"**Confidence:** {confidence_score:.1%}",
        ]
        
        # Add fix suggestion if available
        suggested_fix = analysis_results.get("suggested_fix")
        if suggested_fix:
            text_parts.extend([
                "",
                "**💡 Suggested Fix:**",
                suggested_fix[:300] + ("..." if len(suggested_fix) > 300 else "")
            ])
        
        # Create facts section
        facts = [
            {"name": "Ticket", "value": ticket_key},
            {"name": "Priority", "value": ticket_data.get("priority", "Unknown")},
            {"name": "Status", "value": ticket_data.get("status", "Unknown")},
            {"name": "Confidence", "value": f"{confidence_score:.1%}"}
        ]
        
        # Add similar tickets info
        similar_tickets = analysis_results.get("similar_tickets", [])
        if similar_tickets:
            facts.append({
                "name": "Similar Issues", 
                "value": f"{len(similar_tickets)} found"
            })
        
        # Add documentation info
        relevant_docs = analysis_results.get("relevant_docs", [])
        if relevant_docs:
            facts.append({
                "name": "Documentation", 
                "value": f"{len(relevant_docs)} relevant docs"
            })
        
        # Create interactive buttons
        buttons = [
            InteractiveButton(
                id="elaborate_fix",
                text="💬 Elaborate on Fix",
                action=ButtonAction.ELABORATE_FIX,
                style="primary",
                value=ticket_key
            )
        ]
        
        if similar_tickets:
            buttons.append(InteractiveButton(
                id="view_similar",
                text="📋 View Similar Issues",
                action=ButtonAction.VIEW_SIMILAR_TICKETS,
                value=ticket_key
            ))
        
        if relevant_docs:
            buttons.append(InteractiveButton(
                id="view_docs",
                text="📚 View Documentation",
                action=ButtonAction.VIEW_DOCUMENTATION,
                value=ticket_key
            ))
        
        buttons.extend([
            InteractiveButton(
                id="chat_driftor",
                text="💭 Chat with Driftor",
                action=ButtonAction.CHAT_WITH_DRIFTOR,
                value=ticket_key
            ),
            InteractiveButton(
                id="mark_helpful",
                text="👍 Helpful",
                action=ButtonAction.MARK_HELPFUL,
                style="default",
                value=ticket_key
            ),
            InteractiveButton(
                id="mark_unhelpful",
                text="👎 Not Helpful",
                action=ButtonAction.MARK_UNHELPFUL,
                style="default",
                value=ticket_key
            )
        ])
        
        return MessageCard(
            title=title,
            subtitle=f"Automated analysis for {ticket_key}",
            text="\n".join(text_parts),
            color=color,
            facts=facts,
            buttons=buttons,
            correlation_id=ticket_key,
            thumbnail_url="https://driftor.dev/images/logo-small.png"
        )
    
    async def send_error_notification(
        self,
        user_id: str,
        error_message: str,
        ticket_key: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> MessageResponse:
        """Send error notification."""
        try:
            title = "⚠️ Analysis Error"
            if ticket_key:
                title += f": {ticket_key}"
            
            card = MessageCard(
                title=title,
                text=f"**Error:** {error_message}\n\nOur team has been notified and will investigate the issue.",
                color="attention",
                facts=[
                    {"name": "Ticket", "value": ticket_key or "Unknown"},
                    {"name": "Time", "value": "Just now"}
                ],
                buttons=[
                    InteractiveButton(
                        id="retry_analysis",
                        text="🔄 Retry Analysis",
                        action=ButtonAction.CHAT_WITH_DRIFTOR,
                        style="primary",
                        value=ticket_key or ""
                    )
                ]
            )
            
            response = await self.send_card(user_id, card)
            
            if tenant_id:
                await audit(
                    event_type=AuditEventType.NOTIFICATION_SENT,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    resource_type="error_notification",
                    details={
                        "platform": self.platform.value,
                        "error_message": error_message,
                        "ticket_key": ticket_key
                    }
                )
            
            return response
            
        except Exception as e:
            logger.error(
                "Failed to send error notification",
                user_id=user_id,
                error=str(e)
            )
            return MessageResponse(
                success=False,
                error=str(e),
                platform=self.platform.value
            )
    
    async def send_status_update(
        self,
        user_id: str,
        ticket_key: str,
        status_message: str,
        tenant_id: str
    ) -> MessageResponse:
        """Send status update message."""
        try:
            message = f"🔄 **{ticket_key} Update**\n\n{status_message}"
            response = await self.send_message(user_id, message)
            
            await audit(
                event_type=AuditEventType.NOTIFICATION_SENT,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="status_update",
                resource_id=ticket_key,
                details={
                    "platform": self.platform.value,
                    "message_id": response.message_id
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(
                "Failed to send status update",
                user_id=user_id,
                ticket_key=ticket_key,
                error=str(e)
            )
            return MessageResponse(
                success=False,
                error=str(e),
                platform=self.platform.value
            )
    
    def _format_similar_tickets(self, similar_tickets: List[Dict[str, Any]]) -> str:
        """Format similar tickets for display."""
        if not similar_tickets:
            return "No similar tickets found."
        
        lines = ["**Similar Issues:**"]
        for i, ticket in enumerate(similar_tickets[:3], 1):
            key = ticket.get("key", "")
            summary = ticket.get("summary", "")[:60]
            if len(ticket.get("summary", "")) > 60:
                summary += "..."
            
            lines.append(f"{i}. [{key}]({ticket.get('url', '')}) - {summary}")
        
        if len(similar_tickets) > 3:
            lines.append(f"... and {len(similar_tickets) - 3} more")
        
        return "\n".join(lines)
    
    def _format_documentation(self, docs: List[Dict[str, Any]]) -> str:
        """Format documentation links for display."""
        if not docs:
            return "No relevant documentation found."
        
        lines = ["**Relevant Documentation:**"]
        for i, doc in enumerate(docs[:3], 1):
            title = doc.get("title", "Untitled")[:50]
            if len(doc.get("title", "")) > 50:
                title += "..."
            
            lines.append(f"{i}. [{title}]({doc.get('url', '')})")
        
        if len(docs) > 3:
            lines.append(f"... and {len(docs) - 3} more")
        
        return "\n".join(lines)