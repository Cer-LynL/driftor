"""
Background tasks for ticket analysis and Teams notifications.
"""
from celery import current_task
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import logging

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.ticket import Ticket
from app.services.integrations.jira_client import JiraClient
from app.services.bot.teams_adapter import TeamsAdapter
from app.services.analysis.ticket_analyzer import TicketAnalyzer
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def analyze_ticket_task(self, ticket_id: int) -> Dict[str, Any]:
    """Analyze a ticket and send Teams notification."""
    try:
        current_task.update_state(state='PROGRESS', meta={'step': 'Starting analysis'})
        
        # Get database session
        db = SessionLocal()
        
        try:
            # Fetch ticket from database
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")
            
            current_task.update_state(state='PROGRESS', meta={'step': 'Analyzing ticket'})
            
            # Initialize services
            jira_client = JiraClient.from_settings()
            analyzer = TicketAnalyzer()
            
            # Perform analysis (run async function in sync task)
            import asyncio
            analysis_result = asyncio.run(analyzer.analyze_ticket(ticket, jira_client, db))
            
            # Update ticket with analysis results
            ticket.analysis_result = analysis_result
            ticket.processed_at = func.now()
            db.commit()
            
            current_task.update_state(state='PROGRESS', meta={'step': 'Sending Teams notification'})
            
            # Send Teams notification
            if ticket.assignee_email:
                send_teams_notification.delay(
                    ticket_id=ticket_id,
                    analysis_result=analysis_result
                )
            
            return {
                'status': 'completed',
                'ticket_id': ticket_id,
                'analysis_summary': {
                    'similar_tickets_found': len(analysis_result.get('similar_tickets', [])),
                    'documentation_links': len(analysis_result.get('documentation_links', [])),
                    'code_analysis_available': bool(analysis_result.get('code_analysis'))
                }
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error analyzing ticket {ticket_id}: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'ticket_id': ticket_id}
        )
        raise


@celery_app.task(bind=True)
def send_teams_notification(self, ticket_id: int, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """Send Teams notification about ticket analysis."""
    try:
        current_task.update_state(state='PROGRESS', meta={'step': 'Preparing notification'})
        
        db = SessionLocal()
        
        try:
            # Fetch ticket
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")
            
            # Format notification message
            message = format_ticket_notification(ticket, analysis_result)
            
            # Initialize Teams adapter
            teams_adapter = TeamsAdapter()
            
            # Send proactive message (requires stored conversation reference)
            # For MVP, we'll log the message that would be sent
            logger.info(f"Teams notification for {ticket.assignee_email}: {message}")
            
            # TODO: Implement actual proactive messaging
            # This requires storing conversation references when users first interact
            
            return {
                'status': 'completed',
                'ticket_id': ticket_id,
                'recipient': ticket.assignee_email,
                'message_preview': message[:100] + '...'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error sending Teams notification for ticket {ticket_id}: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'ticket_id': ticket_id}
        )
        raise


def format_ticket_notification(ticket: Ticket, analysis_result: Dict[str, Any]) -> str:
    """Format the Teams notification message for a new ticket assignment."""
    
    # Build the main notification
    message_parts = [
        f"🎫 **New Ticket Assigned: [{ticket.jira_key}]({get_jira_url(ticket)})**",
        f"",
        f"**{ticket.title}**",
        f"",
        f"📋 **Overview:**",
        f"{ticket.description[:200]}..." if len(ticket.description) > 200 else ticket.description,
        f"",
        f"🏷️ **Details:**",
        f"• Priority: {ticket.priority.value if ticket.priority else 'Not set'}",
        f"• Type: {ticket.ticket_type}",
        f"• Project: {ticket.project_key}",
        f""
    ]
    
    # Add similar tickets if found
    similar_tickets = analysis_result.get('similar_tickets', [])
    if similar_tickets:
        message_parts.extend([
            f"🔍 **Similar Issues Found:**",
        ])
        for i, similar in enumerate(similar_tickets[:3], 1):  # Show top 3
            message_parts.append(f"{i}. [{similar['key']}]({get_jira_url_by_key(similar['key'])}) - {similar['title'][:60]}...")
        
        if len(similar_tickets) > 3:
            message_parts.append(f"   *...and {len(similar_tickets) - 3} more*")
        message_parts.append("")
    
    # Add documentation links if found
    doc_links = analysis_result.get('documentation_links', [])
    if doc_links:
        message_parts.extend([
            f"📚 **Related Documentation:**",
        ])
        for i, doc in enumerate(doc_links[:3], 1):  # Show top 3
            message_parts.append(f"{i}. [{doc['title']}]({doc['url']})")
        message_parts.append("")
    
    # Add code analysis if available
    code_analysis = analysis_result.get('code_analysis')
    if code_analysis:
        file_locations = code_analysis.get('file_locations', [])
        if file_locations:
            message_parts.extend([
                f"💻 **Potential Code Issues:**",
            ])
            for location in file_locations[:2]:  # Show top 2
                message_parts.append(f"• `{location['file_path']}` - {location['description']}")
            message_parts.append("")
    
    # Add action prompts
    message_parts.extend([
        f"**What you can do:**",
        f"• Type `elaborate {ticket.jira_key}` for detailed analysis",
        f"• Ask me questions about this ticket",
        f"• Review similar issues and documentation above",
        f"",
        f"Ready to help! 🤖"
    ])
    
    return "\n".join(message_parts)


def get_jira_url(ticket: Ticket) -> str:
    """Get Jira ticket URL."""
    from app.core.config import settings
    base_url = settings.JIRA_BASE_URL or "https://your-domain.atlassian.net"
    return f"{base_url}/browse/{ticket.jira_key}"


def get_jira_url_by_key(ticket_key: str) -> str:
    """Get Jira ticket URL by key."""
    from app.core.config import settings
    base_url = settings.JIRA_BASE_URL or "https://your-domain.atlassian.net"
    return f"{base_url}/browse/{ticket_key}"