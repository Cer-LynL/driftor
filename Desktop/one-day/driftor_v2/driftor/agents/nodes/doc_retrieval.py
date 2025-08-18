"""
Documentation retrieval agent for finding relevant documentation and knowledge base articles.
"""
import re
from typing import Dict, List, Optional, Any, Tuple
import structlog
from datetime import datetime

from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class DocumentationRetriever:
    """Agent for retrieving relevant documentation and knowledge base articles."""
    
    def __init__(self, confluence_client=None, vector_db_client=None):
        self.confluence_client = confluence_client
        self.vector_db_client = vector_db_client
        
        # Search configuration
        self.max_results = 8
        self.relevance_threshold = 0.6
        
        # Documentation source priorities
        self.source_priorities = {
            'confluence': 1.0,
            'wiki': 0.9,
            'readme': 0.8,
            'api_docs': 0.9,
            'troubleshooting': 1.0,
            'knowledge_base': 0.95
        }
        
        # Documentation type patterns
        self.doc_type_patterns = {
            'troubleshooting': [
                r'troubleshooting', r'debugging', r'known issues', r'faq',
                r'common problems', r'error resolution', r'fixes'
            ],
            'api_documentation': [
                r'api', r'endpoint', r'rest', r'graphql', r'swagger',
                r'openapi', r'integration guide'
            ],
            'setup_guide': [
                r'setup', r'installation', r'configuration', r'deployment',
                r'getting started', r'quick start'
            ],
            'best_practices': [
                r'best practices', r'guidelines', r'standards', r'conventions',
                r'coding standards', r'architecture'
            ],
            'user_manual': [
                r'user guide', r'manual', r'how to', r'tutorial',
                r'walkthrough', r'step by step'
            ]
        }
    
    async def retrieve_documentation(
        self, 
        ticket_data: Dict[str, Any], 
        classification: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Retrieve relevant documentation for the ticket."""
        try:
            ticket_key = ticket_data.get("key", "")
            
            # Prepare search context
            search_context = self._prepare_doc_search_context(ticket_data, classification)
            
            # Perform multi-source documentation search
            documentation = await self._multi_source_search(
                search_context, tenant_id
            )
            
            # Rank and filter results
            ranked_docs = self._rank_documentation_results(
                documentation, search_context
            )
            
            # Categorize documentation by type
            categorized_docs = self._categorize_documentation(ranked_docs)
            
            # Audit the documentation retrieval
            await audit(
                event_type=AuditEventType.DATA_ACCESSED,
                tenant_id=tenant_id,
                resource_type="documentation_retrieval",
                resource_id=ticket_key,
                details={
                    "search_component": search_context.get("component"),
                    "search_keywords": search_context.get("keywords", []),
                    "total_results": len(ranked_docs),
                    "sources_searched": list(self.source_priorities.keys())
                }
            )
            
            logger.info(
                "Documentation retrieval completed",
                ticket_key=ticket_key,
                results_count=len(ranked_docs),
                tenant_id=tenant_id
            )
            
            return {
                "documentation": ranked_docs,
                "categorized_docs": categorized_docs,
                "search_metadata": {
                    "search_component": search_context.get("component"),
                    "search_keywords": search_context.get("keywords", []),
                    "total_results": len(ranked_docs),
                    "relevance_threshold": self.relevance_threshold
                }
            }
            
        except Exception as e:
            logger.error(
                "Documentation retrieval failed",
                ticket_key=ticket_data.get("key", "unknown"),
                error=str(e),
                exc_info=True
            )
            
            return {
                "documentation": [],
                "categorized_docs": {},
                "search_metadata": {
                    "error": str(e),
                    "total_results": 0
                }
            }
    
    def _prepare_doc_search_context(
        self, 
        ticket_data: Dict[str, Any], 
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare search context for documentation retrieval."""
        summary = ticket_data.get("summary", "")
        description = ticket_data.get("description", "")
        
        # Extract technology/framework terms
        tech_terms = self._extract_technology_terms(f"{summary} {description}")
        
        # Build search terms prioritizing technical keywords
        search_terms = []
        keywords = classification.get("keywords", [])
        
        # Add high-priority technical terms
        search_terms.extend(tech_terms[:3])
        
        # Add classification keywords
        search_terms.extend(keywords[:5])
        
        # Add component
        component = classification.get("component", "")
        if component and component != "unknown":
            search_terms.append(component)
        
        return {
            "ticket_key": ticket_data.get("key", ""),
            "summary": summary,
            "description": description,
            "component": component,
            "keywords": keywords,
            "search_terms": list(set(search_terms)),  # Remove duplicates
            "severity": classification.get("severity", "unknown"),
            "is_bug": classification.get("is_bug", False),
            "technology_terms": tech_terms
        }
    
    def _extract_technology_terms(self, text: str) -> List[str]:
        """Extract technology and framework terms from text."""
        tech_patterns = [
            # Programming languages
            r'\b(java|python|javascript|typescript|c#|php|ruby|go|rust|kotlin|swift)\b',
            # Frameworks
            r'\b(react|angular|vue|spring|django|flask|express|laravel|rails)\b',
            # Databases
            r'\b(mysql|postgresql|mongodb|redis|elasticsearch|oracle|sqlite)\b',
            # Infrastructure
            r'\b(docker|kubernetes|aws|azure|gcp|jenkins|nginx|apache)\b',
            # APIs and protocols
            r'\b(rest|graphql|soap|http|https|oauth|jwt|api)\b',
            # Tools and libraries
            r'\b(git|maven|gradle|npm|yarn|webpack|babel|junit|pytest)\b'
        ]
        
        found_terms = []
        text_lower = text.lower()
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            found_terms.extend(matches)
        
        return list(set(found_terms))  # Remove duplicates
    
    async def _multi_source_search(
        self, 
        search_context: Dict[str, Any], 
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Search across multiple documentation sources."""
        all_docs = []
        
        # 1. Confluence search
        if self.confluence_client:
            confluence_docs = await self._search_confluence(search_context, tenant_id)
            all_docs.extend(confluence_docs)
        
        # 2. Vector database search (for indexed documentation)
        if self.vector_db_client:
            vector_docs = await self._search_vector_docs(search_context, tenant_id)
            all_docs.extend(vector_docs)
        
        # 3. Knowledge base search (simulated for now)
        kb_docs = await self._search_knowledge_base(search_context, tenant_id)
        all_docs.extend(kb_docs)
        
        # 4. API documentation search
        api_docs = await self._search_api_documentation(search_context, tenant_id)
        all_docs.extend(api_docs)
        
        return all_docs
    
    async def _search_confluence(
        self, 
        search_context: Dict[str, Any], 
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Search Confluence for relevant documentation."""
        try:
            if not self.confluence_client:
                return []
            
            search_terms = search_context.get("search_terms", [])
            if not search_terms:
                return []
            
            # Build Confluence CQL query
            cql_query = self._build_confluence_cql(search_terms, search_context)
            
            # Execute search
            results = await self.confluence_client.search_content(
                cql=cql_query,
                limit=self.max_results,
                excerpt="highlight"
            )
            
            confluence_docs = []
            for result in results.get("results", []):
                confluence_docs.append({
                    "title": result.get("title", ""),
                    "url": result.get("_links", {}).get("webui", ""),
                    "excerpt": result.get("excerpt", ""),
                    "content": result.get("body", {}).get("storage", {}).get("value", ""),
                    "space": result.get("space", {}).get("name", ""),
                    "last_modified": result.get("version", {}).get("when", ""),
                    "author": result.get("version", {}).get("by", {}).get("displayName", ""),
                    "source": "confluence",
                    "doc_type": self._detect_doc_type(result.get("title", "")),
                    "relevance_score": 0.0  # Will be calculated later
                })
            
            return confluence_docs
            
        except Exception as e:
            logger.warning(
                "Confluence search failed",
                error=str(e),
                tenant_id=tenant_id
            )
            return []
    
    def _build_confluence_cql(
        self, 
        search_terms: List[str], 
        search_context: Dict[str, Any]
    ) -> str:
        """Build Confluence CQL query."""
        # Escape and quote search terms
        quoted_terms = [f'"{term}"' for term in search_terms[:5]]  # Limit terms
        
        # Build basic text search
        text_query = " AND ".join(quoted_terms)
        
        # Add space restrictions if component is known
        component = search_context.get("component", "")
        space_filter = ""
        if component and component != "unknown":
            space_filter = f' AND space.title ~ "{component}"'
        
        # Prioritize certain content types
        type_filter = ' AND type in ("page", "blogpost")'
        
        return f"text ~ \"{text_query}\"{space_filter}{type_filter}"
    
    async def _search_vector_docs(
        self, 
        search_context: Dict[str, Any], 
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Search vector database for documentation."""
        try:
            if not self.vector_db_client:
                return []
            
            # Create search query from context
            search_query = " ".join(search_context.get("search_terms", []))
            
            # Search documentation collection
            results = await self.vector_db_client.similarity_search(
                collection_name=f"documentation_{tenant_id}",
                query_text=search_query,
                n_results=self.max_results,
                where={"doc_type": {"$in": ["troubleshooting", "api_docs", "best_practices"]}}
            )
            
            vector_docs = []
            for result in results.get("documents", []):
                metadata = result.get("metadata", {})
                vector_docs.append({
                    "title": metadata.get("title", ""),
                    "url": metadata.get("url", ""),
                    "excerpt": result.get("document", "")[:300] + "...",
                    "content": result.get("document", ""),
                    "source": metadata.get("source", "vector_db"),
                    "doc_type": metadata.get("doc_type", "unknown"),
                    "last_modified": metadata.get("last_modified", ""),
                    "relevance_score": 1.0 - result.get("distance", 0.0)
                })
            
            return vector_docs
            
        except Exception as e:
            logger.warning(
                "Vector documentation search failed",
                error=str(e),
                tenant_id=tenant_id
            )
            return []
    
    async def _search_knowledge_base(
        self, 
        search_context: Dict[str, Any], 
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Search knowledge base articles (simulated for MVP)."""
        # This would integrate with actual knowledge base systems
        # For now, return simulated results based on component and keywords
        
        component = search_context.get("component", "")
        keywords = search_context.get("keywords", [])
        
        if not component or component == "unknown":
            return []
        
        # Simulated knowledge base articles
        kb_articles = [
            {
                "title": f"{component.title()} Troubleshooting Guide",
                "url": f"https://kb.company.com/{component}-troubleshooting",
                "excerpt": f"Common issues and solutions for {component} component...",
                "content": f"This guide covers troubleshooting steps for {component} related issues.",
                "source": "knowledge_base",
                "doc_type": "troubleshooting",
                "last_modified": "2024-01-15T10:00:00Z",
                "author": "Documentation Team",
                "relevance_score": 0.8
            },
            {
                "title": f"{component.title()} Best Practices",
                "url": f"https://kb.company.com/{component}-best-practices",
                "excerpt": f"Best practices and coding standards for {component}...",
                "content": f"Follow these best practices when working with {component}.",
                "source": "knowledge_base", 
                "doc_type": "best_practices",
                "last_modified": "2024-01-10T14:30:00Z",
                "author": "Architecture Team",
                "relevance_score": 0.7
            }
        ]
        
        # Filter based on keywords
        if any(kw for kw in keywords if "error" in kw.lower() or "exception" in kw.lower()):
            kb_articles[0]["relevance_score"] = 0.9  # Boost troubleshooting guide
        
        return kb_articles
    
    async def _search_api_documentation(
        self, 
        search_context: Dict[str, Any], 
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Search API documentation (simulated for MVP)."""
        keywords = search_context.get("keywords", [])
        component = search_context.get("component", "")
        
        # Check if this seems API-related
        api_indicators = ["api", "endpoint", "rest", "http", "request", "response"]
        is_api_related = any(
            indicator in keyword.lower() 
            for keyword in keywords 
            for indicator in api_indicators
        )
        
        if not is_api_related:
            return []
        
        # Simulated API documentation
        api_docs = [
            {
                "title": f"{component.title()} API Reference",
                "url": f"https://docs.company.com/api/{component}",
                "excerpt": f"API endpoints and examples for {component} service...",
                "content": f"Complete API reference for {component} including authentication, endpoints, and examples.",
                "source": "api_docs",
                "doc_type": "api_documentation",
                "last_modified": "2024-01-20T09:00:00Z",
                "author": "API Team",
                "relevance_score": 0.85
            },
            {
                "title": "API Error Handling Guide",
                "url": "https://docs.company.com/api/error-handling",
                "excerpt": "How to handle API errors and common response codes...",
                "content": "Guide to handling API errors, status codes, and retry logic.",
                "source": "api_docs",
                "doc_type": "troubleshooting",
                "last_modified": "2024-01-18T16:20:00Z",
                "author": "API Team",
                "relevance_score": 0.8
            }
        ]
        
        return api_docs
    
    def _detect_doc_type(self, title: str) -> str:
        """Detect documentation type from title."""
        title_lower = title.lower()
        
        for doc_type, patterns in self.doc_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, title_lower):
                    return doc_type
        
        return "general"
    
    def _rank_documentation_results(
        self, 
        documentation: List[Dict[str, Any]], 
        search_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Rank documentation results by relevance."""
        for doc in documentation:
            if doc.get("relevance_score", 0) == 0:
                # Calculate relevance if not already set
                doc["relevance_score"] = self._calculate_doc_relevance(doc, search_context)
        
        # Sort by relevance score (descending)
        documentation.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # Filter by threshold and limit results
        filtered_docs = [
            doc for doc in documentation 
            if doc.get("relevance_score", 0) >= self.relevance_threshold
        ][:self.max_results]
        
        # Add ranking metadata
        for i, doc in enumerate(filtered_docs):
            doc["rank"] = i + 1
            doc["relevance_reason"] = self._generate_relevance_reason(doc, search_context)
        
        return filtered_docs
    
    def _calculate_doc_relevance(
        self, 
        doc: Dict[str, Any], 
        search_context: Dict[str, Any]
    ) -> float:
        """Calculate relevance score for a document."""
        score = 0.0
        
        # Base score from source priority
        source = doc.get("source", "")
        source_score = self.source_priorities.get(source, 0.5)
        score += source_score * 0.3
        
        # Title relevance
        title = doc.get("title", "").lower()
        search_terms = search_context.get("search_terms", [])
        
        title_matches = sum(
            1 for term in search_terms 
            if term.lower() in title
        )
        if search_terms:
            title_relevance = title_matches / len(search_terms)
            score += title_relevance * 0.4
        
        # Content relevance (simplified)
        content = f"{doc.get('excerpt', '')} {doc.get('content', '')}".lower()
        content_matches = sum(
            1 for term in search_terms 
            if term.lower() in content
        )
        if search_terms:
            content_relevance = min(content_matches / len(search_terms), 1.0)
            score += content_relevance * 0.2
        
        # Doc type bonus
        doc_type = doc.get("doc_type", "")
        is_bug = search_context.get("is_bug", False)
        
        if is_bug and doc_type == "troubleshooting":
            score += 0.1  # Boost troubleshooting docs for bugs
        elif doc_type == "api_documentation" and any(
            "api" in term.lower() for term in search_terms
        ):
            score += 0.1  # Boost API docs for API-related issues
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _generate_relevance_reason(
        self, 
        doc: Dict[str, Any], 
        search_context: Dict[str, Any]
    ) -> str:
        """Generate human-readable reason for relevance."""
        reasons = []
        
        # Check title matches
        title = doc.get("title", "").lower()
        search_terms = search_context.get("search_terms", [])
        
        matching_terms = [
            term for term in search_terms 
            if term.lower() in title
        ]
        
        if matching_terms:
            reasons.append(f"matches '{', '.join(matching_terms[:2])}'")
        
        # Check doc type relevance
        doc_type = doc.get("doc_type", "")
        if doc_type == "troubleshooting":
            reasons.append("troubleshooting guide")
        elif doc_type == "api_documentation":
            reasons.append("API documentation")
        elif doc_type == "best_practices":
            reasons.append("best practices guide")
        
        # Check source quality
        source = doc.get("source", "")
        if source == "confluence":
            reasons.append("official documentation")
        elif source == "knowledge_base":
            reasons.append("knowledge base article")
        
        if not reasons:
            reasons.append("general relevance")
        
        return " and ".join(reasons)
    
    def _categorize_documentation(
        self, 
        documentation: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize documentation by type."""
        categories = {
            "troubleshooting": [],
            "api_documentation": [],
            "best_practices": [],
            "setup_guide": [],
            "user_manual": [],
            "general": []
        }
        
        for doc in documentation:
            doc_type = doc.get("doc_type", "general")
            if doc_type in categories:
                categories[doc_type].append(doc)
            else:
                categories["general"].append(doc)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}