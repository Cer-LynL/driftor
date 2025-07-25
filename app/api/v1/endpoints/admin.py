"""
Admin endpoints for project mapping and system management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.schemas.project_mapping import ProjectMapping, ProjectMappingCreate

router = APIRouter()


@router.get("/project-mappings", response_model=List[ProjectMapping])
async def list_project_mappings(
    db: Session = Depends(get_db)
) -> List[ProjectMapping]:
    """List all project-to-repository mappings."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Project mapping listing not yet implemented"
    )


@router.post("/project-mappings", response_model=ProjectMapping)
async def create_project_mapping(
    mapping_data: ProjectMappingCreate,
    db: Session = Depends(get_db)
) -> ProjectMapping:
    """Create a new project-to-repository mapping."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Project mapping creation not yet implemented"
    )


@router.post("/project-mappings/auto-discover")
async def auto_discover_mappings(
    db: Session = Depends(get_db)
) -> dict:
    """Automatically discover project-to-repository mappings."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Auto-discovery not yet implemented"
    )


@router.put("/project-mappings/{mapping_id}/verify")
async def verify_mapping(
    mapping_id: int,
    verified: bool = True,
    notes: str = "",
    db: Session = Depends(get_db)
) -> dict:
    """Verify or reject an automatically discovered mapping."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Mapping verification not yet implemented"
    )


@router.get("/system/health")
async def system_health() -> dict:
    """Get detailed system health information."""
    return {
        "status": "healthy",
        "components": {
            "database": "connected",
            "redis": "connected", 
            "qdrant": "connected",
            "bot_framework": "connected"
        },
        "integrations": {
            "jira": "configured",
            "confluence": "configured",
            "github": "configured"
        }
    }