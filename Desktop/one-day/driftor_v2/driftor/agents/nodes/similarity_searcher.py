"""
Similarity search agent for finding related tickets and issues.
"""
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import text

from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class SimilaritySearcher:
    """Agent for finding similar tickets and issues."""
    
    def __init__(self, db_session: Session = None, vector_db_client=None):
        self.db_session = db_session
        self.vector_db_client = vector_db_client
        
        # Search configuration
        self.similarity_threshold = 0.7
        self.max_results = 10
        self.time_window_months = 24
        
        # Weight factors for different similarity types
        self.similarity_weights = {
            'semantic': 0.4,      # Vector similarity of text content
            'keyword': 0.3,       # Shared technical keywords
            'component': 0.2,     # Same component/technology area
            'error_pattern': 0.1  # Similar error patterns
        }
    
    async def find_similar_tickets(
        self, 
        ticket_data: Dict[str, Any], 
        classification: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Find tickets similar to the current one."""
        try:
            ticket_key = ticket_data.get("key", "")
            
            # Prepare search context
            search_context = self._prepare_search_context(ticket_data, classification)
            
            # Perform hybrid search
            similar_tickets = await self._hybrid_search(
                search_context, tenant_id, ticket_key
            )
            
            # Calculate relevance scores
            scored_tickets = self._calculate_relevance_scores(
                similar_tickets, search_context
            )
            
            # Filter and rank results
            final_results = self._filter_and_rank_results(
                scored_tickets, search_context
            )
            
            # Audit the search
            await audit(
                event_type=AuditEventType.DATA_ACCESSED,
                tenant_id=tenant_id,
                resource_type="similarity_search",
                resource_id=ticket_key,
                details={
                    "search_type": "ticket_similarity",
                    "results_count": len(final_results),
                    "similarity_threshold": self.similarity_threshold,
                    "search_component": search_context.get("component", "unknown")
                }
            )
            
            logger.info(
                "Similarity search completed",
                ticket_key=ticket_key,
                results_count=len(final_results),
                tenant_id=tenant_id
            )
            
            return {
                "similar_tickets": final_results,
                "search_metadata": {
                    "total_candidates": len(similar_tickets),
                    "filtered_results": len(final_results),
                    "search_component": search_context.get("component"),
                    "search_keywords": search_context.get("keywords", []),
                    "similarity_threshold": self.similarity_threshold
                }
            }
            
        except Exception as e:
            logger.error(
                "Similarity search failed",
                ticket_key=ticket_data.get("key", "unknown"),
                error=str(e),
                exc_info=True
            )
            
            return {
                "similar_tickets": [],
                "search_metadata": {
                    "error": str(e),
                    "total_candidates": 0,
                    "filtered_results": 0
                }
            }
    
    def _prepare_search_context(
        self, 
        ticket_data: Dict[str, Any], 
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare search context from ticket and classification data."""
        summary = ticket_data.get("summary", "")
        description = ticket_data.get("description", "") 
        
        return {
            "ticket_key": ticket_data.get("key", ""),
            "summary": summary,
            "description": description,
            "full_text": f"{summary} {description}",
            "component": classification.get("component", "unknown"),
            "severity": classification.get("severity", "unknown"),
            "keywords": classification.get("keywords", []),
            "issue_type": ticket_data.get("issue_type", ""),
            "priority": ticket_data.get("priority", ""),
            "labels": ticket_data.get("labels", []),
            "created": ticket_data.get("created"),
            "is_bug": classification.get("is_bug", False)
        }
    
    async def _hybrid_search(
        self, 
        search_context: Dict[str, Any], 
        tenant_id: str,
        current_ticket_key: str
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining multiple search strategies."""
        candidates = []
        
        # 1. Vector similarity search (if vector DB available)
        if self.vector_db_client:
            vector_results = await self._vector_similarity_search(
                search_context, tenant_id, current_ticket_key
            )
            candidates.extend(vector_results)
        
        # 2. Full-text search in database
        text_results = await self._text_similarity_search(
            search_context, tenant_id, current_ticket_key
        )
        candidates.extend(text_results)
        
        # 3. Component-based search
        component_results = await self._component_similarity_search(
            search_context, tenant_id, current_ticket_key
        )
        candidates.extend(component_results)
        
        # 4. Error pattern search
        if search_context.get("keywords"):
            error_results = await self._error_pattern_search(
                search_context, tenant_id, current_ticket_key
            )
            candidates.extend(error_results)
        
        # Deduplicate by ticket key
        unique_candidates = {}
        for candidate in candidates:
            key = candidate.get("key")
            if key and key not in unique_candidates:
                unique_candidates[key] = candidate
        
        return list(unique_candidates.values())
    
    async def _vector_similarity_search(
        self, 
        search_context: Dict[str, Any], 
        tenant_id: str,
        current_ticket_key: str
    ) -> List[Dict[str, Any]]:
        """Search using vector embeddings (semantic similarity)."""
        try:
            if not self.vector_db_client:
                return []
            
            # Create embedding for search text
            search_text = search_context["full_text"]
            
            # Query vector database
            # This would use ChromaDB or similar vector database
            results = await self.vector_db_client.similarity_search(
                collection_name=f"tickets_{tenant_id}",
                query_text=search_text,
                n_results=self.max_results * 2,  # Get more for filtering
                where={"ticket_key": {"$ne": current_ticket_key}}
            )
            
            # Convert to standard format
            vector_candidates = []
            for result in results.get("documents", []):
                vector_candidates.append({
                    "key": result.get("metadata", {}).get("ticket_key"),
                    "summary": result.get("metadata", {}).get("summary", ""),
                    "description": result.get("metadata", {}).get("description", ""),
                    "component": result.get("metadata", {}).get("component", ""),
                    "similarity_score": result.get("distance", 0.0),
                    "search_type": "vector"
                })
            
            return vector_candidates
            
        except Exception as e:
            logger.warning(
                "Vector similarity search failed",
                error=str(e),
                tenant_id=tenant_id
            )
            return []
    
    async def _text_similarity_search(
        self, 
        search_context: Dict[str, Any], 
        tenant_id: str,
        current_ticket_key: str
    ) -> List[Dict[str, Any]]:
        """Search using full-text search in database."""
        try:
            if not self.db_session:
                return []
            
            # Build search terms from keywords and component
            search_terms = []
            if search_context.get("keywords"):
                search_terms.extend(search_context["keywords"][:5])  # Limit terms
            
            if search_context.get("component") != "unknown":
                search_terms.append(search_context["component"])
            
            if not search_terms:
                return []
            
            # Create PostgreSQL full-text search query
            search_query = " | ".join(search_terms)  # OR search
            
            # Calculate time window
            cutoff_date = datetime.now() - timedelta(days=30 * self.time_window_months)
            
            # Execute search query
            sql = text("""
                SELECT 
                    ticket_key,
                    summary,
                    description,
                    component,
                    severity,
                    created_at,
                    ts_rank_cd(
                        to_tsvector('english', summary || ' ' || COALESCE(description, '')),
                        plainto_tsquery('english', :search_query)
                    ) as text_similarity
                FROM tickets 
                WHERE tenant_id = :tenant_id
                    AND ticket_key != :current_key
                    AND created_at >= :cutoff_date
                    AND (
                        to_tsvector('english', summary || ' ' || COALESCE(description, ''))
                        @@ plainto_tsquery('english', :search_query)
                    )
                ORDER BY text_similarity DESC
                LIMIT :max_results
            """)
            
            result = self.db_session.execute(sql, {
                "search_query": search_query,
                "tenant_id": tenant_id,
                "current_key": current_ticket_key,
                "cutoff_date": cutoff_date,
                "max_results": self.max_results
            })
            
            text_candidates = []
            for row in result:
                text_candidates.append({
                    "key": row.ticket_key,
                    "summary": row.summary,
                    "description": row.description or "",
                    "component": row.component or "unknown",
                    "severity": row.severity or "unknown",
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "similarity_score": float(row.text_similarity or 0.0),
                    "search_type": "text"
                })
            
            return text_candidates
            
        except Exception as e:
            logger.warning(
                "Text similarity search failed",
                error=str(e),
                tenant_id=tenant_id
            )
            return []
    
    async def _component_similarity_search(
        self, 
        search_context: Dict[str, Any], 
        tenant_id: str,
        current_ticket_key: str
    ) -> List[Dict[str, Any]]:
        """Search for tickets in the same component/technology area."""
        try:
            if not self.db_session:
                return []
            
            component = search_context.get("component", "")
            if component == "unknown" or not component:
                return []
            
            # Calculate time window
            cutoff_date = datetime.now() - timedelta(days=30 * self.time_window_months)
            
            sql = text("""
                SELECT 
                    ticket_key,
                    summary,
                    description,
                    component,
                    severity,
                    created_at,
                    1.0 as component_similarity
                FROM tickets 
                WHERE tenant_id = :tenant_id
                    AND ticket_key != :current_key
                    AND component = :component
                    AND created_at >= :cutoff_date
                    AND is_resolved = true
                ORDER BY created_at DESC
                LIMIT :max_results
            """)
            
            result = self.db_session.execute(sql, {
                "tenant_id": tenant_id,
                "current_key": current_ticket_key,
                "component": component,
                "cutoff_date": cutoff_date,
                "max_results": self.max_results // 2
            })
            
            component_candidates = []
            for row in result:
                component_candidates.append({
                    "key": row.ticket_key,
                    "summary": row.summary,
                    "description": row.description or "",
                    "component": row.component,
                    "severity": row.severity or "unknown",
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "similarity_score": 1.0,  # Perfect component match
                    "search_type": "component"
                })
            
            return component_candidates
            
        except Exception as e:
            logger.warning(
                "Component similarity search failed",
                error=str(e),
                tenant_id=tenant_id
            )
            return []
    
    async def _error_pattern_search(
        self, 
        search_context: Dict[str, Any], 
        tenant_id: str,
        current_ticket_key: str
    ) -> List[Dict[str, Any]]:
        """Search for tickets with similar error patterns."""
        try:
            if not self.db_session:
                return []
            
            keywords = search_context.get("keywords", [])
            error_keywords = [kw for kw in keywords if any(
                error_term in kw.lower() 
                for error_term in ['error', 'exception', 'fail', 'timeout', 'null']
            )]
            
            if not error_keywords:
                return []
            
            # Build search for error patterns
            error_query = " | ".join(error_keywords[:3])  # Limit to top 3 error keywords
            
            cutoff_date = datetime.now() - timedelta(days=30 * self.time_window_months)
            
            sql = text("""
                SELECT 
                    ticket_key,
                    summary,
                    description,
                    component,
                    severity,
                    created_at,
                    ts_rank_cd(
                        to_tsvector('english', summary || ' ' || COALESCE(description, '')),
                        plainto_tsquery('english', :error_query)
                    ) as error_similarity
                FROM tickets 
                WHERE tenant_id = :tenant_id
                    AND ticket_key != :current_key
                    AND created_at >= :cutoff_date
                    AND is_resolved = true
                    AND (
                        to_tsvector('english', summary || ' ' || COALESCE(description, ''))
                        @@ plainto_tsquery('english', :error_query)
                    )
                ORDER BY error_similarity DESC
                LIMIT :max_results
            """)
            
            result = self.db_session.execute(sql, {
                "error_query": error_query,
                "tenant_id": tenant_id,
                "current_key": current_ticket_key,
                "cutoff_date": cutoff_date,
                "max_results": self.max_results // 2
            })
            
            error_candidates = []
            for row in result:
                error_candidates.append({
                    "key": row.ticket_key,
                    "summary": row.summary,
                    "description": row.description or "",
                    "component": row.component or "unknown",
                    "severity": row.severity or "unknown",
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "similarity_score": float(row.error_similarity or 0.0),
                    "search_type": "error_pattern"
                })
            
            return error_candidates
            
        except Exception as e:
            logger.warning(
                "Error pattern search failed",
                error=str(e),
                tenant_id=tenant_id
            )
            return []
    
    def _calculate_relevance_scores(
        self, 
        candidates: List[Dict[str, Any]], 
        search_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate composite relevance scores for candidates."""
        for candidate in candidates:
            # Initialize scores
            scores = {
                'semantic': 0.0,
                'keyword': 0.0,
                'component': 0.0,
                'error_pattern': 0.0
            }
            
            # Semantic similarity (from vector search or text search)
            if candidate.get("search_type") == "vector":
                scores['semantic'] = candidate.get("similarity_score", 0.0)
            elif candidate.get("search_type") == "text":
                scores['semantic'] = min(candidate.get("similarity_score", 0.0) / 0.5, 1.0)
            
            # Keyword similarity
            candidate_text = f"{candidate.get('summary', '')} {candidate.get('description', '')}"
            keyword_score = self._calculate_keyword_similarity(
                search_context.get("keywords", []), candidate_text
            )
            scores['keyword'] = keyword_score
            
            # Component similarity
            if candidate.get("component") == search_context.get("component"):
                scores['component'] = 1.0
            elif candidate.get("component", "unknown") != "unknown":
                scores['component'] = 0.3  # Partial credit for having a component
            
            # Error pattern similarity
            if candidate.get("search_type") == "error_pattern":
                scores['error_pattern'] = min(candidate.get("similarity_score", 0.0), 1.0)
            
            # Calculate composite score
            composite_score = sum(
                scores[score_type] * weight 
                for score_type, weight in self.similarity_weights.items()
            )
            
            candidate["relevance_score"] = composite_score
            candidate["score_breakdown"] = scores
        
        return candidates
    
    def _calculate_keyword_similarity(self, search_keywords: List[str], candidate_text: str) -> float:
        """Calculate keyword-based similarity score."""
        if not search_keywords:
            return 0.0
        
        candidate_text_lower = candidate_text.lower()
        matching_keywords = sum(
            1 for keyword in search_keywords 
            if keyword.lower() in candidate_text_lower
        )
        
        return matching_keywords / len(search_keywords)
    
    def _filter_and_rank_results(
        self, 
        candidates: List[Dict[str, Any]], 
        search_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Filter and rank final results."""
        # Filter by minimum similarity threshold
        filtered = [
            candidate for candidate in candidates 
            if candidate.get("relevance_score", 0.0) >= self.similarity_threshold
        ]
        
        # Sort by relevance score (descending)
        filtered.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
        
        # Limit results
        final_results = filtered[:self.max_results]
        
        # Add additional metadata
        for i, result in enumerate(final_results):
            result["rank"] = i + 1
            result["similarity_reason"] = self._generate_similarity_reason(
                result, search_context
            )
        
        return final_results
    
    def _generate_similarity_reason(
        self, 
        result: Dict[str, Any], 
        search_context: Dict[str, Any]
    ) -> str:
        """Generate human-readable reason for similarity."""
        reasons = []
        
        scores = result.get("score_breakdown", {})
        
        if scores.get("component", 0) >= 0.8:
            reasons.append("same component")
        
        if scores.get("keyword", 0) >= 0.5:
            reasons.append("similar technical keywords")
        
        if scores.get("semantic", 0) >= 0.7:
            reasons.append("similar description")
        
        if scores.get("error_pattern", 0) >= 0.5:
            reasons.append("similar error patterns")
        
        if result.get("search_type") == "component":
            reasons.append("resolved in same component")
        
        if not reasons:
            reasons.append("general similarity")
        
        return " and ".join(reasons)