"""
User schemas for request/response validation.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    full_name: str
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for creating a new user."""
    microsoft_user_id: Optional[str] = None
    teams_user_id: Optional[str] = None


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    notification_preferences: Optional[dict] = None


class User(UserBase):
    """Schema for user responses."""
    id: int
    microsoft_user_id: Optional[str] = None
    teams_user_id: Optional[str] = None
    is_admin: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    
    model_config = {"from_attributes": True}