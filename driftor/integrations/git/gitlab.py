"""
GitLab integration supporting both GitLab.com and self-hosted instances.
"""
import base64
from typing import Dict, List, Optional
import gitlab
from gitlab.exceptions import GitlabError, GitlabGetError
import structlog

from .base import BaseGitProvider, Repository, FileContent, SearchResult, GitBlameInfo, GitProvider
from driftor.integrations.base import IntegrationConfig, WebhookConfig
from driftor.core.rate_limiter import RateLimitType

logger = structlog.get_logger(__name__)


class GitLabProvider(BaseGitProvider):
    """GitLab integration supporting Cloud and self-hosted instances."""
    
    def __init__(self, config: IntegrationConfig, credentials: Dict[str, str]):
        super().__init__(config, credentials)
        
        # Set up rate limiting
        config.rate_limit_type = RateLimitType.GITHUB_REQUESTS  # Reuse GitHub rate limits
        
        self.token = self.get_credential("access_token")
        self.gitlab_client = self._create_gitlab_client()
    
    def _get_provider_type(self) -> GitProvider:
        return GitProvider.GITLAB
    
    def _create_gitlab_client(self) -> gitlab.Gitlab:
        """Create authenticated GitLab client."""
        if not self.token:
            raise ValueError("GitLab access token is required")
        
        # Support self-hosted GitLab instances
        gitlab_url = self.config.api_base_url
        if not gitlab_url or gitlab_url == "https://gitlab.com":
            gitlab_url = "https://gitlab.com"
        
        return gitlab.Gitlab(gitlab_url, private_token=self.token)
    
    async def test_connection(self) -> bool:
        """Test GitLab API connection."""
        try:
            user = self.gitlab_client.auth()
            logger.info(
                "GitLab connection successful",
                user_id=user.get("id"),
                tenant_id=self.config.tenant_id
            )
            return True
            
        except GitlabError as e:
            logger.error(
                "GitLab connection failed",
                error=str(e),
                tenant_id=self.config.tenant_id
            )
            return False
        except Exception as e:
            logger.error("GitLab connection error", error=str(e))
            return False
    
    def get_webhook_config(self) -> Optional[WebhookConfig]:
        """Get GitLab webhook configuration."""
        webhook_secret = self.get_credential("webhook_secret")
        if not webhook_secret:
            return None
        
        return WebhookConfig(
            endpoint_url=f"{self.config.api_base_url}/webhooks/gitlab",
            secret=webhook_secret,
            events=[
                "push_events",
                "merge_requests_events",
                "issues_events",
                "note_events",
                "pipeline_events"
            ]
        )
    
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitLab webhook signature."""
        webhook_secret = self.get_credential("webhook_secret")
        if not webhook_secret:
            return False
        
        # GitLab uses X-Gitlab-Token header for verification
        return signature == webhook_secret
    
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
                # List group/organization projects
                try:
                    group = self.gitlab_client.groups.get(organization)
                    projects = group.projects.list(all=True, per_page=min(limit, 100))
                except GitlabGetError:
                    return []
            else:
                # List user's projects
                projects = self.gitlab_client.projects.list(
                    owned=True, 
                    membership=True,
                    per_page=min(limit, 100),
                    order_by="last_activity_at",
                    sort="desc"
                )
            
            for project in projects[:limit]:
                try:
                    # Get detailed project info
                    detailed_project = self.gitlab_client.projects.get(project.id)
                    
                    repository = Repository(
                        id=str(detailed_project.id),
                        name=detailed_project.name,
                        full_name=detailed_project.path_with_namespace,
                        description=detailed_project.description,
                        private=detailed_project.visibility == "private",
                        default_branch=detailed_project.default_branch or "main",
                        clone_url=detailed_project.http_url_to_repo,
                        ssh_url=detailed_project.ssh_url_to_repo,
                        web_url=detailed_project.web_url,
                        provider=GitProvider.GITLAB,
                        permissions={
                            "read": True,  # If we can see it, we can read it
                            "write": detailed_project.permissions.get("project_access", {}).get("access_level", 0) >= 30,
                            "admin": detailed_project.permissions.get("project_access", {}).get("access_level", 0) >= 40
                        },
                        language=getattr(detailed_project, 'language', None),
                        size_kb=getattr(detailed_project, 'statistics', {}).get('repository_size', 0) // 1024,
                        created_at=detailed_project.created_at,
                        updated_at=detailed_project.last_activity_at
                    )
                    repositories.append(repository)
                    
                except Exception as e:
                    logger.warning(
                        "Failed to process GitLab project",
                        project_id=project.id,
                        error=str(e)
                    )
                    continue
            
            return repositories
            
        except Exception as e:
            logger.error("Failed to list GitLab repositories", error=str(e))
            return []
    
    async def get_repository(self, repo_id: str) -> Optional[Repository]:
        """Get repository by ID or path."""
        try:
            await self._check_rate_limit("get_repository")
            
            try:
                project = self.gitlab_client.projects.get(repo_id)
            except GitlabGetError:
                return None
            
            return Repository(
                id=str(project.id),
                name=project.name,
                full_name=project.path_with_namespace,
                description=project.description,
                private=project.visibility == "private",
                default_branch=project.default_branch or "main",
                clone_url=project.http_url_to_repo,
                ssh_url=project.ssh_url_to_repo,
                web_url=project.web_url,
                provider=GitProvider.GITLAB,
                permissions={
                    "read": True,
                    "write": project.permissions.get("project_access", {}).get("access_level", 0) >= 30,
                    "admin": project.permissions.get("project_access", {}).get("access_level", 0) >= 40
                },
                language=getattr(project, 'language', None),
                size_kb=getattr(project, 'statistics', {}).get('repository_size', 0) // 1024,
                created_at=project.created_at,
                updated_at=project.last_activity_at
            )
            
        except Exception as e:
            logger.error("Failed to get GitLab repository", repo_id=repo_id, error=str(e))
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
            
            project = self.gitlab_client.projects.get(repo_id)
            
            try:
                # Get file from specified branch
                file_content = project.files.get(file_path=file_path, ref=branch)
            except GitlabGetError:
                # Try default branch
                try:
                    default_branch = project.default_branch or "main"
                    file_content = project.files.get(file_path=file_path, ref=default_branch)
                    branch = default_branch
                except GitlabGetError:
                    return None
            
            # Decode content
            if file_content.encoding == "base64":
                content = base64.b64decode(file_content.content).decode('utf-8', errors='ignore')
            else:
                content = file_content.content
            
            # Get blame information
            blame_info = await self._get_blame_for_file(project, file_path, branch)
            
            return FileContent(
                path=file_path,
                content=content,
                encoding=file_content.encoding,
                size=file_content.size,
                sha=file_content.blob_id,
                branch=branch,
                blame_info=blame_info,
                last_modified=file_content.last_commit_id,
                last_commit=None
            )
            
        except Exception as e:
            logger.error(
                "Failed to get GitLab file content",
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
            
            project = self.gitlab_client.projects.get(repo_id)
            
            # GitLab search API parameters
            search_params = {
                "scope": "blobs",
                "search": query,
                "per_page": min(limit, 100)
            }
            
            if file_extension:
                search_params["search"] += f" extension:{file_extension}"
            
            # Perform search
            search_results = project.search("blobs", query, per_page=min(limit, 100))
            
            results = []
            
            for item in search_results[:limit]:
                try:
                    # Get file content to find exact line numbers
                    file_content = await self.get_file_content(
                        repo_id, 
                        item["path"],
                        item.get("ref", project.default_branch)
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
                                file_path=item["path"],
                                line_number=line_num,
                                line_content=line.strip(),
                                context_before=context_before,
                                context_after=context_after,
                                score=1.0  # GitLab doesn't provide relevance scores
                            ))
                            
                            if len(results) >= limit:
                                break
                    
                    if len(results) >= limit:
                        break
                        
                except Exception as e:
                    logger.warning(
                        "Failed to process GitLab search result",
                        file_path=item.get("path"),
                        error=str(e)
                    )
                    continue
            
            return results
            
        except Exception as e:
            logger.error(
                "GitLab code search failed",
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
            
            project = self.gitlab_client.projects.get(repo_id)
            commits = project.commits.list(path=file_path, per_page=limit)
            
            history = []
            
            for commit in commits:
                history.append({
                    "sha": commit.id,
                    "message": commit.message,
                    "author": commit.author_name,
                    "author_email": commit.author_email,
                    "date": commit.created_at,
                    "url": commit.web_url,
                    "stats": commit.stats if hasattr(commit, 'stats') else {}
                })
            
            return history
            
        except Exception as e:
            logger.error(
                "Failed to get GitLab file history",
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
            
            project = self.gitlab_client.projects.get(repo_id)
            return await self._get_blame_for_file(project, file_path, branch)
            
        except Exception as e:
            logger.error(
                "Failed to get GitLab blame info",
                repo_id=repo_id,
                file_path=file_path,
                error=str(e)
            )
            return []
    
    async def _get_blame_for_file(
        self, 
        project, 
        file_path: str, 
        branch: str
    ) -> List[GitBlameInfo]:
        """Get blame information using GitLab API."""
        try:
            # Get file blame
            blame_data = project.files.blame(file_path=file_path, ref=branch)
            
            blame_info = []
            for i, blame_item in enumerate(blame_data):
                blame_info.append(GitBlameInfo(
                    line_number=i + 1,
                    commit_sha=blame_item["commit"]["id"],
                    author=blame_item["commit"]["author_name"],
                    author_email=blame_item["commit"]["author_email"],
                    timestamp=blame_item["commit"]["created_at"],
                    message=blame_item["commit"]["message"].split('\n')[0]
                ))
            
            return blame_info
            
        except Exception as e:
            logger.warning("Failed to get GitLab blame info", error=str(e))
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
            
            project = self.gitlab_client.projects.get(repo_id)
            
            kwargs = {"per_page": limit}
            if file_path:
                kwargs["path"] = file_path
            if author:
                kwargs["author"] = author
            if since:
                kwargs["since"] = since
            
            commits = project.commits.list(**kwargs)
            
            results = []
            
            for commit in commits:
                # Extract issue references
                issue_refs = self.extract_issue_references(commit.message)
                
                results.append({
                    "sha": commit.id,
                    "message": commit.message,
                    "author": commit.author_name,
                    "author_email": commit.author_email,
                    "committer": commit.committer_name,
                    "date": commit.created_at,
                    "url": commit.web_url,
                    "issue_references": issue_refs,
                    "stats": getattr(commit, 'stats', {}),
                    "files_changed": []  # Would require additional API call
                })
            
            return results
            
        except Exception as e:
            logger.error(
                "Failed to get GitLab recent commits",
                repo_id=repo_id,
                error=str(e)
            )
            return []