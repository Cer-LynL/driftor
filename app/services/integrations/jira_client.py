"""
Jira API client for fetching tickets and project information.
"""
import httpx
from typing import Dict, List, Optional, Any
import logging
import base64

from app.core.config import settings

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for interacting with Jira REST API."""
    
    def __init__(self, base_url: str, username: str, api_token: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.api_token = api_token
        
        # Create authentication header
        auth_string = f"{username}:{api_token}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        self.headers = {
            "Authorization": f"Basic {auth_b64}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    async def get_ticket(self, ticket_key: str) -> Optional[Dict[str, Any]]:
        """Fetch a single ticket by key."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/rest/api/3/issue/{ticket_key}"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching ticket {ticket_key}: {e}")
            return None
    
    async def search_tickets(
        self,
        jql: str,
        fields: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Search tickets using JQL."""
        try:
            if fields is None:
                fields = ["summary", "description", "assignee", "reporter", "status", "priority", "created", "updated"]
            
            payload = {
                "jql": jql,
                "fields": fields,
                "maxResults": max_results
            }
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/rest/api/3/search"
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("issues", [])
        except Exception as e:
            logger.error(f"Error searching tickets with JQL '{jql}': {e}")
            return []
    
    async def get_similar_tickets(
        self,
        project_key: str,
        title: str,
        description: str = "",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find similar tickets in the same project."""
        # Extract keywords from title and description
        keywords = self._extract_keywords(title, description)
        
        if not keywords:
            return []
        
        # Build JQL query to find similar tickets
        keyword_query = " OR ".join([f'text ~ "{keyword}"' for keyword in keywords[:5]])
        jql = f'project = {project_key} AND ({keyword_query}) ORDER BY created DESC'
        
        return await self.search_tickets(jql, max_results=limit)
    
    async def get_project_info(self, project_key: str) -> Optional[Dict[str, Any]]:
        """Get project information."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/rest/api/3/project/{project_key}"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching project {project_key}: {e}")
            return None
    
    async def get_ticket_history(self, ticket_key: str) -> List[Dict[str, Any]]:
        """Get ticket history and changelog."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/rest/api/3/issue/{ticket_key}?expand=changelog"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                return data.get("changelog", {}).get("histories", [])
        except Exception as e:
            logger.error(f"Error fetching ticket history for {ticket_key}: {e}")
            return []
    
    def _extract_keywords(self, title: str, description: str = "") -> List[str]:
        """Extract meaningful keywords from ticket title and description."""
        import re
        
        text = f"{title} {description}".lower()
        
        # Remove common stop words and extract meaningful terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'cannot', 'not', 'no'
        }
        
        # Extract words (alphanumeric, 3+ chars)
        words = re.findall(r'\b[a-zA-Z0-9]{3,}\b', text)
        
        # Filter out stop words and common generic terms
        keywords = [
            word for word in words 
            if word not in stop_words and len(word) >= 3
        ]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for keyword in keywords:
            if keyword not in seen:
                seen.add(keyword)
                unique_keywords.append(keyword)
        
        return unique_keywords[:10]  # Return top 10 keywords
    
    @classmethod
    def from_settings(cls) -> Optional['JiraClient']:
        """Create Jira client from application settings."""
        if not all([settings.JIRA_BASE_URL, settings.JIRA_USERNAME, settings.JIRA_API_TOKEN]):
            logger.warning("Jira configuration not complete in settings")
            return None
        
        return cls(
            base_url=settings.JIRA_BASE_URL,
            username=settings.JIRA_USERNAME,
            api_token=settings.JIRA_API_TOKEN
        )