"""
Jira integration supporting Cloud, Server, and Data Center with enterprise security.
"""
import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Union
from atlassian import Jira
from atlassian.jira import JiraError
import httpx
import structlog

from driftor.integrations.base import BaseIntegration, IntegrationConfig, APIResponse, WebhookConfig
from driftor.core.rate_limiter import RateLimitType
from driftor.security.audit import audit, AuditEventType, AuditSeverity

logger = structlog.get_logger(__name__)


class JiraDeploymentType(str, Enum):
    """Jira deployment types."""
    CLOUD = "cloud"
    SERVER = "server"
    DATA_CENTER = "datacenter"


class JiraIssueType(str, Enum):
    """Common Jira issue types."""
    BUG = "Bug"
    TASK = "Task"
    STORY = "Story"
    EPIC = "Epic"
    SUB_TASK = "Sub-task"


class JiraIssuePriority(str, Enum):
    """Jira issue priorities."""
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"


class JiraIssueStatus(str, Enum):
    """Common Jira issue statuses."""
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"
    TO_DO = "To Do"
    DONE = "Done"


class JiraClient(BaseIntegration):
    """Enterprise Jira integration supporting all deployment types."""
    
    def __init__(self, config: IntegrationConfig, credentials: Dict[str, str]):
        super().__init__(config, credentials)
        
        # Set up rate limiting
        config.rate_limit_type = RateLimitType.JIRA_REQUESTS
        
        self.deployment_type = self._detect_deployment_type()
        self.jira_client = self._create_jira_client()
    
    def _detect_deployment_type(self) -> JiraDeploymentType:
        """Detect Jira deployment type from base URL."""
        base_url = self.config.api_base_url.lower()
        
        if "atlassian.net" in base_url:
            return JiraDeploymentType.CLOUD
        elif "jira" in base_url:
            # Could be Server or Data Center - we'll determine later
            return JiraDeploymentType.SERVER
        else:
            return JiraDeploymentType.SERVER
    
    def _create_jira_client(self) -> Jira:
        """Create authenticated Jira client."""
        username = self.get_credential("username")
        password = self.get_credential("password")  # API token for Cloud
        token = self.get_credential("api_token")
        
        if self.deployment_type == JiraDeploymentType.CLOUD:
            # Jira Cloud uses email + API token
            if not username or not (password or token):
                raise ValueError("Jira Cloud requires username and API token")
            
            return Jira(
                url=self.config.api_base_url,
                username=username,
                password=token or password,
                cloud=True
            )
        else:
            # Jira Server/Data Center
            if token:
                # Personal Access Token (PAT) for newer versions
                return Jira(
                    url=self.config.api_base_url,
                    token=token
                )
            elif username and password:
                # Basic auth for older versions
                return Jira(
                    url=self.config.api_base_url,
                    username=username,
                    password=password
                )
            else:
                raise ValueError("Jira Server requires username/password or API token")
    
    async def test_connection(self) -> bool:
        """Test Jira API connection."""
        try:
            # Get current user info
            response = await self._make_request(
                "GET",
                f"{self.config.api_base_url}/rest/api/2/myself",
                identifier="test_connection"
            )
            
            if response.success:
                user_data = response.data
                logger.info(
                    "Jira connection successful",
                    user=user_data.get("displayName") if user_data else "unknown",
                    deployment_type=self.deployment_type.value,
                    tenant_id=self.config.tenant_id
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(
                "Jira connection failed",
                error=str(e),
                deployment_type=self.deployment_type.value,
                tenant_id=self.config.tenant_id
            )
            return False
    
    def get_webhook_config(self) -> Optional[WebhookConfig]:
        """Get Jira webhook configuration."""
        webhook_secret = self.get_credential("webhook_secret")
        if not webhook_secret:
            return None
        
        return WebhookConfig(
            endpoint_url=f"{self.config.api_base_url}/webhooks/jira",
            secret=webhook_secret,
            events=[
                "jira:issue_created",
                "jira:issue_updated",
                "jira:issue_deleted",
                "comment_created",
                "comment_updated",
                "comment_deleted",
                "worklog_created",
                "worklog_updated",
                "worklog_deleted"
            ]
        )
    
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Jira webhook signature."""
        webhook_secret = self.get_credential("webhook_secret")
        if not webhook_secret:
            return False
        
        # Jira doesn't use HMAC signatures by default
        # Instead, it uses the webhook secret as a query parameter
        # For security, we implement HMAC verification
        return self.verify_webhook_signature_hmac(
            payload, signature, webhook_secret, "sha256"
        )
    
    async def get_issue(self, issue_key: str) -> Optional[Dict[str, any]]:
        """Get issue details by key."""
        try:
            await self._check_rate_limit("get_issue")
            
            response = await self._make_request(
                "GET",
                f"{self.config.api_base_url}/rest/api/2/issue/{issue_key}",
                identifier="get_issue"
            )
            
            if response.success and response.data:
                return self._normalize_issue_data(response.data)
            
            return None
            
        except Exception as e:
            logger.error(
                "Failed to get Jira issue",
                issue_key=issue_key,
                error=str(e)
            )
            return None
    
    async def search_issues(
        self,
        jql: str,
        fields: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict[str, any]]:
        """Search issues using JQL."""
        try:
            await self._check_rate_limit("search_issues")
            
            params = {
                "jql": jql,
                "maxResults": min(limit, 100),
                "startAt": 0
            }
            
            if fields:
                params["fields"] = ",".join(fields)
            
            response = await self._make_request(
                "POST",
                f"{self.config.api_base_url}/rest/api/2/search",
                json_data=params,
                identifier="search_issues"
            )
            
            if response.success and response.data:
                issues = response.data.get("issues", [])
                return [self._normalize_issue_data(issue) for issue in issues]
            
            return []
            
        except Exception as e:
            logger.error(
                "Failed to search Jira issues",
                jql=jql,
                error=str(e)
            )
            return []
    
    async def find_similar_issues(
        self,
        summary: str,
        description: str,
        project_key: Optional[str] = None,
        issue_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, any]]:
        """Find similar issues based on summary and description."""
        try:
            # Build JQL query for similar issues
            search_terms = []
            
            # Extract key terms from summary and description
            key_words = self._extract_keywords(f"{summary} {description}")
            
            if key_words:
                # Search in summary and description
                text_search = " OR ".join([f'text ~ "{word}"' for word in key_words[:5]])
                search_terms.append(f"({text_search})")
            
            if project_key:
                search_terms.append(f"project = {project_key}")
            
            if issue_type:
                search_terms.append(f'issuetype = "{issue_type}"')
            
            # Exclude resolved/closed issues for better relevance
            search_terms.append("status not in (Resolved, Closed, Done)")
            
            # Order by most recently updated
            jql = " AND ".join(search_terms) + " ORDER BY updated DESC"
            
            logger.info(
                "Searching for similar issues",
                jql=jql,
                tenant_id=self.config.tenant_id
            )
            
            return await self.search_issues(jql, limit=limit)
            
        except Exception as e:
            logger.error(
                "Failed to find similar issues",
                summary=summary[:100],
                error=str(e)
            )
            return []
    
    async def get_issue_comments(self, issue_key: str) -> List[Dict[str, any]]:
        """Get comments for an issue."""
        try:
            await self._check_rate_limit("get_issue_comments")
            
            response = await self._make_request(
                "GET",
                f"{self.config.api_base_url}/rest/api/2/issue/{issue_key}/comment",
                identifier="get_issue_comments"
            )
            
            if response.success and response.data:
                comments = response.data.get("comments", [])
                return [self._normalize_comment_data(comment) for comment in comments]
            
            return []
            
        except Exception as e:
            logger.error(
                "Failed to get issue comments",
                issue_key=issue_key,
                error=str(e)
            )
            return []
    
    async def get_issue_history(self, issue_key: str) -> List[Dict[str, any]]:
        """Get change history for an issue."""
        try:
            await self._check_rate_limit("get_issue_history")
            
            response = await self._make_request(
                "GET",
                f"{self.config.api_base_url}/rest/api/2/issue/{issue_key}",
                params={"expand": "changelog"},
                identifier="get_issue_history"
            )
            
            if response.success and response.data:
                changelog = response.data.get("changelog", {})
                histories = changelog.get("histories", [])
                
                return [self._normalize_history_data(history) for history in histories]
            
            return []
            
        except Exception as e:
            logger.error(
                "Failed to get issue history",
                issue_key=issue_key,
                error=str(e)
            )
            return []
    
    async def add_comment(
        self, 
        issue_key: str, 
        comment_body: str,
        visibility: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """Add comment to an issue."""
        try:
            await self._check_rate_limit("add_comment")
            
            comment_data = {"body": comment_body}
            if visibility:
                comment_data["visibility"] = visibility
            
            response = await self._make_request(
                "POST",
                f"{self.config.api_base_url}/rest/api/2/issue/{issue_key}/comment",
                json_data=comment_data,
                identifier="add_comment"
            )
            
            if response.success and response.data:
                comment_id = response.data.get("id")
                
                # Audit comment creation
                await audit(
                    event_type=AuditEventType.DATA_CREATED,
                    tenant_id=self.config.tenant_id,
                    resource_type="jira_comment",
                    resource_id=comment_id,
                    action="ADD_COMMENT",
                    details={
                        "issue_key": issue_key,
                        "comment_length": len(comment_body)
                    }
                )
                
                return comment_id
            
            return None
            
        except Exception as e:
            logger.error(
                "Failed to add comment",
                issue_key=issue_key,
                error=str(e)
            )
            return None
    
    async def transition_issue(
        self, 
        issue_key: str, 
        transition_id: str,
        fields: Optional[Dict[str, any]] = None,
        comment: Optional[str] = None
    ) -> bool:
        """Transition an issue to a new status."""
        try:
            await self._check_rate_limit("transition_issue")
            
            transition_data = {
                "transition": {"id": transition_id}
            }
            
            if fields:
                transition_data["fields"] = fields
            
            if comment:
                transition_data["update"] = {
                    "comment": [{"add": {"body": comment}}]
                }
            
            response = await self._make_request(
                "POST",
                f"{self.config.api_base_url}/rest/api/2/issue/{issue_key}/transitions",
                json_data=transition_data,
                identifier="transition_issue"
            )
            
            success = response.success
            
            if success:
                # Audit transition
                await audit(
                    event_type=AuditEventType.DATA_UPDATED,
                    tenant_id=self.config.tenant_id,
                    resource_type="jira_issue",
                    resource_id=issue_key,
                    action="TRANSITION_ISSUE",
                    details={
                        "transition_id": transition_id,
                        "has_comment": bool(comment)
                    }
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to transition issue",
                issue_key=issue_key,
                transition_id=transition_id,
                error=str(e)
            )
            return False
    
    async def get_projects(self) -> List[Dict[str, any]]:
        """Get accessible projects."""
        try:
            await self._check_rate_limit("get_projects")
            
            response = await self._make_request(
                "GET",
                f"{self.config.api_base_url}/rest/api/2/project",
                identifier="get_projects"
            )
            
            if response.success and response.data:
                return [self._normalize_project_data(project) for project in response.data]
            
            return []
            
        except Exception as e:
            logger.error("Failed to get projects", error=str(e))
            return []
    
    def _normalize_issue_data(self, issue_data: Dict[str, any]) -> Dict[str, any]:
        """Normalize issue data to a consistent format."""
        fields = issue_data.get("fields", {})
        
        return {
            "id": issue_data.get("id"),
            "key": issue_data.get("key"),
            "self": issue_data.get("self"),
            "url": f"{self.config.api_base_url}/browse/{issue_data.get('key')}",
            
            # Basic fields
            "summary": fields.get("summary", ""),
            "description": fields.get("description", ""),
            "issue_type": fields.get("issuetype", {}).get("name", ""),
            "priority": fields.get("priority", {}).get("name", ""),
            "status": fields.get("status", {}).get("name", ""),
            
            # People
            "assignee": self._normalize_user_data(fields.get("assignee")),
            "reporter": self._normalize_user_data(fields.get("reporter")),
            "creator": self._normalize_user_data(fields.get("creator")),
            
            # Project
            "project": {
                "key": fields.get("project", {}).get("key", ""),
                "name": fields.get("project", {}).get("name", ""),
                "id": fields.get("project", {}).get("id", "")
            },
            
            # Dates
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "resolved": fields.get("resolutiondate"),
            
            # Additional fields
            "labels": fields.get("labels", []),
            "components": [comp.get("name", "") for comp in fields.get("components", [])],
            "versions": [ver.get("name", "") for ver in fields.get("versions", [])],
            "fix_versions": [ver.get("name", "") for ver in fields.get("fixVersions", [])],
            
            # Raw data for advanced processing
            "raw_fields": fields
        }
    
    def _normalize_user_data(self, user_data: Optional[Dict[str, any]]) -> Optional[Dict[str, any]]:
        """Normalize user data."""
        if not user_data:
            return None
        
        return {
            "account_id": user_data.get("accountId"),  # Cloud
            "name": user_data.get("name"),  # Server
            "display_name": user_data.get("displayName", ""),
            "email": user_data.get("emailAddress", ""),
            "active": user_data.get("active", True)
        }
    
    def _normalize_comment_data(self, comment_data: Dict[str, any]) -> Dict[str, any]:
        """Normalize comment data."""
        return {
            "id": comment_data.get("id"),
            "body": comment_data.get("body", ""),
            "author": self._normalize_user_data(comment_data.get("author")),
            "created": comment_data.get("created"),
            "updated": comment_data.get("updated"),
            "visibility": comment_data.get("visibility")
        }
    
    def _normalize_history_data(self, history_data: Dict[str, any]) -> Dict[str, any]:
        """Normalize history/changelog data."""
        return {
            "id": history_data.get("id"),
            "author": self._normalize_user_data(history_data.get("author")),
            "created": history_data.get("created"),
            "items": [
                {
                    "field": item.get("field"),
                    "field_type": item.get("fieldtype"),
                    "from": item.get("fromString"),
                    "to": item.get("toString")
                }
                for item in history_data.get("items", [])
            ]
        }
    
    def _normalize_project_data(self, project_data: Dict[str, any]) -> Dict[str, any]:
        """Normalize project data."""
        return {
            "id": project_data.get("id"),
            "key": project_data.get("key"),
            "name": project_data.get("name", ""),
            "description": project_data.get("description", ""),
            "project_type": project_data.get("projectTypeKey", ""),
            "lead": self._normalize_user_data(project_data.get("lead")),
            "url": project_data.get("self", "")
        }
    
    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract key terms from text for similarity search."""
        # Simple keyword extraction - in production, use more sophisticated NLP
        import re
        
        # Remove special characters and split
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Common stop words to exclude
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'this', 'that', 'these', 'those', 'are',
            'was', 'were', 'been', 'have', 'has', 'had', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'issue', 'bug', 'problem'
        }
        
        # Filter and count
        word_counts = {}
        for word in words:
            if word not in stop_words and len(word) > 2:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Return most frequent words
        return sorted(word_counts.keys(), key=lambda x: word_counts[x], reverse=True)[:max_keywords]