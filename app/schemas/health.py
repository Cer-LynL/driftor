"""
Health check schemas.
"""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    database: str
    version: str