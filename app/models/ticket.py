"""
Ticket model for storing and analyzing Jira tickets.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class TicketStatus(enum.Enum):
    """Jira ticket status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


class TicketPriority(enum.Enum):
    """Jira ticket priority."""
    LOWEST = "lowest"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    HIGHEST = "highest"


class Ticket(Base):
    """Model for storing Jira ticket information and analysis."""
    
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Jira ticket details
    jira_id = Column(String, unique=True, index=True, nullable=False)
    jira_key = Column(String, unique=True, index=True, nullable=False)
    project_key = Column(String, index=True, nullable=False)
    
    # Basic information
    title = Column(String, nullable=False)
    description = Column(Text)
    ticket_type = Column(String, nullable=False)  # Bug, Story, Task, etc.
    status = Column(Enum(TicketStatus), nullable=False)
    priority = Column(Enum(TicketPriority))
    
    # Assignment
    assignee_email = Column(String, index=True)
    assignee_name = Column(String)
    reporter_email = Column(String)
    reporter_name = Column(String)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True))
    
    # Analysis fields
    processed_at = Column(DateTime(timezone=True))
    analysis_result = Column(Text)  # JSON string with analysis results
    similar_tickets = Column(Text)  # JSON array of similar ticket IDs
    code_analysis = Column(Text)  # JSON string with code analysis results
    
    # Vector embeddings for similarity search
    title_embedding = Column(Text)  # JSON array of floats
    description_embedding = Column(Text)  # JSON array of floats
    
    # Metadata
    raw_data = Column(Text)  # Original Jira webhook payload
    sync_version = Column(Integer, default=1)
    
    def __repr__(self) -> str:
        return f"<Ticket(id={self.id}, key='{self.jira_key}', title='{self.title[:50]}...')>"