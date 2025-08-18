"""
GitHub integration with enterprise security and private repository support.
"""
import base64
from typing import Dict, List, Optional
from github import Github, Auth, GithubException
import httpx
import structlog

from .base import BaseGitProvider, Repository, FileContent, SearchResult, GitBlameInfo, GitProvider
from driftor.integrations.base import IntegrationConfig, APIResponse, WebhookConfig
from driftor.core.rate_limiter import RateLimitType
from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class GitHubProvider(BaseGitProvider):
    """GitHub integration supporting both Cloud and Enterprise Server."""
    
    def __init__(self, config: IntegrationConfig, credentials: Dict[str, str]):
        super().__init__(config, credentials)
        
        # Set up rate limiting
        config.rate_limit_type = RateLimitType.GITHUB_REQUESTS
        
        self.token = self.get_credential("access_token")
        self.github_client = self._create_github_client()
    
    def _get_provider_type(self) -> GitProvider:
        return GitProvider.GITHUB
    
    def _create_github_client(self) -> Github:
        """Create authenticated GitHub client."""
        if not self.token:
            raise ValueError("GitHub access token is required")
        
        auth = Auth.Token(self.token)
        
        # Support GitHub Enterprise Server
        base_url = self.config.api_base_url
        if base_url and base_url != "https://api.github.com":
            return Github(auth=auth, base_url=base_url, per_page=100)
        else:
            return Github(auth=auth, per_page=100)
    
    async def test_connection(self) -> bool:
        """Test GitHub API connection."""
        try:
            user = self.github_client.get_user()
            logger.info(
                "GitHub connection successful",
                user=user.login,
                tenant_id=self.config.tenant_id
            )
            return True
            
        except GithubException as e:
            logger.error(
                "GitHub connection failed",
                error=str(e),
                status_code=e.status,
                tenant_id=self.config.tenant_id
            )
            return False
        except Exception as e:
            logger.error("GitHub connection error", error=str(e))
            return False
    
    def get_webhook_config(self) -> Optional[WebhookConfig]:
        """Get GitHub webhook configuration."""
        webhook_secret = self.get_credential("webhook_secret")
        if not webhook_secret:
            return None
        
        return WebhookConfig(
            endpoint_url=f"{self.config.api_base_url}/webhooks/github",
            secret=webhook_secret,
            events=[
                "push",
                "pull_request",
                "issues",
                "issue_comment",
                "commit_comment"
            ]
        )
    
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature."""
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
            
            repositories = []
            
            if organization:
                # List organization repositories
                org = self.github_client.get_organization(organization)
                repos = org.get_repos(type="all", sort="updated")
            else:
                # List user repositories
                repos = self.github_client.get_user().get_repos(
                    type="all", 
                    sort="updated"
                )
            
            count = 0
            for repo in repos:
                if count >= limit:
                    break
                
                try:
                    repository = Repository(
                        id=str(repo.id),
                        name=repo.name,
                        full_name=repo.full_name,
                        description=repo.description,
                        private=repo.private,
                        default_branch=repo.default_branch or "main",
                        clone_url=repo.clone_url,
                        ssh_url=repo.ssh_url,
                        web_url=repo.html_url,
                        provider=GitProvider.GITHUB,
                        permissions={
                            "read": repo.permissions.pull if repo.permissions else True,
                            "write": repo.permissions.push if repo.permissions else False,
                            "admin": repo.permissions.admin if repo.permissions else False
                        },
                        language=repo.language,
                        size_kb=repo.size,
                        created_at=repo.created_at.isoformat() if repo.created_at else "",
                        updated_at=repo.updated_at.isoformat() if repo.updated_at else ""
                    )
                    repositories.append(repository)
                    count += 1
                    
                except Exception as e:
                    logger.warning(
                        "Failed to process repository",
                        repo_name=repo.name if hasattr(repo, 'name') else 'unknown',
                        error=str(e)
                    )
                    continue
            
            return repositories
            
        except Exception as e:
            logger.error("Failed to list repositories", error=str(e))
            return []
    
    async def get_repository(self, repo_id: str) -> Optional[Repository]:
        """Get repository by ID or full name."""
        try:
            await self._check_rate_limit("get_repository")
            
            # Try by ID first, then by full name
            try:
                if repo_id.isdigit():
                    repo = self.github_client.get_repo(int(repo_id))
                else:
                    repo = self.github_client.get_repo(repo_id)
            except GithubException:
                return None
            
            return Repository(
                id=str(repo.id),
                name=repo.name,
                full_name=repo.full_name,
                description=repo.description,
                private=repo.private,
                default_branch=repo.default_branch or "main",
                clone_url=repo.clone_url,
                ssh_url=repo.ssh_url,
                web_url=repo.html_url,
                provider=GitProvider.GITHUB,
                permissions={
                    "read": repo.permissions.pull if repo.permissions else True,
                    "write": repo.permissions.push if repo.permissions else False,
                    "admin": repo.permissions.admin if repo.permissions else False
                },
                language=repo.language,
                size_kb=repo.size,
                created_at=repo.created_at.isoformat() if repo.created_at else "",
                updated_at=repo.updated_at.isoformat() if repo.updated_at else ""
            )
            
        except Exception as e:
            logger.error("Failed to get repository", repo_id=repo_id, error=str(e))
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
            
            repo = self.github_client.get_repo(repo_id)
            
            try:
                # Try specified branch first
                file_content = repo.get_contents(file_path, ref=branch)
            except GithubException:
                # Try default branch
                try:
                    file_content = repo.get_contents(file_path, ref=repo.default_branch)
                    branch = repo.default_branch
                except GithubException:
                    return None
            
            if file_content.type != "file":
                return None
            
            # Decode content
            if file_content.encoding == "base64":
                content = base64.b64decode(file_content.content).decode('utf-8', errors='ignore')
            else:
                content = file_content.content
            
            # Get blame information
            blame_info = await self._get_blame_for_file(repo, file_path, branch)
            
            return FileContent(
                path=file_path,
                content=content,
                encoding=file_content.encoding,
                size=file_content.size,
                sha=file_content.sha,
                branch=branch,
                blame_info=blame_info,
                last_modified=None,  # GitHub doesn't provide this directly
                last_commit=None     # Would require additional API call
            )
            
        except Exception as e:
            logger.error(
                "Failed to get file content",
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
            
            # Build search query
            search_query = f"{query} repo:{repo_id}"
            if file_extension:
                search_query += f" extension:{file_extension}"
            
            # Use GitHub search API
            search_results = self.github_client.search_code(
                query=search_query,
                sort="indexed",
                order="desc"
            )
            
            results = []
            count = 0
            
            for item in search_results:
                if count >= limit:
                    break
                
                try:
                    # Get file content to find exact matches
                    file_content = await self.get_file_content(
                        repo_id, 
                        item.path, 
                        item.repository.default_branch
                    )
                    
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
                                file_path=item.path,
                                line_number=line_num,
                                line_content=line.strip(),
                                context_before=context_before,
                                context_after=context_after,
                                score=item.score if hasattr(item, 'score') else 1.0
                            ))
                            count += 1
                            
                            if count >= limit:
                                break
                    
                    if count >= limit:
                        break
                        
                except Exception as e:
                    logger.warning(
                        "Failed to process search result",
                        file_path=item.path,
                        error=str(e)
                    )
                    continue
            
            return results
            
        except Exception as e:
            logger.error(
                "Code search failed",
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
            
            repo = self.github_client.get_repo(repo_id)
            commits = repo.get_commits(path=file_path)
            
            history = []
            count = 0
            
            for commit in commits:
                if count >= limit:
                    break
                
                history.append({
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": commit.commit.author.name,
                    "author_email": commit.commit.author.email,
                    "date": commit.commit.author.date.isoformat(),
                    "url": commit.html_url,
                    "stats": {
                        "additions": commit.stats.additions if commit.stats else 0,
                        "deletions": commit.stats.deletions if commit.stats else 0,
                        "total": commit.stats.total if commit.stats else 0
                    }
                })
                count += 1
            
            return history
            
        except Exception as e:
            logger.error(
                "Failed to get file history",
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
            
            repo = self.github_client.get_repo(repo_id)
            return await self._get_blame_for_file(repo, file_path, branch)
            
        except Exception as e:
            logger.error(
                "Failed to get blame info",
                repo_id=repo_id,
                file_path=file_path,
                error=str(e)
            )
            return []
    
    async def _get_blame_for_file(
        self, 
        repo, 
        file_path: str, 
        branch: str
    ) -> List[GitBlameInfo]:
        """Get blame information using GitHub API."""
        try:
            # GitHub doesn't have a direct blame API, so we approximate
            # by getting recent commits for the file
            commits = repo.get_commits(path=file_path, sha=branch)
            
            blame_info = []
            for i, commit in enumerate(commits):
                if i >= 10:  # Limit to recent commits
                    break
                
                blame_info.append(GitBlameInfo(
                    line_number=i + 1,  # Approximate
                    commit_sha=commit.sha,
                    author=commit.commit.author.name,
                    author_email=commit.commit.author.email,
                    timestamp=commit.commit.author.date.isoformat(),
                    message=commit.commit.message.split('\n')[0]  # First line only
                ))
            
            return blame_info
            
        except Exception as e:
            logger.warning("Failed to get blame info", error=str(e))
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
            
            repo = self.github_client.get_repo(repo_id)
            
            kwargs = {}
            if file_path:
                kwargs["path"] = file_path
            if author:
                kwargs["author"] = author
            if since:
                kwargs["since"] = since
            
            commits = repo.get_commits(**kwargs)
            
            results = []
            count = 0
            
            for commit in commits:
                if count >= limit:
                    break
                
                # Extract issue references
                issue_refs = self.extract_issue_references(commit.commit.message)
                
                results.append({
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": commit.commit.author.name,
                    "author_email": commit.commit.author.email,
                    "committer": commit.commit.committer.name,
                    "date": commit.commit.author.date.isoformat(),
                    "url": commit.html_url,
                    "issue_references": issue_refs,
                    "stats": {
                        "additions": commit.stats.additions if commit.stats else 0,
                        "deletions": commit.stats.deletions if commit.stats else 0,
                        "total": commit.stats.total if commit.stats else 0
                    },
                    "files_changed": [f.filename for f in commit.files] if commit.files else []
                })
                count += 1
            
            return results
            
        except Exception as e:
            logger.error(
                "Failed to get recent commits",
                repo_id=repo_id,
                error=str(e)
            )
            return []