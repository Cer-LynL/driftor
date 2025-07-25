"""
Confluence API client for searching documentation.
"""
import httpx
from typing import Dict, List, Optional, Any
import logging
import base64

from app.core.config import settings

logger = logging.getLogger(__name__)


class ConfluenceClient:
    """Client for interacting with Confluence REST API."""
    
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
    
    async def search_content(
        self, 
        query: str, 
        limit: int = 10,
        spaces: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search Confluence content by query."""
        try:
            # Build CQL (Confluence Query Language) query
            cql_query = f'text ~ "{query}"'
            
            if spaces:
                space_filter = " OR ".join([f'space.key = "{space}"' for space in spaces])
                cql_query += f' AND ({space_filter})'
            
            params = {
                'cql': cql_query,
                'limit': limit,
                'expand': 'space,version,body.view'
            }
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/rest/api/content/search"
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                results = data.get('results', [])
                
                # Format results
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        'id': result.get('id'),
                        'title': result.get('title', ''),
                        'url': self._build_page_url(result),
                        'excerpt': self._extract_excerpt(result),
                        'space': result.get('space', {}),
                        'type': result.get('type', ''),
                        'last_modified': result.get('version', {}).get('when', '')
                    })
                
                return formatted_results
                
        except Exception as e:
            logger.error(f"Error searching Confluence content for '{query}': {e}")
            return []
    
    async def get_page_content(self, page_id: str) -> Optional[Dict[str, Any]]:
        """Get full content of a Confluence page."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/rest/api/content/{page_id}"
                params = {'expand': 'body.storage,space,version'}
                
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                return response.json()
                
        except Exception as e:
            logger.error(f"Error fetching page content for {page_id}: {e}")
            return None
    
    async def search_by_labels(
        self, 
        labels: List[str], 
        space_key: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search content by labels."""
        try:
            label_query = " AND ".join([f'label = "{label}"' for label in labels])
            cql_query = f'({label_query})'
            
            if space_key:
                cql_query += f' AND space.key = "{space_key}"'
            
            params = {
                'cql': cql_query,
                'limit': limit,
                'expand': 'space,version'
            }
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/rest/api/content/search"
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                results = data.get('results', [])
                
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        'id': result.get('id'),
                        'title': result.get('title', ''),
                        'url': self._build_page_url(result),
                        'space': result.get('space', {}),
                        'labels': labels,
                        'last_modified': result.get('version', {}).get('when', '')
                    })
                
                return formatted_results
                
        except Exception as e:
            logger.error(f"Error searching by labels {labels}: {e}")
            return []
    
    async def get_spaces(self) -> List[Dict[str, Any]]:
        """Get list of accessible spaces."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/rest/api/space"
                params = {'limit': 100}
                
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                return data.get('results', [])
                
        except Exception as e:
            logger.error(f"Error fetching spaces: {e}")
            return []
    
    def _build_page_url(self, result: Dict[str, Any]) -> str:
        """Build full URL for a Confluence page."""
        page_id = result.get('id')
        space_key = result.get('space', {}).get('key', '')
        title = result.get('title', '').replace(' ', '+')
        
        # Try to build a clean URL
        if space_key and title:
            return f"{self.base_url}/spaces/{space_key}/pages/{page_id}/{title}"
        else:
            return f"{self.base_url}/pages/viewpage.action?pageId={page_id}"
    
    def _extract_excerpt(self, result: Dict[str, Any]) -> str:
        """Extract text excerpt from page content."""
        try:
            body = result.get('body', {})
            if 'view' in body:
                view_content = body['view'].get('value', '')
                # Remove HTML tags and get first 200 characters
                import re
                clean_text = re.sub(r'<[^>]+>', '', view_content)
                return clean_text.strip()[:200] + '...' if len(clean_text) > 200 else clean_text.strip()
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting excerpt: {e}")
            return ""
    
    @classmethod
    def from_settings(cls) -> Optional['ConfluenceClient']:
        """Create Confluence client from application settings."""
        if not all([settings.CONFLUENCE_BASE_URL, settings.CONFLUENCE_USERNAME, settings.CONFLUENCE_API_TOKEN]):
            logger.warning("Confluence configuration not complete in settings")
            return None
        
        return cls(
            base_url=settings.CONFLUENCE_BASE_URL,
            username=settings.CONFLUENCE_USERNAME,
            api_token=settings.CONFLUENCE_API_TOKEN
        )