"""
Code analysis service that uses Claude Code API for analyzing repositories
and suggesting fixes for Jira tickets.
"""
from typing import Dict, Any, List, Optional
import logging
import re
from anthropic import Anthropic

from app.core.config import settings
from app.models.ticket import Ticket
from app.models.project_mapping import ProjectMapping
from app.services.integrations.git_client import GitClient

logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """Service for analyzing code repositories and suggesting fixes using Claude Code API."""
    
    def __init__(self):
        self.anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    async def analyze_for_ticket(
        self, 
        ticket: Ticket, 
        git_client: GitClient,
        project_mapping: ProjectMapping
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze code repository for potential issues related to the ticket
        and suggest fixes using Claude Code API.
        """
        try:
            logger.info(f"Starting code analysis for ticket {ticket.jira_key}")
            
            # Step 1: Search for relevant code files
            relevant_files = await self._find_relevant_files(ticket, git_client)
            
            if not relevant_files:
                logger.info(f"No relevant files found for ticket {ticket.jira_key}")
                return None
            
            # Step 2: Analyze relevant files with intelligent prioritization
            analysis_results = []
            
            # Phase 1: Quick analysis of top files to identify patterns
            priority_files = await self._prioritize_files_for_analysis(
                ticket, relevant_files[:10], git_client
            )
            
            # Phase 2: Deep analysis of high-priority files (up to 8 files)
            for file_info in priority_files[:8]:  
                file_analysis = await self._analyze_file(
                    ticket=ticket,
                    file_info=file_info,
                    git_client=git_client,
                    analysis_depth="deep" if file_info.get('priority_score', 0) > 0.7 else "quick"
                )
                
                if file_analysis:
                    analysis_results.append(file_analysis)
            
            # Phase 3: If no strong matches, expand search to related components
            if not analysis_results or max(r.get('confidence', 0) for r in analysis_results) < 0.6:
                logger.info(f"Expanding search for {ticket.jira_key} - initial analysis confidence low")
                expanded_files = await self._find_related_components(ticket, git_client, analysis_results)
                
                for file_info in expanded_files[:5]:
                    file_analysis = await self._analyze_file(
                        ticket=ticket,
                        file_info=file_info,
                        git_client=git_client,
                        analysis_depth="targeted"
                    )
                    if file_analysis:
                        analysis_results.append(file_analysis)
            
            if not analysis_results:
                return None
            
            # Step 3: Generate comprehensive analysis summary
            summary = await self._generate_analysis_summary(ticket, analysis_results)
            
            return {
                'ticket_key': ticket.jira_key,
                'repository': f"{project_mapping.git_organization}/{project_mapping.git_repository}",
                'analysis_timestamp': ticket.updated_at.isoformat(),
                'file_locations': analysis_results,
                'summary': summary,
                'confidence_score': self._calculate_analysis_confidence(analysis_results),
                'suggested_actions': self._extract_suggested_actions(analysis_results)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing code for ticket {ticket.jira_key}: {e}")
            return None
    
    async def _find_relevant_files(self, ticket: Ticket, git_client: GitClient) -> List[Dict[str, Any]]:
        """Find code files that might be related to the ticket."""
        try:
            relevant_files = []
            
            # Extract search terms from ticket
            search_terms = self._extract_search_terms(ticket.title, ticket.description or '')
            
            # Search for each term in the codebase
            for term in search_terms[:5]:  # Search top 5 terms
                try:
                    search_results = await git_client.search_code(
                        query=term,
                        limit=5
                    )
                    
                    for result in search_results:
                        relevant_files.append({
                            'file_path': result.get('file_path'),
                            'search_term': term,
                            'score': result.get('score', 0),
                            'url': result.get('url')
                        })
                        
                except Exception as e:
                    logger.error(f"Error searching for term '{term}': {e}")
                    continue
            
            # Remove duplicates and sort by relevance
            unique_files = {}
            for file_info in relevant_files:
                path = file_info['file_path']
                if path not in unique_files or file_info['score'] > unique_files[path]['score']:
                    unique_files[path] = file_info
            
            return sorted(unique_files.values(), key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error finding relevant files: {e}")
            return []
    
    async def _prioritize_files_for_analysis(
        self, 
        ticket: Ticket, 
        candidate_files: List[Dict[str, Any]], 
        git_client: GitClient
    ) -> List[Dict[str, Any]]:
        """Intelligently prioritize files for analysis based on multiple factors."""
        try:
            prioritized_files = []
            
            for file_info in candidate_files:
                file_path = file_info['file_path']
                priority_score = 0.0
                
                # Factor 1: File extension relevance (40% weight)
                ext_score = self._calculate_file_extension_score(file_path, ticket)
                priority_score += ext_score * 0.4
                
                # Factor 2: Path relevance to ticket keywords (30% weight)
                path_score = self._calculate_path_relevance_score(file_path, ticket)
                priority_score += path_score * 0.3
                
                # Factor 3: Search match score (20% weight)
                search_score = file_info.get('score', 0) / 100.0  # Normalize
                priority_score += search_score * 0.2
                
                # Factor 4: Recent modification (10% weight)
                recency_score = await self._calculate_file_recency_score(file_path, git_client)
                priority_score += recency_score * 0.1
                
                file_info['priority_score'] = priority_score
                prioritized_files.append(file_info)
            
            # Sort by priority score
            prioritized_files.sort(key=lambda x: x['priority_score'], reverse=True)
            return prioritized_files
            
        except Exception as e:
            logger.error(f"Error prioritizing files: {e}")
            return candidate_files  # Return original list as fallback

    async def _find_related_components(
        self, 
        ticket: Ticket, 
        git_client: GitClient, 
        initial_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find related components when initial analysis has low confidence."""
        try:
            related_files = []
            
            # Strategy 1: Look for common patterns in stack traces or error messages
            error_patterns = self._extract_error_patterns(ticket.description or "")
            for pattern in error_patterns:
                search_results = await git_client.search_code(pattern, limit=3)
                related_files.extend(search_results)
            
            # Strategy 2: Find files that import/reference files from initial analysis
            if initial_results:
                for result in initial_results[:2]:  # Check top 2 results
                    file_path = result.get('file_path', '')
                    if file_path:
                        # Search for files that import this file
                        import_search = await self._find_files_importing(file_path, git_client)
                        related_files.extend(import_search)
            
            # Strategy 3: Look in common bug-prone areas
            common_patterns = [
                "validation", "auth", "security", "error", "exception", 
                "handler", "middleware", "config", "util"
            ]
            
            for pattern in common_patterns:
                if pattern.lower() in ticket.title.lower() or pattern.lower() in (ticket.description or "").lower():
                    search_results = await git_client.search_code(pattern, limit=2)
                    related_files.extend(search_results)
            
            # Remove duplicates and add metadata
            unique_files = {}
            for file_info in related_files:
                path = file_info.get('file_path')
                if path and path not in unique_files:
                    file_info['search_strategy'] = 'expanded_search'
                    unique_files[path] = file_info
            
            return list(unique_files.values())
            
        except Exception as e:
            logger.error(f"Error finding related components: {e}")
            return []

    def _calculate_file_extension_score(self, file_path: str, ticket: Ticket) -> float:
        """Score file based on extension relevance to typical bug locations."""
        try:
            extension = file_path.split('.')[-1].lower()
            
            # High priority extensions for bug analysis
            high_priority = {
                'py': 0.9, 'js': 0.9, 'ts': 0.9, 'java': 0.9, 'cpp': 0.8, 'c': 0.8,
                'go': 0.8, 'rs': 0.8, 'php': 0.8, 'rb': 0.8, 'cs': 0.8
            }
            
            # Medium priority
            medium_priority = {
                'jsx': 0.7, 'tsx': 0.7, 'vue': 0.7, 'html': 0.6, 'css': 0.5,
                'scss': 0.5, 'sql': 0.7, 'yaml': 0.6, 'yml': 0.6, 'json': 0.6
            }
            
            # Low priority
            low_priority = {
                'md': 0.2, 'txt': 0.2, 'xml': 0.4, 'properties': 0.4, 'conf': 0.4
            }
            
            if extension in high_priority:
                return high_priority[extension]
            elif extension in medium_priority:
                return medium_priority[extension]
            elif extension in low_priority:
                return low_priority[extension]
            else:
                return 0.3  # Unknown extension
                
        except Exception:
            return 0.3

    def _calculate_path_relevance_score(self, file_path: str, ticket: Ticket) -> float:
        """Score file path relevance to ticket content."""
        try:
            path_lower = file_path.lower()
            title_words = set(ticket.title.lower().split())
            desc_words = set((ticket.description or "").lower().split())
            
            # Extract meaningful words (length > 3)
            meaningful_words = {word for word in title_words.union(desc_words) if len(word) > 3}
            
            score = 0.0
            max_possible_score = len(meaningful_words)
            
            if max_possible_score == 0:
                return 0.0
            
            # Check how many ticket keywords appear in the file path
            for word in meaningful_words:
                if word in path_lower:
                    score += 1.0
            
            # Bonus for being in common bug-prone directories
            bug_prone_paths = ['service', 'controller', 'handler', 'middleware', 'auth', 'security', 'validation']
            for path_segment in bug_prone_paths:
                if path_segment in path_lower:
                    score += 0.5
                    break
            
            return min(score / max_possible_score, 1.0)
            
        except Exception:
            return 0.0

    async def _calculate_file_recency_score(self, file_path: str, git_client: GitClient) -> float:
        """Score based on how recently the file was modified (more recent = higher score)."""
        try:
            # This would require Git API to get commit history
            # For MVP, return neutral score
            return 0.5
        except Exception:
            return 0.5

    def _extract_error_patterns(self, description: str) -> List[str]:
        """Extract error patterns, exception names, and stack trace elements."""
        import re
        
        patterns = []
        
        # Extract exception names
        exception_pattern = r'\b\w*(?:Exception|Error)\b'
        exceptions = re.findall(exception_pattern, description, re.IGNORECASE)
        patterns.extend(exceptions)
        
        # Extract method/function names from stack traces
        method_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\)'
        methods = re.findall(method_pattern, description)
        patterns.extend([m.split('(')[0] for m in methods])
        
        # Extract quoted strings (often error messages)
        quoted_pattern = r'"([^"]{4,})"'
        quoted_strings = re.findall(quoted_pattern, description)
        patterns.extend(quoted_strings)
        
        return patterns[:10]  # Limit to avoid too many searches

    async def _find_files_importing(self, target_file: str, git_client: GitClient) -> List[Dict[str, Any]]:
        """Find files that import or reference the target file."""
        try:
            # Extract filename without extension
            filename = target_file.split('/')[-1].split('.')[0]
            
            # Search for import statements
            import_patterns = [
                f'import {filename}',
                f'from {filename}',
                f'require("{filename}")',
                f'include "{filename}"'
            ]
            
            results = []
            for pattern in import_patterns:
                search_results = await git_client.search_code(pattern, limit=2)
                results.extend(search_results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error finding importing files: {e}")
            return []

    async def _analyze_file(
        self, 
        ticket: Ticket, 
        file_info: Dict[str, Any], 
        git_client: GitClient,
        analysis_depth: str = "deep"
    ) -> Optional[Dict[str, Any]]:
        """Analyze a specific file using Claude Code API."""
        try:
            file_path = file_info['file_path']
            
            # Get file content
            file_content = await git_client.get_file_content(file_path)
            if not file_content:
                logger.warning(f"Could not retrieve content for {file_path}")
                return None
            
            # Limit file size for analysis (Claude has token limits)
            if len(file_content) > 10000:  # ~10KB limit
                file_content = file_content[:10000] + "\n... (truncated)"
            
            # Create analysis prompt based on depth
            prompt = self._create_analysis_prompt(ticket, file_path, file_content, analysis_depth)
            
            # Adjust token limit based on analysis depth
            max_tokens = {
                "quick": 800,
                "deep": 2000,
                "targeted": 1200
            }.get(analysis_depth, 1500)
            
            # Call Claude API
            response = self.anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            
            analysis_text = response.content[0].text
            
            # Parse the analysis response
            parsed_analysis = self._parse_analysis_response(analysis_text)
            
            return {
                'file_path': file_path,
                'file_url': file_info.get('url'),
                'search_term': file_info.get('search_term'),
                'description': parsed_analysis.get('description', ''),
                'potential_issues': parsed_analysis.get('issues', []),
                'suggested_fix': parsed_analysis.get('fix', ''),
                'confidence': parsed_analysis.get('confidence', 0.5),
                'analysis_raw': analysis_text
            }
            
        except Exception as e:
            logger.error(f"Error analyzing file {file_info.get('file_path', 'unknown')}: {e}")
            return None
    
    def _create_analysis_prompt(self, ticket: Ticket, file_path: str, file_content: str, analysis_depth: str = "deep") -> str:
        """Create a prompt for Claude to analyze the code file."""
        
        base_prompt = f"""You are a senior software engineer analyzing code for a bug ticket.

**Ticket Information:**
- Key: {ticket.jira_key}
- Title: {ticket.title}
- Description: {ticket.description or 'No description provided'}
- Type: {ticket.ticket_type}

**File to Analyze:**
- Path: {file_path}
- Content:
```
{file_content}
```"""

        if analysis_depth == "quick":
            task_prompt = """
**Task (Quick Analysis):**
Quickly scan this file for obvious issues related to the ticket. Focus on:
1. Clear bugs that match the ticket description
2. Common error patterns (null checks, validation, etc.)
3. Exception handling issues

**Response Format:**
DESCRIPTION: One sentence about the file's purpose and relevance.
POTENTIAL_ISSUES: List 1-3 most obvious issues only.
SUGGESTED_FIX: Brief fix recommendations.
CONFIDENCE: Rate 0.0 to 1.0."""

        elif analysis_depth == "targeted":
            task_prompt = """
**Task (Targeted Analysis):**
This file was found through expanded search. Analyze specifically for:
1. Secondary effects that could cause the reported bug
2. Configuration or setup issues
3. Dependencies that might be failing
4. Integration points with other components

**Response Format:**
DESCRIPTION: Brief description focusing on how this relates to the main issue.
POTENTIAL_ISSUES: List specific integration or dependency issues.
SUGGESTED_FIX: Targeted recommendations for this component.
CONFIDENCE: Rate 0.0 to 1.0."""

        else:  # deep analysis
            task_prompt = """
**Task (Deep Analysis):**
Thoroughly analyze this code file for the bug ticket. Look for:
1. Direct bugs or logic errors that could cause the reported issue
2. Edge cases not properly handled
3. Race conditions, threading issues, or async problems
4. Input validation and error handling gaps
5. Performance issues that could manifest as bugs
6. Security vulnerabilities that might appear as functional bugs
7. Configuration or environment-dependent issues

**Response Format:**
DESCRIPTION: Detailed description of the file's purpose and its relevance to the ticket.

POTENTIAL_ISSUES:
- Issue 1: Specific description with line numbers and code context
- Issue 2: [Continue for all identified issues]

SUGGESTED_FIX:
Comprehensive fix recommendations including:
- Specific code changes needed
- Testing recommendations
- Potential side effects to consider

CONFIDENCE: Rate your confidence in this analysis from 0.0 to 1.0.

Focus on actionable insights with specific line numbers and code examples."""

        return base_prompt + task_prompt
    
    def _parse_analysis_response(self, analysis_text: str) -> Dict[str, Any]:
        """Parse Claude's analysis response into structured data."""
        try:
            parsed = {
                'description': '',
                'issues': [],
                'fix': '',
                'confidence': 0.5
            }
            
            # Extract description
            desc_match = re.search(r'DESCRIPTION:\s*(.*?)(?=POTENTIAL_ISSUES:|$)', analysis_text, re.DOTALL)
            if desc_match:
                parsed['description'] = desc_match.group(1).strip()
            
            # Extract potential issues
            issues_match = re.search(r'POTENTIAL_ISSUES:\s*(.*?)(?=SUGGESTED_FIX:|$)', analysis_text, re.DOTALL)
            if issues_match:
                issues_text = issues_match.group(1).strip()
                # Split by bullet points or dashes
                issue_lines = re.findall(r'[-•]\s*(.+)', issues_text)
                parsed['issues'] = [issue.strip() for issue in issue_lines]
            
            # Extract suggested fix
            fix_match = re.search(r'SUGGESTED_FIX:\s*(.*?)(?=CONFIDENCE:|$)', analysis_text, re.DOTALL)
            if fix_match:
                parsed['fix'] = fix_match.group(1).strip()
            
            # Extract confidence
            conf_match = re.search(r'CONFIDENCE:\s*([\d.]+)', analysis_text)
            if conf_match:
                try:
                    parsed['confidence'] = float(conf_match.group(1))
                except ValueError:
                    parsed['confidence'] = 0.5
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return {
                'description': 'Analysis parsing failed',
                'issues': [],
                'fix': analysis_text,  # Return raw text as fallback
                'confidence': 0.3
            }
    
    async def _generate_analysis_summary(self, ticket: Ticket, analysis_results: List[Dict[str, Any]]) -> str:
        """Generate a comprehensive summary of all file analyses."""
        try:
            # Create summary prompt
            files_summary = []
            for result in analysis_results:
                files_summary.append(f"- {result['file_path']}: {result.get('description', 'No description')}")
            
            summary_prompt = f"""
Based on the analysis of multiple files for ticket {ticket.jira_key} "{ticket.title}", 
provide a concise summary of the findings:

**Files Analyzed:**
{chr(10).join(files_summary)}

**Task:**
Provide a 2-3 sentence summary of the most likely cause of the bug and the recommended approach to fix it.
Focus on the highest confidence findings and actionable next steps.
"""
            
            response = self.anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=300,
                messages=[{"role": "user", "content": summary_prompt}]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            logger.error(f"Error generating analysis summary: {e}")
            return "Analysis summary generation failed."
    
    def _extract_search_terms(self, title: str, description: str) -> List[str]:
        """Extract meaningful search terms from ticket title and description."""
        import re
        
        text = f"{title} {description}".lower()
        
        # Extract potential class names, method names, and technical terms
        patterns = [
            r'\b[A-Z][a-zA-Z]*(?:Service|Controller|Manager|Handler|Component)\b',  # Service classes
            r'\b[a-zA-Z]+Exception\b',  # Exception names
            r'\b[a-zA-Z]+Error\b',      # Error names
            r'\b[a-zA-Z]{4,}\b'         # General terms 4+ chars
        ]
        
        terms = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            terms.update(matches)
        
        # Filter out common stop words
        stop_words = {'error', 'issue', 'problem', 'failed', 'cannot', 'when', 'after', 'before'}
        terms = [term for term in terms if term.lower() not in stop_words]
        
        return list(terms)[:10]  # Return top 10 terms
    
    def _calculate_analysis_confidence(self, analysis_results: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence score for the code analysis."""
        if not analysis_results:
            return 0.0
        
        # Average confidence of individual file analyses
        confidences = [result.get('confidence', 0.5) for result in analysis_results]
        avg_confidence = sum(confidences) / len(confidences)
        
        # Boost confidence if multiple files have issues identified
        issue_count = sum(len(result.get('potential_issues', [])) for result in analysis_results)
        issue_boost = min(issue_count * 0.1, 0.3)  # Max 0.3 boost
        
        return min(avg_confidence + issue_boost, 1.0)
    
    def _extract_suggested_actions(self, analysis_results: List[Dict[str, Any]]) -> List[str]:
        """Extract actionable suggestions from the analysis results."""
        actions = []
        
        for result in analysis_results:
            file_path = result.get('file_path', '')
            suggested_fix = result.get('suggested_fix', '')
            
            if suggested_fix:
                actions.append(f"Review {file_path}: {suggested_fix[:100]}...")
        
        # Add general actions
        if analysis_results:
            actions.append("Run tests after making any changes")
            actions.append("Consider adding unit tests for the identified areas")
        
        return actions[:5]  # Limit to top 5 actions