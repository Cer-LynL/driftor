"""
Simple web interface for user onboarding and integration setup.
"""
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models.integration import Integration, IntegrationType
from app.services.auth.oauth_handler import OAuthHandler
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
oauth_handler = OAuthHandler()


@router.get("/", response_class=HTMLResponse)
async def onboarding_home(request: Request):
    """Main onboarding page."""
    return templates.TemplateResponse("onboarding/home.html", {
        "request": request,
        "project_name": settings.PROJECT_NAME
    })


@router.get("/setup", response_class=HTMLResponse)
async def setup_integrations(request: Request, db: Session = Depends(get_db)):
    """Integration setup page."""
    # Get existing integrations
    integrations = db.query(Integration).filter(Integration.is_active == True).all()
    
    integration_status = {
        "jira": any(i.integration_type == IntegrationType.JIRA for i in integrations),
        "confluence": any(i.integration_type == IntegrationType.CONFLUENCE for i in integrations),
        "github": any(i.integration_type == IntegrationType.GITHUB for i in integrations),
    }
    
    return templates.TemplateResponse("onboarding/setup.html", {
        "request": request,
        "integration_status": integration_status,
        "jira_oauth_url": f"{settings.API_V1_STR}/auth/oauth/jira",
        "confluence_oauth_url": f"{settings.API_V1_STR}/auth/oauth/confluence",
        "github_oauth_url": f"{settings.API_V1_STR}/auth/oauth/github"
    })


@router.get("/success", response_class=HTMLResponse)
async def onboarding_success(request: Request):
    """Onboarding completion page."""
    return templates.TemplateResponse("onboarding/success.html", {
        "request": request,
        "teams_bot_endpoint": f"{request.base_url}api/v1/bot/messages",
        "jira_webhook_endpoint": f"{request.base_url}api/v1/tickets/webhook/jira"
    })


@router.post("/manual-setup")
async def manual_integration_setup(
    request: Request,
    integration_type: str = Form(...),
    name: str = Form(...),
    base_url: str = Form(...),
    username: str = Form(...),
    api_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle manual integration setup form."""
    try:
        # Validate integration type
        if integration_type not in ["jira", "confluence", "github"]:
            raise HTTPException(status_code=400, detail="Invalid integration type")
        
        # Create integration (simplified for MVP)
        integration = Integration(
            integration_type=IntegrationType(integration_type),
            name=name,
            base_url=base_url,
            username=username,
            encrypted_token=api_token,  # In production, encrypt this
            is_active=True,
            user_id=1  # For MVP, use default user ID
        )
        
        db.add(integration)
        db.commit()
        
        return RedirectResponse(url="/onboarding/setup?success=true", status_code=303)
        
    except Exception as e:
        return RedirectResponse(url=f"/onboarding/setup?error={str(e)}", status_code=303)