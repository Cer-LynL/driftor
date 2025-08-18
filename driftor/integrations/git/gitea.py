"""
Gitea integration for self-hosted Git repositories.
"""
import base64
from typing import Dict, List, Optional
import httpx
import structlog

from .base import BaseGitProvider, Repository, FileContent, SearchResult, GitBlameInfo, GitProvider
from driftor.integrations.base import IntegrationConfig, WebhookConfig
from driftor.core.rate_limiter import RateLimitType

logger = structlog.get_logger(__name__)


class GiteaProvider(BaseGitProvider):
    """Gitea integration for self-hosted instances."""
    
    def __init__(self, config: IntegrationConfig, credentials: Dict[str, str]):
        super().__init__(config, credentials)
        
        # Set up rate limiting
        config.rate_limit_type = RateLimitType.GITHUB_REQUESTS  # Reuse GitHub rate limits
        
        self.token = self.get_credential("access_token")
        self.api_base = config.api_base_url.rstrip("/") + "/api/v1"
    
    def _get_provider_type(self) -> GitProvider:
        return GitProvider.GITEA
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        return {
            "Authorization": f"token {self.token}",
            "Content-Type": "application/json"
        }
    
    async def test_connection(self) -> bool:
        """Test Gitea API connection."""
        try:
            response = await self._make_request(
                "GET",
                f"{self.api_base}/user",
                headers=self._get_headers(),
                identifier="test_connection"
            )
            
            if response.success:
                user_data = response.data
                logger.info(
                    "Gitea connection successful",
                    username=user_data.get("login") if user_data else "unknown",
                    tenant_id=self.config.tenant_id
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error("Gitea connection error", error=str(e))
            return False
    
    def get_webhook_config(self) -> Optional[WebhookConfig]:
        """Get Gitea webhook configuration."""
        webhook_secret = self.get_credential("webhook_secret")
        if not webhook_secret:
            return None
        
        return WebhookConfig(
            endpoint_url=f"{self.config.api_base_url}/webhooks/gitea",
            secret=webhook_secret,
            events=[
                "push",
                "create",
                "delete",
                "issues",
                "issue_comment",
                "pull_request",
                "pull_request_comment"
            ]
        )
    
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Gitea webhook signature."""
        webhook_secret = self.get_credential("webhook_secret")
        if not webhook_secret:
            return False
        
        return self.verify_webhook_signature_hmac(
            payload, signature, webhook_secret, "sha256"
        )
    
    async def list_repositories(
        self, 
        organization: Optional[str] = None,
        limit: int = 100
    ) -> List[Repository]:
        """List accessible repositories."""
        try:
            await self._check_rate_limit("list_repositories")
            
            if organization:
                # List organization repositories
                endpoint = f"{self.api_base}/orgs/{organization}/repos"
            else:
                # List user repositories
                endpoint = f"{self.api_base}/user/repos"
            
            response = await self._make_request(
                "GET",
                endpoint,
                headers=self._get_headers(),
                params={"limit": limit, "sort": "updated", "order": "desc"},
                identifier="list_repositories"
            )
            
            if not response.success or not response.data:
                return []
            
            repositories = []
            
            for repo_data in response.data[:limit]:
                try:
                    repository = Repository(
                        id=str(repo_data["id"]),
                        name=repo_data["name"],
                        full_name=repo_data["full_name"],
                        description=repo_data.get("description", ""),
                        private=repo_data["private"],
                        default_branch=repo_data.get("default_branch", "main"),
                        clone_url=repo_data["clone_url"],
                        ssh_url=repo_data["ssh_url"],
                        web_url=repo_data["html_url"],
                        provider=GitProvider.GITEA,
                        permissions={
                            "read": repo_data.get("permissions", {}).get("pull", True),
                            "write": repo_data.get("permissions", {}).get("push", False),
                            "admin": repo_data.get("permissions", {}).get("admin", False)
                        },
                        language=repo_data.get("language"),
                        size_kb=repo_data.get("size", 0),
                        created_at=repo_data.get("created_at", ""),
                        updated_at=repo_data.get("updated_at", "")
                    )
                    repositories.append(repository)
                    
                except Exception as e:
                    logger.warning(
                        "Failed to process Gitea repository",
                        repo_name=repo_data.get("name", "unknown"),
                        error=str(e)
                    )
                    continue
            
            return repositories
            
        except Exception as e:
            logger.error("Failed to list Gitea repositories", error=str(e))
            return []
    
    async def get_repository(self, repo_id: str) -> Optional[Repository]:
        """Get repository by ID or full name."""
        try:
            await self._check_rate_limit("get_repository")
            
            # Gitea uses owner/repo format for API calls
            if "/" not in repo_id:
                # If just ID is provided, we need to find the full name
                # This is a limitation - Gitea API requires owner/repo format
                logger.warning("Gitea requires owner/repo format", repo_id=repo_id)
                return None
            
            response = await self._make_request(
                "GET",
                f"{self.api_base}/repos/{repo_id}",
                headers=self._get_headers(),
                identifier="get_repository"
            )
            
            if not response.success or not response.data:
                return None
            
            repo_data = response.data
            
            return Repository(
                id=str(repo_data["id"]),
                name=repo_data["name"],
                full_name=repo_data["full_name"],
                description=repo_data.get("description", ""),
                private=repo_data["private"],
                default_branch=repo_data.get("default_branch", "main"),
                clone_url=repo_data["clone_url"],
                ssh_url=repo_data["ssh_url"],
                web_url=repo_data["html_url"],
                provider=GitProvider.GITEA,
                permissions={
                    "read": repo_data.get("permissions", {}).get("pull", True),
                    "write": repo_data.get("permissions", {}).get("push", False),
                    "admin": repo_data.get("permissions", {}).get("admin", False)
                },
                language=repo_data.get("language"),
                size_kb=repo_data.get("size", 0),
                created_at=repo_data.get("created_at", ""),
                updated_at=repo_data.get("updated_at", "")
            )
            
        except Exception as e:
            logger.error("Failed to get Gitea repository", repo_id=repo_id, error=str(e))
            return None
    
    async def get_file_content(
        self, 
        repo_id: str, 
        file_path: str, 
        branch: str = "main"
    ) -> Optional[FileContent]:
        """Get file content from repository."""
        try:
            await self._check_rate_limit("get_file_content")
            
            response = await self._make_request(
                "GET",
                f"{self.api_base}/repos/{repo_id}/contents/{file_path}",
                headers=self._get_headers(),
                params={"ref": branch},
                identifier="get_file_content"
            )
            
            if not response.success or not response.data:
                # Try default branch
                repo = await self.get_repository(repo_id)
                if repo and repo.default_branch != branch:
                    return await self.get_file_content(repo_id, file_path, repo.default_branch)
                return None
            
            file_data = response.data
            
            # Handle directory case
            if file_data.get("type") != "file":
                return None
            
            # Decode content
            if file_data.get("encoding") == "base64":
                content = base64.b64decode(file_data["content"]).decode('utf-8', errors='ignore')
            else:
                content = file_data["content"]
            
            return FileContent(
                path=file_path,
                content=content,
                encoding=file_data.get("encoding", "utf-8"),
                size=file_data.get("size", len(content)),
                sha=file_data.get("sha", ""),
                branch=branch,
                blame_info=None,  # Will be populated if requested
                last_modified=None,
                last_commit=None
            )
            
        except Exception as e:
            logger.error(
                "Failed to get Gitea file content",
                repo_id=repo_id,
                file_path=file_path,
                branch=branch,
                error=str(e)
            )
            return None
    
    async def search_code(
        self, 
        repo_id: str, 
        query: str, 
        file_extension: Optional[str] = None,
        limit: int = 20
    ) -> List[SearchResult]:
        """Search code in repository."""
        try:
            await self._check_rate_limit("search_code")
            
            # Gitea search API
            params = {
                "q": query,
                "limit": min(limit, 50),
                "repo": repo_id
            }
            
            if file_extension:
                params["q"] += f" extension:{file_extension}"
            
            response = await self._make_request(
                "GET",
                f"{self.api_base}/repos/{repo_id}/search",
                headers=self._get_headers(),
                params=params,
                identifier="search_code"
            )
            
            if not response.success or not response.data:
                return []
            
            results = []
            
            for item in response.data.get("data", [])[:limit]:
                try:
                    file_path = item.get("path", "")
                    if not file_path:
                        continue
                    
                    # Get file content to find exact matches
                    file_content = await self.get_file_content(repo_id, file_path)
                    if not file_content:
                        continue
                    
                    lines = file_content.content.split('\n')
                    
                    # Find lines containing the query
                    for line_num, line in enumerate(lines, 1):
                        if query.lower() in line.lower():
                            # Get context lines
                            context_before = lines[max(0, line_num-3):line_num-1]
                            context_after = lines[line_num:min(len(lines), line_num+3)]
                            
                            results.append(SearchResult(
                                file_path=file_path,
                                line_number=line_num,
                                line_content=line.strip(),
                                context_before=context_before,
                                context_after=context_after,
                                score=1.0  # Gitea doesn't provide relevance scores
                            ))
                            
                            if len(results) >= limit:
                                break
                    
                    if len(results) >= limit:
                        break
                        
                except Exception as e:
                    logger.warning(
                        "Failed to process Gitea search result",
                        item=item,
                        error=str(e)
                    )
                    continue
            
            return results
            
        except Exception as e:
            logger.error(
                "Gitea code search failed",
                repo_id=repo_id,
                query=query,
                error=str(e)
            )
            return []
    
    async def get_file_history(
        self, 
        repo_id: str, 
        file_path: str, 
        limit: int = 10
    ) -> List[Dict[str, any]]:
        """Get file commit history."""
        try:
            await self._check_rate_limit("get_file_history")
            
            response = await self._make_request(
                "GET",
                f"{self.api_base}/repos/{repo_id}/commits",
                headers=self._get_headers(),
                params={"path": file_path, "limit": limit},
                identifier="get_file_history"
            )
            
            if not response.success or not response.data:
                return []
            
            history = []
            
            for commit in response.data:
                history.append({
                    "sha": commit["sha"],
                    "message": commit["commit"]["message"],
                    "author": commit["commit"]["author"]["name"],
                    "author_email": commit["commit"]["author"]["email"],
                    "date": commit["commit"]["author"]["date"],
                    "url": commit.get("html_url", ""),
                    "stats": {}  # Gitea doesn't provide stats in commit list
                })
            
            return history
            
        except Exception as e:
            logger.error(
                "Failed to get Gitea file history",
                repo_id=repo_id,
                file_path=file_path,
                error=str(e)
            )
            return []
    
    async def get_blame_info(
        self, 
        repo_id: str, 
        file_path: str, 
        branch: str = "main"
    ) -> List[GitBlameInfo]:
        """Get blame information for a file."""
        try:
            await self._check_rate_limit("get_blame_info")
            
            # Gitea doesn't have a direct blame API
            # We'll approximate by getting recent commits for the file
            commits = await self.get_file_history(repo_id, file_path, 10)
            
            blame_info = []
            for i, commit in enumerate(commits):
                blame_info.append(GitBlameInfo(
                    line_number=i + 1,  # Approximate
                    commit_sha=commit["sha"],
                    author=commit["author"],
                    author_email=commit["author_email"],
                    timestamp=commit["date"],
                    message=commit["message"].split('\n')[0]  # First line only
                ))
            
            return blame_info
            
        except Exception as e:
            logger.error(
                "Failed to get Gitea blame info",
                repo_id=repo_id,
                file_path=file_path,
                error=str(e)
            )
            return []
    
    async def get_recent_commits(
        self, 
        repo_id: str, 
        file_path: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, any]]:
        """Get recent commits from repository."""
        try:
            await self._check_rate_limit("get_recent_commits")
            
            params = {"limit": limit}
            if file_path:
                params["path"] = file_path
            if author:
                params["author"] = author
            if since:
                params["since"] = since
            
            response = await self._make_request(
                "GET",
                f"{self.api_base}/repos/{repo_id}/commits",
                headers=self._get_headers(),
                params=params,
                identifier="get_recent_commits"
            )
            
            if not response.success or not response.data:
                return []
            
            results = []
            
            for commit in response.data:
                # Extract issue references
                message = commit["commit"]["message"]
                issue_refs = self.extract_issue_references(message)
                
                results.append({
                    "sha": commit["sha"],
                    "message": message,
                    "author": commit["commit"]["author"]["name"],
                    "author_email": commit["commit"]["author"]["email"],
                    "committer": commit["commit"]["committer"]["name"],
                    "date": commit["commit"]["author"]["date"],
                    "url": commit.get("html_url", ""),
                    "issue_references": issue_refs,
                    "stats": {},  # Would require additional API call
                    "files_changed": []  # Would require additional API call
                })
            
            return results
            
        except Exception as e:
            logger.error(
                "Failed to get Gitea recent commits",
                repo_id=repo_id,
                error=str(e)
            )
            return []