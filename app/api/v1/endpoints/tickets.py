"""
Ticket management and analysis endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List, Optional
import logging

from app.core.database import get_db
from app.schemas.ticket import TicketCreate, Ticket as TicketSchema
from app.models.ticket import Ticket
from app.services.integrations.jira_webhook import JiraWebhookProcessor

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[TicketSchema])
async def list_tickets(
    project_key: Optional[str] = None,
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
) -> List[TicketSchema]:
    """List tickets with optional filtering."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Ticket listing not yet implemented"
    )


@router.get("/{ticket_id}", response_model=TicketSchema)
async def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db)
) -> TicketSchema:
    """Get a specific ticket with analysis results."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Ticket retrieval not yet implemented"
    )


@router.post("/webhook/jira")
async def jira_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_atlassian_webhook_identifier: Optional[str] = Header(None)
) -> dict:
    """Handle Jira webhook for ticket events."""
    try:
        # Get webhook payload
        payload = await request.body()
        webhook_data = await request.json()
        
        # Initialize webhook processor
        processor = JiraWebhookProcessor()
        
        # Validate signature if configured
        signature = request.headers.get('x-hub-signature-256', '')
        if not processor.validate_webhook_signature(payload, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        logger.info(f"Received Jira webhook: {webhook_data.get('webhookEvent', 'unknown')}")
        
        # Check if this is a ticket assignment event
        if not processor.is_ticket_assignment_event(webhook_data):
            logger.info("Webhook event is not a ticket assignment, ignoring")
            return {"status": "ignored", "reason": "Not a ticket assignment event"}
        
        # Check if this is a bug ticket (MVP scope)
        if not processor.is_bug_ticket(webhook_data):
            logger.info("Webhook event is not a bug ticket, ignoring for MVP")
            return {"status": "ignored", "reason": "Not a bug ticket"}
        
        # Extract ticket data
        ticket_data = processor.extract_ticket_data(webhook_data)
        if not ticket_data:
            raise HTTPException(status_code=400, detail="Could not extract ticket data")
        
        # Check if ticket already exists
        existing_ticket = db.query(Ticket).filter(
            Ticket.jira_key == ticket_data.jira_key
        ).first()
        
        if existing_ticket:
            # Update existing ticket
            for field, value in ticket_data.dict(exclude_unset=True).items():
                if field != 'raw_data':  # Don't overwrite raw_data
                    setattr(existing_ticket, field, value)
            existing_ticket.updated_at = func.now()
            db.commit()
            
            ticket_id = existing_ticket.id
            logger.info(f"Updated existing ticket: {ticket_data.jira_key}")
        else:
            # Create new ticket
            db_ticket = Ticket(**ticket_data.dict())
            db.add(db_ticket)
            db.commit()
            db.refresh(db_ticket)
            
            ticket_id = db_ticket.id
            logger.info(f"Created new ticket: {ticket_data.jira_key}")
        
        # Trigger asynchronous analysis if assignee is present
        if ticket_data.assignee_email:
            from app.tasks.ticket_analysis import analyze_ticket_task
            task = analyze_ticket_task.delay(ticket_id)
            
            return {
                "status": "accepted", 
                "ticket_key": ticket_data.jira_key,
                "task_id": task.id,
                "assignee": ticket_data.assignee_email
            }
        else:
            return {
                "status": "accepted",
                "ticket_key": ticket_data.jira_key, 
                "message": "No assignee found, skipping analysis"
            }
            
    except Exception as e:
        logger.error(f"Error processing Jira webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{ticket_id}/analyze")
async def analyze_ticket(
    ticket_id: int,
    db: Session = Depends(get_db)
) -> dict:
    """Trigger manual analysis of a ticket."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Ticket analysis not yet implemented"
    )


@router.get("/{ticket_id}/similar")
async def find_similar_tickets(
    ticket_id: int,
    limit: int = 5,
    db: Session = Depends(get_db)
) -> List[dict]:
    """Find similar tickets using vector search."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Similar ticket search not yet implemented"
    )