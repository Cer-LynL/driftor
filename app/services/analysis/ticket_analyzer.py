"""
Core ticket analysis service that orchestrates similarity search, 
documentation lookup, and code analysis.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import logging
import json

from app.models.ticket import Ticket
from app.services.integrations.jira_client import JiraClient
from app.services.integrations.confluence_client import ConfluenceClient
from app.services.integrations.git_client import GitClient
from app.services.analysis.similarity_search import SimilaritySearchService
from app.services.analysis.code_analyzer import CodeAnalyzer

logger = logging.getLogger(__name__)


class TicketAnalyzer:
    """Main service for analyzing tickets and generating comprehensive reports."""
    
    def __init__(self):
        self.similarity_service = SimilaritySearchService()
        self.code_analyzer = CodeAnalyzer()
    
    async def analyze_ticket(
        self, 
        ticket: Ticket, 
        jira_client: Optional[JiraClient] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive ticket analysis including:
        - Similar ticket search
        - Documentation lookup  
        - Code analysis and fix suggestions
        """
        try:
            analysis_result = {
                'ticket_key': ticket.jira_key,
                'analysis_timestamp': ticket.updated_at.isoformat(),
                'similar_tickets': [],
                'documentation_links': [],
                'code_analysis': None,
                'confidence_score': 0.0,
                'analysis_metadata': {}
            }
            
            # Step 1: Find similar tickets
            logger.info(f"Finding similar tickets for {ticket.jira_key}")
            similar_tickets = await self._find_similar_tickets(ticket, jira_client, db)
            analysis_result['similar_tickets'] = similar_tickets
            
            # Step 2: Search for relevant documentation
            logger.info(f"Searching documentation for {ticket.jira_key}")
            documentation = await self._search_documentation(ticket)
            analysis_result['documentation_links'] = documentation
            
            # Step 3: Analyze code and suggest fixes
            logger.info(f"Analyzing code for {ticket.jira_key}")
            code_analysis = await self._analyze_code(ticket)
            analysis_result['code_analysis'] = code_analysis
            
            # Step 4: Calculate overall confidence score
            confidence = self._calculate_confidence_score(analysis_result)
            analysis_result['confidence_score'] = confidence
            
            # Step 5: Add metadata
            analysis_result['analysis_metadata'] = {
                'similar_tickets_count': len(similar_tickets),
                'documentation_links_count': len(documentation),
                'code_analysis_available': bool(code_analysis),
                'analysis_version': '1.0'
            }
            
            logger.info(f"Analysis completed for {ticket.jira_key} with confidence {confidence:.2f}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing ticket {ticket.jira_key}: {e}")
            return {
                'ticket_key': ticket.jira_key,
                'error': str(e),
                'analysis_timestamp': ticket.updated_at.isoformat(),
                'similar_tickets': [],
                'documentation_links': [],
                'code_analysis': None,
                'confidence_score': 0.0
            }
    
    async def _find_similar_tickets(
        self, 
        ticket: Ticket, 
        jira_client: Optional[JiraClient] = None,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Find similar tickets using multiple approaches."""
        similar_tickets = []
        
        try:
            # Approach 1: Use Jira client for text-based similarity
            if jira_client:
                jira_similar = await jira_client.get_similar_tickets(
                    project_key=ticket.project_key,
                    title=ticket.title,
                    description=ticket.description or "",
                    limit=5
                )
                
                for jira_ticket in jira_similar:
                    similar_tickets.append({
                        'key': jira_ticket.get('key'),
                        'title': jira_ticket.get('fields', {}).get('summary', ''),
                        'description': self._extract_description(jira_ticket.get('fields', {})),
                        'status': jira_ticket.get('fields', {}).get('status', {}).get('name'),
                        'similarity_method': 'jira_text_search',
                        'similarity_score': 0.7  # Placeholder score
                    })
            
            # Approach 2: Use vector similarity search (if embeddings available)
            if db and hasattr(ticket, 'title_embedding') and ticket.title_embedding:
                vector_similar = await self.similarity_service.find_similar_by_embedding(
                    ticket, db, limit=3
                )
                
                for similar in vector_similar:
                    similar_tickets.append({
                        'key': similar['ticket_key'],
                        'title': similar['title'],
                        'description': similar['description'][:200] + '...',
                        'status': similar['status'],
                        'similarity_method': 'vector_embedding',
                        'similarity_score': similar['similarity_score']
                    })
            
            # Remove duplicates and sort by similarity score
            unique_tickets = {}
            for ticket_data in similar_tickets:
                key = ticket_data['key']
                if key not in unique_tickets or ticket_data['similarity_score'] > unique_tickets[key]['similarity_score']:
                    unique_tickets[key] = ticket_data
            
            return sorted(unique_tickets.values(), key=lambda x: x['similarity_score'], reverse=True)[:5]
            
        except Exception as e:
            logger.error(f"Error finding similar tickets: {e}")
            return []
    
    async def _search_documentation(self, ticket: Ticket) -> List[Dict[str, str]]:
        """Search for relevant documentation in Confluence."""
        try:
            confluence_client = ConfluenceClient.from_settings()
            if not confluence_client:
                logger.warning("Confluence client not configured")
                return []
            
            # Extract keywords from ticket
            keywords = self._extract_search_keywords(ticket.title, ticket.description or "")
            
            documentation_links = []
            for keyword in keywords[:5]:  # Search top 5 keywords
                results = await confluence_client.search_content(keyword, limit=2)
                
                for result in results:
                    documentation_links.append({
                        'title': result.get('title', ''),
                        'url': result.get('url', ''),
                        'excerpt': result.get('excerpt', ''),
                        'space': result.get('space', {}).get('name', ''),
                        'search_keyword': keyword
                    })
            
            # Remove duplicates
            unique_docs = {}
            for doc in documentation_links:
                url = doc['url']
                if url not in unique_docs:
                    unique_docs[url] = doc
            
            return list(unique_docs.values())[:5]  # Return top 5
            
        except Exception as e:
            logger.error(f"Error searching documentation: {e}")
            return []
    
    async def _analyze_code(self, ticket: Ticket) -> Optional[Dict[str, Any]]:
        """Analyze code repositories for potential fixes."""
        try:
            # Get project mapping to determine which repository to analyze
            from app.services.project_mapping.mapper import ProjectMapper
            mapper = ProjectMapper()
            
            project_mapping = await mapper.get_mapping_for_project(ticket.project_key)
            if not project_mapping:
                logger.warning(f"No repository mapping found for project {ticket.project_key}")
                return None
            
            # Initialize Git client
            git_client = GitClient(
                provider=project_mapping.git_provider,
                organization=project_mapping.git_organization,
                repository=project_mapping.git_repository
            )
            
            # Use code analyzer to find potential issues and fixes
            code_analysis = await self.code_analyzer.analyze_for_ticket(
                ticket=ticket,
                git_client=git_client,
                project_mapping=project_mapping
            )
            
            return code_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing code for ticket {ticket.jira_key}: {e}")
            return None
    
    def _calculate_confidence_score(self, analysis_result: Dict[str, Any]) -> float:
        """Calculate overall confidence score for the analysis."""
        score = 0.0
        max_score = 1.0
        
        # Similar tickets found (0.3 weight)
        similar_count = len(analysis_result.get('similar_tickets', []))
        if similar_count > 0:
            score += min(similar_count / 3.0, 1.0) * 0.3
        
        # Documentation found (0.2 weight)
        doc_count = len(analysis_result.get('documentation_links', []))
        if doc_count > 0:
            score += min(doc_count / 2.0, 1.0) * 0.2
        
        # Code analysis available (0.5 weight)
        code_analysis = analysis_result.get('code_analysis')
        if code_analysis and code_analysis.get('file_locations'):
            file_count = len(code_analysis['file_locations'])
            score += min(file_count / 2.0, 1.0) * 0.5
        
        return min(score, max_score)
    
    def _extract_description(self, fields: Dict[str, Any]) -> str:
        """Extract description text from Jira fields."""
        description = fields.get('description')
        if not description:
            return ""
        
        if isinstance(description, dict):
            # Handle ADF format
            return self._extract_text_from_adf(description)
        else:
            return str(description)[:200] + "..."
    
    def _extract_text_from_adf(self, adf_content: Dict[str, Any]) -> str:
        """Extract plain text from Atlassian Document Format."""
        try:
            def extract_text_recursive(node):
                text = ""
                if isinstance(node, dict):
                    if node.get('type') == 'text':
                        text += node.get('text', '')
                    elif 'content' in node:
                        for child in node['content']:
                            text += extract_text_recursive(child)
                return text
            
            return extract_text_recursive(adf_content).strip()[:200] + "..."
        except:
            return ""
    
    def _extract_search_keywords(self, title: str, description: str) -> List[str]:
        """Extract meaningful keywords for documentation search."""
        import re
        
        text = f"{title} {description}".lower()
        
        # Extract technical terms, error messages, component names
        patterns = [
            r'\b[a-zA-Z]+Exception\b',  # Exception names
            r'\b[a-zA-Z]+Error\b',      # Error names  
            r'\b[A-Z][a-zA-Z]*Service\b',  # Service names
            r'\b[A-Z][a-zA-Z]*Controller\b',  # Controller names
            r'\b[a-zA-Z]{4,}\b'         # General terms 4+ chars
        ]
        
        keywords = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            keywords.update(matches)
        
        # Remove common stop words
        stop_words = {'error', 'issue', 'problem', 'failed', 'cannot', 'unable', 'when', 'after', 'before'}
        keywords = [kw for kw in keywords if kw.lower() not in stop_words]
        
        return list(keywords)[:10]