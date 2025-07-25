"""
Ticket schemas for request/response validation.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.ticket import TicketStatus, TicketPriority


class TicketBase(BaseModel):
    """Base ticket schema."""
    jira_id: str
    jira_key: str
    project_key: str
    title: str
    description: Optional[str] = None
    ticket_type: str
    status: TicketStatus
    priority: Optional[TicketPriority] = None


class TicketCreate(TicketBase):
    """Schema for creating a new ticket."""
    assignee_email: Optional[str] = None
    assignee_name: Optional[str] = None
    reporter_email: Optional[str] = None
    reporter_name: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class TicketUpdate(BaseModel):
    """Schema for updating ticket information."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assignee_email: Optional[str] = None
    assignee_name: Optional[str] = None


class TicketAnalysis(BaseModel):
    """Schema for ticket analysis results."""
    similar_tickets: List[Dict[str, Any]] = []
    documentation_links: List[Dict[str, str]] = []
    code_analysis: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None


class Ticket(TicketBase):
    """Schema for ticket responses."""
    id: int
    assignee_email: Optional[str] = None
    assignee_name: Optional[str] = None
    reporter_email: Optional[str] = None
    reporter_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    analysis_result: Optional[TicketAnalysis] = None
    
    model_config = {"from_attributes": True}