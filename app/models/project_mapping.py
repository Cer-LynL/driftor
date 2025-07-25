"""
Project mapping model for linking Jira projects to Git repositories.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, Float, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class MappingConfidence(enum.Enum):
    """Confidence level for automated project-to-repo mapping."""
    HIGH = "high"        # >85% confidence, auto-applied
    MEDIUM = "medium"    # 60-85% confidence, requires review
    LOW = "low"          # <60% confidence, flagged for manual review


class ProjectMapping(Base):
    """Model for mapping Jira projects to Git repositories."""
    
    __tablename__ = "project_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Jira project information
    jira_project_key = Column(String, index=True, nullable=False)
    jira_project_name = Column(String, nullable=False)
    jira_project_id = Column(String, nullable=False)
    
    # Git repository information
    git_provider = Column(String, nullable=False)  # github, gitlab, azure_devops
    git_organization = Column(String, nullable=False)
    git_repository = Column(String, nullable=False)
    git_branch = Column(String, default="main")
    git_repository_id = Column(String)  # Provider-specific repo ID
    
    # Mapping metadata
    confidence_score = Column(Float)  # 0.0 to 1.0
    confidence_level = Column(Enum(MappingConfidence))
    mapping_algorithm = Column(String)  # How this mapping was determined
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # Human-verified mapping
    verification_notes = Column(Text)
    
    # Analysis data
    matching_factors = Column(Text)  # JSON with factors that led to this mapping
    alternative_mappings = Column(Text)  # JSON with other potential mappings
    
    # Audit trail
    created_by_id = Column(Integer, ForeignKey("users.id"))
    verified_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    verified_at = Column(DateTime(timezone=True))
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="project_mappings")
    verified_by = relationship("User", foreign_keys=[verified_by_id])
    
    def __repr__(self) -> str:
        return (f"<ProjectMapping(id={self.id}, "
                f"jira='{self.jira_project_key}', "
                f"git='{self.git_organization}/{self.git_repository}', "
                f"confidence='{self.confidence_level}')>")