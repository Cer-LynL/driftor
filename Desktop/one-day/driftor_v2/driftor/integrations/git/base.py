"""
Base Git provider integration supporting GitHub, GitLab, and Gitea.
"""
import asyncio
import base64
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
import structlog

from driftor.integrations.base import BaseIntegration, IntegrationConfig, APIResponse
from driftor.core.rate_limiter import RateLimitType
from driftor.security.audit import audit, AuditEventType, AuditSeverity

logger = structlog.get_logger(__name__)


class GitProvider(str, Enum):
    """Supported Git providers."""
    GITHUB = "github"
    GITLAB = "gitlab"
    GITEA = "gitea"


@dataclass
class Repository:
    """Repository information."""
    id: str
    name: str
    full_name: str
    description: Optional[str]
    private: bool
    default_branch: str
    clone_url: str
    ssh_url: str
    web_url: str
    provider: GitProvider
    
    # Access control
    permissions: Dict[str, bool]
    
    # Metadata
    language: Optional[str]
    size_kb: int
    created_at: str
    updated_at: str


@dataclass
class FileContent:
    """File content from repository."""
    path: str
    content: str
    encoding: str
    size: int
    sha: str
    branch: str
    
    # Context
    blame_info: Optional[List[Dict[str, any]]] = None
    last_modified: Optional[str] = None
    last_commit: Optional[Dict[str, any]] = None


@dataclass
class GitBlameInfo:
    """Git blame information for a line."""
    line_number: int
    commit_sha: str
    author: str
    author_email: str
    timestamp: str
    message: str


@dataclass
class SearchResult:
    """Code search result."""
    file_path: str
    line_number: int
    line_content: str
    context_before: List[str]
    context_after: List[str]
    score: float


class BaseGitProvider(BaseIntegration, ABC):
    """Base class for Git provider integrations."""
    
    def __init__(self, config: IntegrationConfig, credentials: Dict[str, str]):
        super().__init__(config, credentials)
        self.provider = self._get_provider_type()
    
    @abstractmethod
    def _get_provider_type(self) -> GitProvider:
        """Get the provider type."""
        pass
    
    @abstractmethod
    async def list_repositories(
        self, 
        organization: Optional[str] = None,
        limit: int = 100
    ) -> List[Repository]:
        """List accessible repositories."""
        pass
    
    @abstractmethod
    async def get_repository(self, repo_id: str) -> Optional[Repository]:
        """Get repository by ID or full name."""
        pass
    
    @abstractmethod
    async def get_file_content(
        self, 
        repo_id: str, 
        file_path: str, 
        branch: str = "main"
    ) -> Optional[FileContent]:
        """Get file content from repository."""
        pass
    
    @abstractmethod
    async def search_code(
        self, 
        repo_id: str, 
        query: str, 
        file_extension: Optional[str] = None,
        limit: int = 20
    ) -> List[SearchResult]:
        """Search code in repository."""
        pass
    
    @abstractmethod
    async def get_file_history(
        self, 
        repo_id: str, 
        file_path: str, 
        limit: int = 10
    ) -> List[Dict[str, any]]:
        """Get file commit history."""
        pass
    
    @abstractmethod
    async def get_blame_info(
        self, 
        repo_id: str, 
        file_path: str, 
        branch: str = "main"
    ) -> List[GitBlameInfo]:
        """Get blame information for a file."""
        pass
    
    async def analyze_repository_structure(self, repo_id: str) -> Dict[str, any]:
        """Analyze repository structure to understand project type and layout."""
        try:
            repo = await self.get_repository(repo_id)
            if not repo:
                return {"error": "Repository not found"}
            
            # Get common configuration files
            config_files = [
                "package.json",      # Node.js
                "requirements.txt",  # Python
                "Cargo.toml",       # Rust
                "go.mod",           # Go
                "pom.xml",          # Java Maven
                "build.gradle",     # Java Gradle
                "composer.json",    # PHP
                "Gemfile",          # Ruby
                ".csproj",          # C#
                "CMakeLists.txt",   # C/C++
                "Dockerfile",       # Docker
                "docker-compose.yml", # Docker Compose
            ]
            
            project_info = {
                "repository": repo.name,
                "provider": repo.provider.value,
                "primary_language": repo.language,
                "project_type": "unknown",
                "config_files": [],
                "directory_structure": {},
                "potential_entry_points": []
            }
            
            # Check for configuration files
            for config_file in config_files:
                try:
                    content = await self.get_file_content(repo_id, config_file)
                    if content:
                        project_info["config_files"].append({
                            "file": config_file,
                            "size": content.size,
                            "last_modified": content.last_modified
                        })
                        
                        # Determine project type
                        if config_file == "package.json":
                            project_info["project_type"] = "nodejs"
                        elif config_file in ["requirements.txt", "setup.py"]:
                            project_info["project_type"] = "python"
                        elif config_file == "Cargo.toml":
                            project_info["project_type"] = "rust"
                        elif config_file == "go.mod":
                            project_info["project_type"] = "go"
                        elif config_file in ["pom.xml", "build.gradle"]:
                            project_info["project_type"] = "java"
                        
                except Exception:
                    # File doesn't exist, continue
                    continue
            
            # Analyze directory structure (limited to avoid rate limits)
            try:
                common_dirs = ["src", "lib", "app", "components", "services", "utils", "tests", "test"]
                for dir_name in common_dirs:
                    # This is a simplified check - in practice, you'd use tree/contents API
                    test_file = f"{dir_name}/README.md"  # Try to access a common file
                    try:
                        await self.get_file_content(repo_id, test_file)
                        project_info["directory_structure"][dir_name] = True
                    except:
                        project_info["directory_structure"][dir_name] = False
                        
            except Exception as e:
                logger.warning("Failed to analyze directory structure", error=str(e))
            
            return project_info
            
        except Exception as e:
            logger.error(
                "Repository analysis failed",
                repo_id=repo_id,
                provider=self.provider.value,
                error=str(e)
            )
            return {"error": str(e)}
    
    async def find_relevant_files(
        self, 
        repo_id: str, 
        keywords: List[str],
        file_extensions: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None
    ) -> List[Dict[str, any]]:
        """Find files relevant to the given keywords."""
        try:
            relevant_files = []
            exclude_paths = exclude_paths or ["node_modules", ".git", "dist", "build", "__pycache__"]
            
            # Search for each keyword
            for keyword in keywords:
                try:
                    search_results = await self.search_code(
                        repo_id=repo_id,
                        query=keyword,
                        limit=10
                    )
                    
                    for result in search_results:
                        # Skip excluded paths
                        if any(exclude in result.file_path for exclude in exclude_paths):
                            continue
                        
                        # Filter by file extension if specified
                        if file_extensions:
                            file_ext = result.file_path.split('.')[-1].lower()
                            if file_ext not in file_extensions:
                                continue
                        
                        # Get full file content
                        file_content = await self.get_file_content(repo_id, result.file_path)
                        if file_content:
                            relevant_files.append({
                                "path": result.file_path,
                                "line_number": result.line_number,
                                "matched_line": result.line_content,
                                "keyword": keyword,
                                "score": result.score,
                                "size": file_content.size,
                                "last_modified": file_content.last_modified,
                                "language": self._detect_language(result.file_path)
                            })
                    
                    # Rate limiting pause
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.warning(
                        "Keyword search failed",
                        keyword=keyword,
                        repo_id=repo_id,
                        error=str(e)
                    )
                    continue
            
            # Remove duplicates and sort by score
            seen_files = set()
            unique_files = []
            
            for file_info in sorted(relevant_files, key=lambda x: x["score"], reverse=True):
                if file_info["path"] not in seen_files:
                    seen_files.add(file_info["path"])
                    unique_files.append(file_info)
            
            return unique_files[:20]  # Limit to top 20 results
            
        except Exception as e:
            logger.error(
                "Failed to find relevant files",
                repo_id=repo_id,
                keywords=keywords,
                error=str(e)
            )
            return []
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        extension_map = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'jsx': 'javascript',
            'tsx': 'typescript',
            'java': 'java',
            'kt': 'kotlin',
            'scala': 'scala',
            'go': 'go',
            'rs': 'rust',
            'cpp': 'cpp',
            'cc': 'cpp',
            'cxx': 'cpp',
            'c': 'c',
            'h': 'c',
            'hpp': 'cpp',
            'cs': 'csharp',
            'php': 'php',
            'rb': 'ruby',
            'swift': 'swift',
            'r': 'r',
            'sql': 'sql',
            'sh': 'shell',
            'bash': 'shell',
            'yaml': 'yaml',
            'yml': 'yaml',
            'json': 'json',
            'xml': 'xml',
            'html': 'html',
            'css': 'css',
            'scss': 'scss',
            'sass': 'sass'
        }
        
        ext = file_path.split('.')[-1].lower()
        return extension_map.get(ext, 'unknown')
    
    async def get_recent_commits(
        self, 
        repo_id: str, 
        file_path: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, any]]:
        """Get recent commits, optionally filtered."""
        # This is a base implementation - each provider will override
        try:
            # Get file history if file_path is specified
            if file_path:
                return await self.get_file_history(repo_id, file_path, limit)
            
            # Otherwise return empty list - subclasses should implement repo-wide commits
            return []
            
        except Exception as e:
            logger.error(
                "Failed to get recent commits",
                repo_id=repo_id,
                file_path=file_path,
                error=str(e)
            )
            return []
    
    def extract_issue_references(self, text: str) -> List[str]:
        """Extract issue references from commit messages or text."""
        patterns = [
            r'#(\d+)',                    # #123
            r'(?:fix|fixes|close|closes|resolve|resolves)\s+#(\d+)',  # fixes #123
            r'(?:issue|bug)\s+#?(\d+)',   # issue 123 or issue #123
            r'(?:ticket|task)\s+#?(\d+)'  # ticket 123
        ]
        
        references = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            references.extend(matches)
        
        return list(set(references))  # Remove duplicates
    
    async def analyze_code_quality(
        self, 
        repo_id: str, 
        file_paths: List[str]
    ) -> Dict[str, any]:
        """Analyze code quality metrics for given files."""
        try:
            analysis = {
                "files_analyzed": 0,
                "total_lines": 0,
                "complexity_score": 0.0,
                "issues": [],
                "suggestions": []
            }
            
            for file_path in file_paths[:5]:  # Limit to 5 files to avoid rate limits
                try:
                    content = await self.get_file_content(repo_id, file_path)
                    if not content:
                        continue
                    
                    analysis["files_analyzed"] += 1
                    lines = content.content.split('\n')
                    analysis["total_lines"] += len(lines)
                    
                    # Basic complexity analysis
                    complexity = self._calculate_basic_complexity(content.content, file_path)
                    analysis["complexity_score"] += complexity
                    
                    # Basic issue detection
                    issues = self._detect_basic_issues(content.content, file_path)
                    analysis["issues"].extend(issues)
                    
                except Exception as e:
                    logger.warning(
                        "Failed to analyze file",
                        file_path=file_path,
                        error=str(e)
                    )
                    continue
            
            # Average complexity
            if analysis["files_analyzed"] > 0:
                analysis["complexity_score"] /= analysis["files_analyzed"]
            
            return analysis
            
        except Exception as e:
            logger.error(
                "Code quality analysis failed",
                repo_id=repo_id,
                error=str(e)
            )
            return {"error": str(e)}
    
    def _calculate_basic_complexity(self, content: str, file_path: str) -> float:
        """Calculate basic complexity score."""
        language = self._detect_language(file_path)
        lines = content.split('\n')
        
        complexity_indicators = {
            'if': 1, 'else': 1, 'elif': 1, 'while': 1, 'for': 1,
            'switch': 2, 'case': 1, 'try': 1, 'catch': 1, 'except': 1,
            'function': 2, 'def': 2, 'class': 3, 'async': 1, 'await': 1
        }
        
        score = 0
        for line in lines:
            line_lower = line.lower().strip()
            for indicator, weight in complexity_indicators.items():
                if indicator in line_lower:
                    score += weight
        
        # Normalize by file size
        return score / max(len(lines), 1)
    
    def _detect_basic_issues(self, content: str, file_path: str) -> List[Dict[str, any]]:
        """Detect basic code issues."""
        issues = []
        lines = content.split('\n')
        
        # Common issue patterns
        issue_patterns = {
            'TODO': 'TODO comment found',
            'FIXME': 'FIXME comment found',
            'XXX': 'XXX comment found',
            'console.log': 'Debug statement left in code',
            'print(': 'Debug print statement (Python)',
            'debugger': 'Debugger statement left in code',
            'eval(': 'Potentially unsafe eval() usage',
            'innerHTML': 'Potentially unsafe innerHTML usage'
        }
        
        for line_num, line in enumerate(lines, 1):
            for pattern, description in issue_patterns.items():
                if pattern in line:
                    issues.append({
                        "line": line_num,
                        "type": "warning",
                        "description": description,
                        "content": line.strip()
                    })
        
        return issues