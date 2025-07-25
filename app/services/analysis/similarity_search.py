"""
Similarity search service using vector embeddings and traditional text matching.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import json
from sentence_transformers import SentenceTransformer

from app.models.ticket import Ticket

logger = logging.getLogger(__name__)


class SimilaritySearchService:
    """Service for finding similar tickets using various similarity methods."""
    
    def __init__(self):
        # Initialize sentence transformer model for embeddings
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Sentence transformer model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load sentence transformer model: {e}")
            self.model = None
    
    async def find_similar_by_embedding(
        self, 
        target_ticket: Ticket, 
        db: Session, 
        limit: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Find similar tickets using vector embeddings."""
        try:
            if not self.model:
                logger.warning("Sentence transformer model not available")
                return []
            
            # Generate embedding for target ticket
            target_text = f"{target_ticket.title} {target_ticket.description or ''}"
            target_embedding = self.model.encode(target_text)
            
            # Store embedding in ticket if not already present
            if not target_ticket.title_embedding:
                target_ticket.title_embedding = json.dumps(target_embedding.tolist())
                db.commit()
            
            # For PostgreSQL with pgvector extension, we would use:
            # SELECT *, embedding <-> %s as distance FROM tickets ORDER BY distance LIMIT %s
            
            # For MVP without pgvector, we'll use a simple approach
            # In production, implement proper vector database integration
            
            similar_tickets = []
            
            # Query recent tickets from same project for comparison
            recent_tickets = db.query(Ticket).filter(
                Ticket.project_key == target_ticket.project_key,
                Ticket.id != target_ticket.id
            ).order_by(Ticket.created_at.desc()).limit(50).all()
            
            for ticket in recent_tickets:
                try:
                    # Generate embedding if not present
                    if not ticket.title_embedding:
                        ticket_text = f"{ticket.title} {ticket.description or ''}"
                        ticket_embedding = self.model.encode(ticket_text)
                        ticket.title_embedding = json.dumps(ticket_embedding.tolist())
                    else:
                        ticket_embedding = json.loads(ticket.title_embedding)
                    
                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(target_embedding, ticket_embedding)
                    
                    if similarity >= similarity_threshold:
                        similar_tickets.append({
                            'ticket_id': ticket.id,
                            'ticket_key': ticket.jira_key,
                            'title': ticket.title,
                            'description': ticket.description or '',
                            'status': ticket.status.value,
                            'similarity_score': float(similarity)
                        })
                
                except Exception as e:
                    logger.error(f"Error calculating similarity for ticket {ticket.jira_key}: {e}")
                    continue
            
            # Commit any new embeddings
            db.commit()
            
            # Sort by similarity and return top results
            similar_tickets.sort(key=lambda x: x['similarity_score'], reverse=True)
            return similar_tickets[:limit]
            
        except Exception as e:
            logger.error(f"Error finding similar tickets by embedding: {e}")
            return []
    
    async def find_similar_by_keywords(
        self, 
        target_ticket: Ticket, 
        db: Session, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar tickets using keyword matching."""
        try:
            # Extract keywords from target ticket
            keywords = self._extract_keywords(target_ticket.title, target_ticket.description or '')
            
            if not keywords:
                return []
            
            similar_tickets = []
            
            # Search for tickets containing similar keywords
            for keyword in keywords[:5]:  # Use top 5 keywords
                # Use PostgreSQL full-text search or simple LIKE queries
                query = text("""
                    SELECT id, jira_key, title, description, status
                    FROM tickets 
                    WHERE project_key = :project_key 
                    AND id != :target_id
                    AND (
                        title ILIKE :keyword 
                        OR description ILIKE :keyword
                    )
                    ORDER BY created_at DESC
                    LIMIT :limit
                """)
                
                results = db.execute(query, {
                    'project_key': target_ticket.project_key,
                    'target_id': target_ticket.id,
                    'keyword': f'%{keyword}%',
                    'limit': limit
                })
                
                for row in results:
                    # Calculate simple keyword match score
                    match_score = self._calculate_keyword_score(
                        target_ticket.title, 
                        target_ticket.description or '',
                        row.title,
                        row.description or ''
                    )
                    
                    similar_tickets.append({
                        'ticket_id': row.id,
                        'ticket_key': row.jira_key,
                        'title': row.title,
                        'description': row.description or '',
                        'status': row.status,
                        'similarity_score': match_score,
                        'matching_keyword': keyword
                    })
            
            # Remove duplicates and sort by score
            unique_tickets = {}
            for ticket in similar_tickets:
                key = ticket['ticket_id']
                if key not in unique_tickets or ticket['similarity_score'] > unique_tickets[key]['similarity_score']:
                    unique_tickets[key] = ticket
            
            result = list(unique_tickets.values())
            result.sort(key=lambda x: x['similarity_score'], reverse=True)
            return result[:limit]
            
        except Exception as e:
            logger.error(f"Error finding similar tickets by keywords: {e}")
            return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            import numpy as np
            
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)
            
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def _extract_keywords(self, title: str, description: str) -> List[str]:
        """Extract meaningful keywords from ticket text."""
        import re
        
        text = f"{title} {description}".lower()
        
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'cannot', 'not', 'no', 'yes'
        }
        
        # Extract meaningful terms
        words = re.findall(r'\b[a-zA-Z0-9]{3,}\b', text)
        keywords = [word for word in words if word not in stop_words]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for keyword in keywords:
            if keyword not in seen:
                seen.add(keyword)
                unique_keywords.append(keyword)
        
        return unique_keywords[:15]  # Return top 15 keywords
    
    def _calculate_keyword_score(self, title1: str, desc1: str, title2: str, desc2: str) -> float:
        """Calculate similarity score based on keyword overlap."""
        try:
            keywords1 = set(self._extract_keywords(title1, desc1))
            keywords2 = set(self._extract_keywords(title2, desc2))
            
            if not keywords1 or not keywords2:
                return 0.0
            
            # Calculate Jaccard similarity
            intersection = len(keywords1.intersection(keywords2))
            union = len(keywords1.union(keywords2))
            
            return intersection / union if union > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating keyword score: {e}")
            return 0.0