"""
Integration schemas for request/response validation.
"""
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
from datetime import datetime

from app.models.integration import IntegrationType


class IntegrationBase(BaseModel):
    """Base integration schema."""
    integration_type: IntegrationType
    name: str
    base_url: HttpUrl


class IntegrationCreate(IntegrationBase):
    """Schema for creating a new integration."""
    username: Optional[str] = None
    api_token: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class IntegrationUpdate(BaseModel):
    """Schema for updating integration information."""
    name: Optional[str] = None
    base_url: Optional[HttpUrl] = None
    username: Optional[str] = None
    api_token: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class Integration(IntegrationBase):
    """Schema for integration responses."""
    id: int
    user_id: int
    is_active: bool
    last_sync: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}