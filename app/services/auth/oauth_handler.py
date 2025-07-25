"""
OAuth authentication handler for external services.
"""
import secrets
import urllib.parse
from typing import Dict, Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class OAuthHandler:
    """Handle OAuth flows for external service integrations."""
    
    def __init__(self):
        self.state_storage: Dict[str, Dict] = {}  # In production, use Redis
    
    def get_jira_auth_url(self, user_id: Optional[str] = None) -> str:
        """Generate Jira OAuth authorization URL."""
        state = secrets.token_urlsafe(32)
        
        # Store state for validation
        self.state_storage[state] = {
            "service": "jira",
            "user_id": user_id,
        }
        
        # Jira OAuth 2.0 parameters
        params = {
            "audience": "api.atlassian.com",
            "client_id": "your-jira-client-id",  # From settings
            "scope": "read:jira-work read:jira-user",
            "redirect_uri": f"{settings.API_V1_STR}/auth/oauth/jira",
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
        
        base_url = "https://auth.atlassian.com/authorize"
        return f"{base_url}?{urllib.parse.urlencode(params)}"
    
    def get_confluence_auth_url(self, user_id: Optional[str] = None) -> str:
        """Generate Confluence OAuth authorization URL."""
        state = secrets.token_urlsafe(32)
        
        self.state_storage[state] = {
            "service": "confluence",
            "user_id": user_id,
        }
        
        params = {
            "audience": "api.atlassian.com",
            "client_id": "your-confluence-client-id",
            "scope": "read:confluence-content.all",
            "redirect_uri": f"{settings.API_V1_STR}/auth/oauth/confluence",
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
        
        base_url = "https://auth.atlassian.com/authorize"
        return f"{base_url}?{urllib.parse.urlencode(params)}"
    
    def get_github_auth_url(self, user_id: Optional[str] = None) -> str:
        """Generate GitHub OAuth authorization URL."""
        state = secrets.token_urlsafe(32)
        
        self.state_storage[state] = {
            "service": "github", 
            "user_id": user_id,
        }
        
        params = {
            "client_id": "your-github-client-id",
            "scope": "repo read:user",
            "redirect_uri": f"{settings.API_V1_STR}/auth/oauth/github",
            "state": state,
        }
        
        base_url = "https://github.com/login/oauth/authorize"
        return f"{base_url}?{urllib.parse.urlencode(params)}"
    
    async def exchange_jira_code(self, code: str, state: str) -> Dict:
        """Exchange Jira authorization code for access token."""
        if state not in self.state_storage:
            raise ValueError("Invalid state parameter")
        
        stored_state = self.state_storage.pop(state)
        if stored_state["service"] != "jira":
            raise ValueError("State mismatch")
        
        # TODO: Implement actual token exchange
        logger.info(f"Exchanging Jira code: {code}")
        
        return {
            "access_token": "mock-jira-token",
            "refresh_token": "mock-refresh-token",
            "user_id": stored_state.get("user_id")
        }
    
    async def exchange_confluence_code(self, code: str, state: str) -> Dict:
        """Exchange Confluence authorization code for access token."""
        if state not in self.state_storage:
            raise ValueError("Invalid state parameter")
        
        stored_state = self.state_storage.pop(state)
        if stored_state["service"] != "confluence":
            raise ValueError("State mismatch")
        
        logger.info(f"Exchanging Confluence code: {code}")
        
        return {
            "access_token": "mock-confluence-token",
            "refresh_token": "mock-refresh-token",
            "user_id": stored_state.get("user_id")
        }
    
    async def exchange_github_code(self, code: str, state: str) -> Dict:
        """Exchange GitHub authorization code for access token."""
        if state not in self.state_storage:
            raise ValueError("Invalid state parameter")
        
        stored_state = self.state_storage.pop(state)
        if stored_state["service"] != "github":
            raise ValueError("State mismatch")
        
        logger.info(f"Exchanging GitHub code: {code}")
        
        return {
            "access_token": "mock-github-token",
            "user_id": stored_state.get("user_id")
        }