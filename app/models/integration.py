"""
Integration models for external service connections.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class IntegrationType(enum.Enum):
    """Types of external integrations."""
    JIRA = "jira"
    CONFLUENCE = "confluence"
    GITHUB = "github"
    GITLAB = "gitlab"
    AZURE_DEVOPS = "azure_devops"


class Integration(Base):
    """Model for storing external service integrations."""
    
    __tablename__ = "integrations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Integration details
    integration_type = Column(Enum(IntegrationType), nullable=False)
    name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    
    # Authentication
    username = Column(String)
    encrypted_token = Column(Text)  # Encrypted API token/password
    oauth_token = Column(Text)  # OAuth access token
    oauth_refresh_token = Column(Text)  # OAuth refresh token
    oauth_expires_at = Column(DateTime(timezone=True))
    
    # Configuration
    config = Column(Text)  # JSON string for additional configuration
    
    # Status
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime(timezone=True))
    last_error = Column(Text)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="integrations")
    
    def __repr__(self) -> str:
        return f"<Integration(id={self.id}, type='{self.integration_type.value}', name='{self.name}')>"