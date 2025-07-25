"""
User model for authentication and permissions.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """User model for storing user information and permissions."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    microsoft_user_id = Column(String, unique=True, index=True)
    teams_user_id = Column(String, unique=True, index=True)
    
    # Authentication
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Preferences
    notification_preferences = Column(Text)  # JSON string
    
    # Relationships
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    project_mappings = relationship("ProjectMapping", back_populates="created_by")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"