"""
Project mapping schemas for request/response validation.
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.models.project_mapping import MappingConfidence


class ProjectMappingBase(BaseModel):
    """Base project mapping schema."""
    jira_project_key: str
    jira_project_name: str
    jira_project_id: str
    git_provider: str
    git_organization: str
    git_repository: str
    git_branch: str = "main"


class ProjectMappingCreate(ProjectMappingBase):
    """Schema for creating a new project mapping."""
    git_repository_id: Optional[str] = None
    confidence_score: Optional[float] = None
    confidence_level: Optional[MappingConfidence] = None
    mapping_algorithm: Optional[str] = None
    matching_factors: Optional[Dict[str, Any]] = None


class ProjectMappingUpdate(BaseModel):
    """Schema for updating project mapping."""
    git_branch: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    verification_notes: Optional[str] = None


class AlternativeMapping(BaseModel):
    """Schema for alternative mapping suggestions."""
    git_organization: str
    git_repository: str
    confidence_score: float
    matching_factors: Dict[str, Any]


class ProjectMapping(ProjectMappingBase):
    """Schema for project mapping responses."""
    id: int
    git_repository_id: Optional[str] = None
    confidence_score: Optional[float] = None
    confidence_level: Optional[MappingConfidence] = None
    mapping_algorithm: Optional[str] = None
    is_active: bool
    is_verified: bool
    verification_notes: Optional[str] = None
    matching_factors: Optional[Dict[str, Any]] = None
    alternative_mappings: Optional[List[AlternativeMapping]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}