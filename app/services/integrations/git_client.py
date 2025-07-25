"""
Git repository client for GitHub/GitLab integration and code analysis.
"""
import httpx
from typing import Dict, List, Optional, Any
import logging
import base64

from app.core.config import settings

logger = logging.getLogger(__name__)


class GitClient:
    """Generic Git client supporting GitHub and GitLab."""
    
    def __init__(self, provider: str, organization: str, repository: str, token: Optional[str] = None):
        self.provider = provider.lower()
        self.organization = organization
        self.repository = repository
        
        # Set up provider-specific configuration
        if self.provider == 'github':
            self.base_url = "https://api.github.com"
            self.token = token or settings.GITHUB_TOKEN
            self.headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json"
            }
        elif self.provider == 'gitlab':
            self.base_url = "https://gitlab.com/api/v4"
            self.token = token or settings.GITLAB_TOKEN
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            raise ValueError(f"Unsupported Git provider: {provider}")
    
    async def search_code(
        self, 
        query: str, 
        file_extension: Optional[str] = None,
        path: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search code in the repository."""
        try:
            if self.provider == 'github':
                return await self._search_github_code(query, file_extension, path, limit)
            elif self.provider == 'gitlab':
                return await self._search_gitlab_code(query, file_extension, path, limit)
        except Exception as e:
            logger.error(f"Error searching code: {e}")
            return []
    
    async def get_file_content(self, file_path: str, branch: str = "main") -> Optional[str]:
        """Get content of a specific file."""
        try:
            if self.provider == 'github':
                return await self._get_github_file_content(file_path, branch)
            elif self.provider == 'gitlab':
                return await self._get_gitlab_file_content(file_path, branch)
        except Exception as e:
            logger.error(f"Error getting file content for {file_path}: {e}")
            return None
    
    async def get_repository_structure(self, path: str = "", branch: str = "main") -> List[Dict[str, Any]]:
        """Get repository directory structure."""
        try:
            if self.provider == 'github':
                return await self._get_github_tree(path, branch)
            elif self.provider == 'gitlab':
                return await self._get_gitlab_tree(path, branch)
        except Exception as e:
            logger.error(f"Error getting repository structure: {e}")
            return []
    
    async def search_issues(self, query: str, state: str = "all", limit: int = 10) -> List[Dict[str, Any]]:
        """Search repository issues."""
        try:
            if self.provider == 'github':
                return await self._search_github_issues(query, state, limit)
            elif self.provider == 'gitlab':
                return await self._search_gitlab_issues(query, state, limit)
        except Exception as e:
            logger.error(f"Error searching issues: {e}")
            return []
    
    # GitHub-specific implementations
    async def _search_github_code(self, query: str, file_extension: Optional[str], path: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """Search GitHub code."""
        search_query = f"{query} repo:{self.organization}/{self.repository}"
        
        if file_extension:
            search_query += f" extension:{file_extension}"
        if path:
            search_query += f" path:{path}"
        
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/search/code"
            params = {'q': search_query, 'per_page': limit}
            
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('items', []):
                results.append({
                    'file_path': item.get('path'),
                    'file_name': item.get('name'),
                    'url': item.get('html_url'),
                    'score': item.get('score', 0),
                    'matches': []  # GitHub doesn't provide match details in search
                })
            
            return results
    
    async def _get_github_file_content(self, file_path: str, branch: str) -> Optional[str]:
        """Get GitHub file content."""
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/repos/{self.organization}/{self.repository}/contents/{file_path}"
            params = {'ref': branch}
            
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get('encoding') == 'base64':
                content = base64.b64decode(data.get('content', '')).decode('utf-8')
                return content
            
            return data.get('content')
    
    async def _get_github_tree(self, path: str, branch: str) -> List[Dict[str, Any]]:
        """Get GitHub repository tree."""
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/repos/{self.organization}/{self.repository}/contents/{path}"
            params = {'ref': branch}
            
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            return response.json()
    
    async def _search_github_issues(self, query: str, state: str, limit: int) -> List[Dict[str, Any]]:
        """Search GitHub issues."""
        search_query = f"{query} repo:{self.organization}/{self.repository}"
        if state != "all":
            search_query += f" state:{state}"
        
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/search/issues"
            params = {'q': search_query, 'per_page': limit}
            
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get('items', [])
    
    # GitLab-specific implementations
    async def _search_gitlab_code(self, query: str, file_extension: Optional[str], path: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """Search GitLab code."""
        project_id = f"{self.organization}%2F{self.repository}"
        
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/projects/{project_id}/search"
            params = {
                'scope': 'blobs',
                'search': query,
                'per_page': limit
            }
            
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data:
                file_path = item.get('path', '')
                if file_extension and not file_path.endswith(f'.{file_extension}'):
                    continue
                if path and not file_path.startswith(path):
                    continue
                
                results.append({
                    'file_path': file_path,
                    'file_name': file_path.split('/')[-1],
                    'url': item.get('web_url'),
                    'matches': [item.get('data', '')]
                })
            
            return results
    
    async def _get_gitlab_file_content(self, file_path: str, branch: str) -> Optional[str]:
        """Get GitLab file content."""
        project_id = f"{self.organization}%2F{self.repository}"
        encoded_path = file_path.replace('/', '%2F')
        
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/projects/{project_id}/repository/files/{encoded_path}/raw"
            params = {'ref': branch}
            
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            return response.text
    
    async def _get_gitlab_tree(self, path: str, branch: str) -> List[Dict[str, Any]]:
        """Get GitLab repository tree."""
        project_id = f"{self.organization}%2F{self.repository}"
        
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/projects/{project_id}/repository/tree"
            params = {'ref': branch, 'path': path, 'per_page': 100}
            
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            return response.json()
    
    async def _search_gitlab_issues(self, query: str, state: str, limit: int) -> List[Dict[str, Any]]:
        """Search GitLab issues."""
        project_id = f"{self.organization}%2F{self.repository}"
        
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/projects/{project_id}/issues"
            params = {
                'search': query,
                'state': state,
                'per_page': limit
            }
            
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            return response.json()
    
    def get_repository_url(self) -> str:
        """Get the web URL for the repository."""
        if self.provider == 'github':
            return f"https://github.com/{self.organization}/{self.repository}"
        elif self.provider == 'gitlab':
            return f"https://gitlab.com/{self.organization}/{self.repository}"
        return ""