"""
Repository mapping agent for analyzing codebase structure and finding relevant files.
"""
import re
import os
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import structlog

from driftor.integrations.git.factory import get_git_integration_manager
from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class RepositoryMapper:
    """Agent for mapping and analyzing repository structure to find relevant code."""
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.git_manager = get_git_integration_manager(db_session)
        
        # Analysis configuration
        self.max_files_to_analyze = 20
        self.max_file_size_bytes = 100 * 1024  # 100KB limit
        self.relevance_threshold = 0.6
        
        # File type priorities for analysis
        self.file_type_priorities = {
            '.py': 1.0, '.java': 1.0, '.js': 0.9, '.ts': 0.9,
            '.php': 0.9, '.rb': 0.9, '.go': 0.9, '.rs': 0.9,
            '.c': 0.8, '.cpp': 0.8, '.cs': 0.8, '.kt': 0.8,
            '.sql': 0.7, '.json': 0.6, '.yaml': 0.6, '.yml': 0.6,
            '.xml': 0.5, '.html': 0.4, '.css': 0.3, '.md': 0.2
        }
        
        # Component/technology to file pattern mapping
        self.component_patterns = {
            'frontend': [
                r'.*/(frontend|client|ui|web|static)/',
                r'.*\.(js|ts|jsx|tsx|vue|html|css|scss)$'
            ],
            'backend': [
                r'.*/(backend|server|api|service)/',
                r'.*\.(py|java|php|rb|go|rs|cs)$'
            ],
            'database': [
                r'.*/(db|database|migrations|models)/',
                r'.*\.(sql|migration)$'
            ],
            'infrastructure': [
                r'.*/(?:docker|k8s|kubernetes|terraform|ansible)/',
                r'.*(?:dockerfile|docker-compose|\.tf|\.tfvars)$'
            ],
            'tests': [
                r'.*/(test|tests|spec|specs)/',
                r'.*test.*\.(py|java|js|ts)$'
            ]
        }
        
        # Error pattern to file type mapping
        self.error_file_patterns = {
            'null_pointer': [
                r'.*\.(java|kt|cs)$',  # Languages prone to NPE
                r'.*/(?:model|entity|dto|pojo)/',
            ],
            'timeout': [
                r'.*/(?:client|service|api|network)/',
                r'.*(?:client|service|http|request)\.(py|java|js|ts)$'
            ],
            'authentication': [
                r'.*/(?:auth|security|login)/',
                r'.*(?:auth|security|token|login)\.(py|java|js|ts)$'
            ],
            'database': [
                r'.*/(?:db|database|model|repository)/',
                r'.*(?:model|entity|repository|dao)\.(py|java|js|ts)$'
            ],
            'api': [
                r'.*/(?:api|controller|endpoint|route)/',
                r'.*(?:controller|route|api|endpoint)\.(py|java|js|ts)$'
            ]
        }
    
    async def map_repository(
        self, 
        ticket_data: Dict[str, Any], 
        classification: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Map repository structure and find relevant files for the ticket."""
        try:
            ticket_key = ticket_data.get("key", "")
            
            # Get repository information from ticket or tenant config
            repo_info = await self._get_repository_info(ticket_data, tenant_id)
            if not repo_info:
                return {
                    "relevant_files": [],
                    "repository_structure": {},
                    "analysis_metadata": {
                        "error": "No repository configured for this ticket"
                    }
                }
            
            # Get Git integration client
            git_client = await self.git_manager.get_integration(
                tenant_id, repo_info["provider"]
            )
            
            if not git_client:
                return {
                    "relevant_files": [],
                    "repository_structure": {},
                    "analysis_metadata": {
                        "error": f"Git integration not available for {repo_info['provider']}"
                    }
                }
            
            # Analyze repository structure
            repo_structure = await self._analyze_repository_structure(
                git_client, repo_info, classification
            )
            
            # Find relevant files based on ticket content and classification
            relevant_files = await self._find_relevant_files(
                git_client, repo_info, ticket_data, classification
            )
            
            # Analyze file contents for additional context
            file_analysis = await self._analyze_file_contents(
                git_client, repo_info, relevant_files
            )
            
            # Audit the repository analysis
            await audit(
                event_type=AuditEventType.DATA_ACCESSED,
                tenant_id=tenant_id,
                resource_type="repository_analysis",
                resource_id=ticket_key,
                details={
                    "repository": f"{repo_info['owner']}/{repo_info['repo']}",
                    "provider": repo_info["provider"],
                    "files_analyzed": len(relevant_files),
                    "component": classification.get("component", "unknown")
                }
            )
            
            logger.info(
                "Repository mapping completed",
                ticket_key=ticket_key,
                repository=f"{repo_info['owner']}/{repo_info['repo']}",
                files_found=len(relevant_files),
                tenant_id=tenant_id
            )
            
            return {
                "relevant_files": relevant_files,
                "file_analysis": file_analysis,
                "repository_structure": repo_structure,
                "repository_info": repo_info,
                "analysis_metadata": {
                    "files_analyzed": len(relevant_files),
                    "repository": f"{repo_info['owner']}/{repo_info['repo']}",
                    "branch": repo_info.get("branch", "main"),
                    "component_focus": classification.get("component", "unknown")
                }
            }
            
        except Exception as e:
            logger.error(
                "Repository mapping failed",
                ticket_key=ticket_data.get("key", "unknown"),
                error=str(e),
                exc_info=True
            )
            
            return {
                "relevant_files": [],
                "repository_structure": {},
                "analysis_metadata": {
                    "error": str(e),
                    "files_analyzed": 0
                }
            }
    
    async def _get_repository_info(
        self, 
        ticket_data: Dict[str, Any], 
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get repository information from ticket or tenant configuration."""
        # Check if repository is specified in ticket
        repo_url = ticket_data.get("repository_url")
        if repo_url:
            return self._parse_repository_url(repo_url)
        
        # Check ticket labels for repository hints
        labels = ticket_data.get("labels", [])
        for label in labels:
            if "/" in label and any(provider in label.lower() for provider in ["github", "gitlab", "gitea"]):
                return self._parse_repository_url(label)
        
        # Get default repository from tenant configuration
        # TODO: Implement when tenant configuration models are ready
        # For now, return a simulated default
        return {
            "provider": "github",
            "owner": "company",
            "repo": "main-application",
            "branch": "main",
            "base_url": "https://github.com"
        }
    
    def _parse_repository_url(self, url: str) -> Dict[str, Any]:
        """Parse repository URL to extract provider, owner, and repo."""
        # GitHub patterns
        github_pattern = r'(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$'
        match = re.match(github_pattern, url)
        if match:
            return {
                "provider": "github",
                "owner": match.group(1),
                "repo": match.group(2),
                "branch": "main",
                "base_url": "https://github.com"
            }
        
        # GitLab patterns
        gitlab_pattern = r'(?:https?://)?(?:www\.)?gitlab\.com/([^/]+)/([^/]+?)(?:\.git)?/?$'
        match = re.match(gitlab_pattern, url)
        if match:
            return {
                "provider": "gitlab",
                "owner": match.group(1),
                "repo": match.group(2),
                "branch": "main",
                "base_url": "https://gitlab.com"
            }
        
        # Gitea patterns (generic self-hosted)
        gitea_pattern = r'(?:https?://)?([^/]+)/([^/]+)/([^/]+?)(?:\.git)?/?$'
        match = re.match(gitea_pattern, url)
        if match:
            return {
                "provider": "gitea",
                "base_url": f"https://{match.group(1)}",
                "owner": match.group(2),
                "repo": match.group(3),
                "branch": "main"
            }
        
        return None
    
    async def _analyze_repository_structure(
        self, 
        git_client, 
        repo_info: Dict[str, Any],
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze overall repository structure."""
        try:
            # Get repository tree
            tree = await git_client.get_repository_tree(
                repo_info["owner"],
                repo_info["repo"],
                recursive=True,
                branch=repo_info.get("branch", "main")
            )
            
            if not tree.success:
                return {"error": "Failed to fetch repository tree"}
            
            files = tree.data.get("tree", [])
            
            # Analyze structure
            structure = {
                "total_files": len(files),
                "file_types": {},
                "directories": set(),
                "components": {},
                "languages": set()
            }
            
            for file_info in files:
                if file_info.get("type") != "blob":
                    continue
                
                path = file_info.get("path", "")
                file_ext = Path(path).suffix.lower()
                
                # Count file types
                structure["file_types"][file_ext] = structure["file_types"].get(file_ext, 0) + 1
                
                # Track directories
                dir_path = str(Path(path).parent)
                if dir_path != ".":
                    structure["directories"].add(dir_path)
                
                # Detect languages
                language = self._detect_language_from_extension(file_ext)
                if language:
                    structure["languages"].add(language)
                
                # Categorize by component
                component = self._categorize_file_by_path(path)
                if component not in structure["components"]:
                    structure["components"][component] = []
                structure["components"][component].append(path)
            
            # Convert sets to lists for JSON serialization
            structure["directories"] = list(structure["directories"])
            structure["languages"] = list(structure["languages"])
            
            return structure
            
        except Exception as e:
            logger.warning("Repository structure analysis failed", error=str(e))
            return {"error": str(e)}
    
    async def _find_relevant_files(
        self,
        git_client,
        repo_info: Dict[str, Any],
        ticket_data: Dict[str, Any],
        classification: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find files relevant to the ticket based on content and classification."""
        relevant_files = []
        
        try:
            # Search for files by name patterns
            name_based_files = await self._search_files_by_name(
                git_client, repo_info, ticket_data, classification
            )
            relevant_files.extend(name_based_files)
            
            # Search for files by content (if search API available)
            content_based_files = await self._search_files_by_content(
                git_client, repo_info, ticket_data, classification
            )
            relevant_files.extend(content_based_files)
            
            # Get files based on component classification
            component_files = await self._get_component_files(
                git_client, repo_info, classification
            )
            relevant_files.extend(component_files)
            
            # Get files based on error patterns
            error_pattern_files = await self._get_error_pattern_files(
                git_client, repo_info, classification
            )
            relevant_files.extend(error_pattern_files)
            
            # Deduplicate and score files
            unique_files = self._deduplicate_and_score_files(
                relevant_files, ticket_data, classification
            )
            
            # Sort by relevance and limit results
            unique_files.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            return unique_files[:self.max_files_to_analyze]
            
        except Exception as e:
            logger.warning("Relevant file search failed", error=str(e))
            return []
    
    async def _search_files_by_name(
        self,
        git_client,
        repo_info: Dict[str, Any],
        ticket_data: Dict[str, Any],
        classification: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search for files by filename patterns."""
        files = []
        
        # Extract potential file/class names from ticket
        keywords = classification.get("keywords", [])
        summary = ticket_data.get("summary", "")
        
        # Look for file-like patterns in summary and keywords
        file_patterns = []
        
        # Extract CamelCase class names
        camel_case_pattern = r'\b[A-Z][a-zA-Z]*(?:[A-Z][a-zA-Z]*)*\b'
        camel_matches = re.findall(camel_case_pattern, summary)
        file_patterns.extend(camel_matches)
        
        # Extract file extensions mentioned
        ext_pattern = r'\b\w+\.(py|java|js|ts|php|rb|go|rs|cs|cpp|c|h)\b'
        ext_matches = re.findall(ext_pattern, summary)
        file_patterns.extend([match[0] for match in ext_matches])
        
        # Use Git search API if available
        for pattern in file_patterns[:5]:  # Limit patterns
            try:
                search_result = await git_client.search_code(
                    repo_info["owner"],
                    repo_info["repo"],
                    query=f"filename:{pattern}",
                    branch=repo_info.get("branch", "main")
                )
                
                if search_result.success:
                    for item in search_result.data.get("items", []):
                        files.append({
                            "path": item.get("path", ""),
                            "name": item.get("name", ""),
                            "url": item.get("html_url", ""),
                            "relevance_score": 0.8,
                            "match_reason": f"filename matches '{pattern}'"
                        })
                        
            except Exception as e:
                logger.debug(f"File name search failed for pattern {pattern}", error=str(e))
        
        return files
    
    async def _search_files_by_content(
        self,
        git_client,
        repo_info: Dict[str, Any],
        ticket_data: Dict[str, Any],
        classification: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search for files by content patterns."""
        files = []
        
        keywords = classification.get("keywords", [])
        
        # Search for technical keywords in code
        search_terms = [kw for kw in keywords if len(kw) > 3][:3]  # Limit and filter
        
        for term in search_terms:
            try:
                search_result = await git_client.search_code(
                    repo_info["owner"],
                    repo_info["repo"],
                    query=term,
                    branch=repo_info.get("branch", "main")
                )
                
                if search_result.success:
                    for item in search_result.data.get("items", []):
                        files.append({
                            "path": item.get("path", ""),
                            "name": item.get("name", ""),
                            "url": item.get("html_url", ""),
                            "relevance_score": 0.7,
                            "match_reason": f"content matches '{term}'"
                        })
                        
            except Exception as e:
                logger.debug(f"Content search failed for term {term}", error=str(e))
        
        return files
    
    async def _get_component_files(
        self,
        git_client,
        repo_info: Dict[str, Any],
        classification: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get files related to the identified component."""
        files = []
        
        component = classification.get("component", "")
        if component == "unknown" or not component:
            return files
        
        # Get patterns for this component
        patterns = self.component_patterns.get(component, [])
        
        try:
            # Get repository tree
            tree = await git_client.get_repository_tree(
                repo_info["owner"],
                repo_info["repo"],
                recursive=True,
                branch=repo_info.get("branch", "main")
            )
            
            if not tree.success:
                return files
            
            for file_info in tree.data.get("tree", []):
                if file_info.get("type") != "blob":
                    continue
                
                path = file_info.get("path", "")
                
                # Check if path matches component patterns
                for pattern in patterns:
                    if re.search(pattern, path, re.IGNORECASE):
                        files.append({
                            "path": path,
                            "name": Path(path).name,
                            "url": f"{repo_info['base_url']}/{repo_info['owner']}/{repo_info['repo']}/blob/{repo_info.get('branch', 'main')}/{path}",
                            "relevance_score": 0.6,
                            "match_reason": f"matches {component} component pattern"
                        })
                        break
                        
        except Exception as e:
            logger.debug("Component file search failed", error=str(e))
        
        return files
    
    async def _get_error_pattern_files(
        self,
        git_client,
        repo_info: Dict[str, Any],
        classification: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get files related to error patterns found in ticket."""
        files = []
        
        keywords = classification.get("keywords", [])
        
        # Identify error patterns
        error_types = []
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for error_type, patterns in self.error_file_patterns.items():
                if any(pattern in keyword_lower for pattern in error_type.split('_')):
                    error_types.append(error_type)
                    break
        
        if not error_types:
            return files
        
        try:
            # Get repository tree
            tree = await git_client.get_repository_tree(
                repo_info["owner"],
                repo_info["repo"],
                recursive=True,
                branch=repo_info.get("branch", "main")
            )
            
            if not tree.success:
                return files
            
            for file_info in tree.data.get("tree", []):
                if file_info.get("type") != "blob":
                    continue
                
                path = file_info.get("path", "")
                
                # Check if path matches error pattern files
                for error_type in error_types:
                    patterns = self.error_file_patterns.get(error_type, [])
                    for pattern in patterns:
                        if re.search(pattern, path, re.IGNORECASE):
                            files.append({
                                "path": path,
                                "name": Path(path).name,
                                "url": f"{repo_info['base_url']}/{repo_info['owner']}/{repo_info['repo']}/blob/{repo_info.get('branch', 'main')}/{path}",
                                "relevance_score": 0.7,
                                "match_reason": f"related to {error_type.replace('_', ' ')} errors"
                            })
                            break
                    
        except Exception as e:
            logger.debug("Error pattern file search failed", error=str(e))
        
        return files
    
    def _deduplicate_and_score_files(
        self,
        files: List[Dict[str, Any]],
        ticket_data: Dict[str, Any],
        classification: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Remove duplicates and improve scoring."""
        unique_files = {}
        
        for file_info in files:
            path = file_info.get("path", "")
            if path in unique_files:
                # Combine scores and reasons
                existing = unique_files[path]
                existing["relevance_score"] = max(
                    existing.get("relevance_score", 0),
                    file_info.get("relevance_score", 0)
                )
                existing["match_reason"] += f"; {file_info.get('match_reason', '')}"
            else:
                # Adjust score based on file type priority
                file_ext = Path(path).suffix.lower()
                type_priority = self.file_type_priorities.get(file_ext, 0.5)
                file_info["relevance_score"] = file_info.get("relevance_score", 0) * type_priority
                
                unique_files[path] = file_info
        
        return list(unique_files.values())
    
    async def _analyze_file_contents(
        self,
        git_client,
        repo_info: Dict[str, Any],
        relevant_files: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze contents of relevant files for additional context."""
        file_analysis = {
            "analyzed_files": [],
            "code_patterns": {},
            "dependencies": set(),
            "error_locations": []
        }
        
        for file_info in relevant_files[:10]:  # Limit analysis
            try:
                path = file_info.get("path", "")
                
                # Get file content
                content_result = await git_client.get_file_content(
                    repo_info["owner"],
                    repo_info["repo"],
                    path,
                    branch=repo_info.get("branch", "main")
                )
                
                if not content_result.success:
                    continue
                
                content = content_result.data.get("content", "")
                if len(content) > self.max_file_size_bytes:
                    content = content[:self.max_file_size_bytes] + "..."
                
                # Analyze file content
                analysis = self._analyze_single_file(path, content)
                analysis["path"] = path
                analysis["size"] = len(content)
                
                file_analysis["analyzed_files"].append(analysis)
                
                # Aggregate patterns
                for pattern, count in analysis.get("patterns", {}).items():
                    file_analysis["code_patterns"][pattern] = file_analysis["code_patterns"].get(pattern, 0) + count
                
                # Aggregate dependencies
                file_analysis["dependencies"].update(analysis.get("imports", []))
                
                # Track potential error locations
                if analysis.get("has_error_handling"):
                    file_analysis["error_locations"].append({
                        "file": path,
                        "error_patterns": analysis.get("error_patterns", [])
                    })
                    
            except Exception as e:
                logger.debug(f"File analysis failed for {path}", error=str(e))
        
        # Convert sets to lists for JSON serialization
        file_analysis["dependencies"] = list(file_analysis["dependencies"])
        
        return file_analysis
    
    def _analyze_single_file(self, path: str, content: str) -> Dict[str, Any]:
        """Analyze a single file's content."""
        analysis = {
            "language": self._detect_language_from_extension(Path(path).suffix),
            "lines": len(content.split('\n')),
            "imports": [],
            "patterns": {},
            "has_error_handling": False,
            "error_patterns": []
        }
        
        # Extract imports/dependencies
        import_patterns = [
            r'^import\s+([^\s;]+)',  # Python, Java
            r'^from\s+([^\s]+)\s+import',  # Python
            r'^#include\s*[<"]([^>"]+)[>"]',  # C/C++
            r'^require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',  # JavaScript/Node
            r'^use\s+([^;]+);'  # Rust, PHP
        ]
        
        for pattern in import_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            analysis["imports"].extend(matches)
        
        # Count common patterns
        patterns_to_count = {
            'try_catch': len(re.findall(r'\btry\s*{|\btry:', content, re.IGNORECASE)),
            'null_checks': len(re.findall(r'!=\s*null|==\s*null|is\s+None|is\s+not\s+None', content)),
            'logging': len(re.findall(r'\blog\.|logger\.|console\.log|print\(', content)),
            'async_await': len(re.findall(r'\basync\s+|\bawait\s+', content)),
            'database_queries': len(re.findall(r'SELECT\s+|INSERT\s+|UPDATE\s+|DELETE\s+', content, re.IGNORECASE))
        }
        
        analysis["patterns"] = {k: v for k, v in patterns_to_count.items() if v > 0}
        
        # Check for error handling
        error_patterns = [
            r'\bexcept\s+', r'\bcatch\s*\(', r'\.catch\(',
            r'\berror\s*:', r'\bException\b', r'\bthrows?\s+'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                analysis["has_error_handling"] = True
                analysis["error_patterns"].append(pattern)
        
        return analysis
    
    def _detect_language_from_extension(self, ext: str) -> str:
        """Detect programming language from file extension."""
        language_map = {
            '.py': 'python', '.java': 'java', '.js': 'javascript', '.ts': 'typescript',
            '.php': 'php', '.rb': 'ruby', '.go': 'go', '.rs': 'rust',
            '.c': 'c', '.cpp': 'cpp', '.cs': 'csharp', '.kt': 'kotlin',
            '.swift': 'swift', '.scala': 'scala', '.clj': 'clojure',
            '.sql': 'sql', '.html': 'html', '.css': 'css'
        }
        return language_map.get(ext.lower(), 'unknown')
    
    def _categorize_file_by_path(self, path: str) -> str:
        """Categorize file by its path structure."""
        path_lower = path.lower()
        
        for component, patterns in self.component_patterns.items():
            for pattern in patterns:
                if re.search(pattern, path_lower):
                    return component
        
        return 'general'