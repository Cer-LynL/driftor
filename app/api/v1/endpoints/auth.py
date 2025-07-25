"""
Authentication endpoints for user management and OAuth flows.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.core.database import get_db
from app.schemas.user import User, UserCreate
from app.models.user import User as UserModel
from app.services.auth.oauth_handler import OAuthHandler

router = APIRouter()
oauth_handler = OAuthHandler()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=User)
async def register_user(
    user_data: UserCreate, 
    db: Session = Depends(get_db)
) -> User:
    """Register a new user."""
    try:
        # Check if user already exists
        existing_user = db.query(UserModel).filter(
            UserModel.email == user_data.email
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Create new user
        db_user = UserModel(
            email=user_data.email,
            full_name=user_data.full_name,
            microsoft_user_id=user_data.microsoft_user_id,
            teams_user_id=user_data.teams_user_id,
            is_active=True
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return User.model_validate(db_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/oauth/jira")
async def jira_oauth_flow(
    code: Optional[str] = None,
    state: Optional[str] = None
) -> dict:
    """Handle Jira OAuth callback."""
    if not code:
        # Return OAuth authorization URL
        auth_url = oauth_handler.get_jira_auth_url()
        return {"auth_url": auth_url}
    
    # Exchange code for tokens
    tokens = await oauth_handler.exchange_jira_code(code, state)
    return {"status": "success", "message": "Jira integration connected"}


@router.get("/oauth/confluence")
async def confluence_oauth_flow(
    code: Optional[str] = None,
    state: Optional[str] = None
) -> dict:
    """Handle Confluence OAuth callback."""
    if not code:
        auth_url = oauth_handler.get_confluence_auth_url()
        return {"auth_url": auth_url}
    
    tokens = await oauth_handler.exchange_confluence_code(code, state)
    return {"status": "success", "message": "Confluence integration connected"}


@router.get("/oauth/github")
async def github_oauth_flow(
    code: Optional[str] = None,
    state: Optional[str] = None
) -> dict:
    """Handle GitHub OAuth callback."""
    if not code:
        auth_url = oauth_handler.get_github_auth_url()
        return {"auth_url": auth_url}
    
    tokens = await oauth_handler.exchange_github_code(code, state)
    return {"status": "success", "message": "GitHub integration connected"}