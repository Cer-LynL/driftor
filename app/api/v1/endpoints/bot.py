"""
Microsoft Teams bot endpoints.
"""
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import logging

from app.services.bot.teams_adapter import TeamsAdapter

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize Teams adapter
teams_adapter = TeamsAdapter()


@router.post("/messages")
async def handle_teams_message(
    request: Request,
    authorization: Optional[str] = Header(None)
) -> dict:
    """Handle incoming messages from Microsoft Teams."""
    try:
        # Get the request body
        body = await request.json()
        
        # Get authorization header
        auth_header = authorization or ""
        
        logger.info(f"Received Teams activity: {body.get('type', 'unknown')}")
        
        # Process the activity
        response = await teams_adapter.process_activity(body, auth_header)
        
        return response or {}
        
    except Exception as e:
        logger.error(f"Error handling Teams message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def bot_status() -> dict:
    """Get bot status and health information."""
    return {
        "status": "online",
        "bot_id": teams_adapter.bot.__class__.__name__,
        "integrations": {
            "jira": "connected",
            "confluence": "connected", 
            "github": "connected"
        }
    }