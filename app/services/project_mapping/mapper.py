"""
Project mapping service for linking Jira projects to Git repositories.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import logging

from app.core.database import SessionLocal
from app.models.project_mapping import ProjectMapping, MappingConfidence
from app.services.integrations.jira_client import JiraClient
from app.services.integrations.git_client import GitClient

logger = logging.getLogger(__name__)


class ProjectMapper:
    """Service for managing project-to-repository mappings."""
    
    def __init__(self):
        pass
    
    async def get_mapping_for_project(self, project_key: str) -> Optional[ProjectMapping]:
        """Get the repository mapping for a Jira project."""
        try:
            db = SessionLocal()
            
            try:
                mapping = db.query(ProjectMapping).filter(
                    ProjectMapping.jira_project_key == project_key,
                    ProjectMapping.is_active == True
                ).first()
                
                return mapping
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting mapping for project {project_key}: {e}")
            return None
    
    async def create_mapping(
        self,
        jira_project_key: str,
        jira_project_name: str,
        jira_project_id: str,
        git_provider: str,
        git_organization: str,
        git_repository: str,
        confidence_score: float = 1.0,
        mapping_algorithm: str = "manual",
        user_id: Optional[int] = None
    ) -> Optional[ProjectMapping]:
        """Create a new project mapping."""
        try:
            db = SessionLocal()
            
            try:
                # Determine confidence level
                if confidence_score >= 0.85:
                    confidence_level = MappingConfidence.HIGH
                elif confidence_score >= 0.60:
                    confidence_level = MappingConfidence.MEDIUM
                else:
                    confidence_level = MappingConfidence.LOW
                
                mapping = ProjectMapping(
                    jira_project_key=jira_project_key,
                    jira_project_name=jira_project_name,
                    jira_project_id=jira_project_id,
                    git_provider=git_provider,
                    git_organization=git_organization,
                    git_repository=git_repository,
                    confidence_score=confidence_score,
                    confidence_level=confidence_level,
                    mapping_algorithm=mapping_algorithm,
                    created_by_id=user_id,
                    is_verified=(confidence_level == MappingConfidence.HIGH)
                )
                
                db.add(mapping)
                db.commit()
                db.refresh(mapping)
                
                logger.info(f"Created mapping: {jira_project_key} -> {git_organization}/{git_repository}")
                return mapping
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error creating mapping: {e}")
            return None
    
    async def auto_discover_mappings(
        self, 
        jira_client: Optional[JiraClient] = None,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Automatically discover project-to-repository mappings."""
        try:
            if not jira_client:
                jira_client = JiraClient.from_settings()
                if not jira_client:
                    logger.error("Jira client not available for auto-discovery")
                    return []
            
            discovered_mappings = []
            
            # Get all Jira projects (this would require implementing get_projects in JiraClient)
            # For MVP, we'll use a placeholder approach
            
            # Example mapping logic (simplified for MVP)
            sample_projects = [
                {
                    'key': 'WEBAPP',
                    'name': 'Web Application',
                    'id': 'project-id-1'
                },
                {
                    'key': 'API',
                    'name': 'API Service',
                    'id': 'project-id-2'
                }
            ]
            
            for project in sample_projects:
                project_key = project['key']
                
                # Check if mapping already exists
                existing = await self.get_mapping_for_project(project_key)
                if existing:
                    continue
                
                # Try to find matching repository
                suggested_mappings = await self._find_matching_repositories(project)
                
                if suggested_mappings:
                    best_match = suggested_mappings[0]
                    
                    # Create mapping if confidence is high enough
                    if best_match['confidence_score'] >= 0.85:
                        mapping = await self.create_mapping(
                            jira_project_key=project_key,
                            jira_project_name=project['name'],
                            jira_project_id=project['id'],
                            git_provider=best_match['provider'],
                            git_organization=best_match['organization'],
                            git_repository=best_match['repository'],
                            confidence_score=best_match['confidence_score'],
                            mapping_algorithm="auto_discovery",
                            user_id=user_id
                        )
                        
                        if mapping:
                            discovered_mappings.append({
                                'project_key': project_key,
                                'mapping_id': mapping.id,
                                'confidence': best_match['confidence_score'],
                                'repository': f"{best_match['organization']}/{best_match['repository']}"
                            })
            
            return discovered_mappings
            
        except Exception as e:
            logger.error(f"Error in auto-discovery: {e}")
            return []
    
    async def _find_matching_repositories(self, jira_project: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find potential repository matches for a Jira project."""
        try:
            project_key = jira_project['key'].lower()
            project_name = jira_project['name'].lower()
            
            # For MVP, implement a simple name-based matching
            # In production, this would query GitHub/GitLab APIs
            
            potential_matches = []
            
            # Sample repository data (in production, this would come from Git APIs)
            sample_repos = [
                {
                    'provider': 'github',
                    'organization': 'mycompany',
                    'repository': 'webapp-frontend',
                    'description': 'Web application frontend'
                },
                {
                    'provider': 'github',
                    'organization': 'mycompany',
                    'repository': 'api-service',
                    'description': 'Main API service'
                }
            ]
            
            for repo in sample_repos:
                repo_name = repo['repository'].lower()
                repo_desc = repo.get('description', '').lower()
                
                confidence_score = self._calculate_matching_confidence(
                    project_key, project_name, repo_name, repo_desc
                )
                
                if confidence_score > 0.3:  # Only consider reasonable matches
                    potential_matches.append({
                        'provider': repo['provider'],
                        'organization': repo['organization'],
                        'repository': repo['repository'],
                        'confidence_score': confidence_score,
                        'matching_factors': {
                            'name_similarity': self._name_similarity(project_key, repo_name),
                            'description_match': project_key in repo_desc or any(
                                word in repo_desc for word in project_name.split()
                            )
                        }
                    })
            
            # Sort by confidence score
            potential_matches.sort(key=lambda x: x['confidence_score'], reverse=True)
            return potential_matches
            
        except Exception as e:
            logger.error(f"Error finding matching repositories: {e}")
            return []
    
    def _calculate_matching_confidence(
        self, 
        project_key: str, 
        project_name: str, 
        repo_name: str, 
        repo_desc: str
    ) -> float:
        """Calculate confidence score for project-repository matching."""
        try:
            score = 0.0
            
            # Name similarity (40% weight)
            name_sim = self._name_similarity(project_key, repo_name)
            score += name_sim * 0.4
            
            # Project name in repo name or description (30% weight)
            project_words = project_name.split()
            name_word_matches = sum(1 for word in project_words if word in repo_name)
            desc_word_matches = sum(1 for word in project_words if word in repo_desc)
            
            word_match_score = (name_word_matches + desc_word_matches * 0.5) / len(project_words)
            score += min(word_match_score, 1.0) * 0.3
            
            # Project key in repo name (30% weight)
            if project_key in repo_name:
                score += 0.3
            elif any(part in repo_name for part in project_key.split('-')):
                score += 0.15
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating matching confidence: {e}")
            return 0.0
    
    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate simple name similarity score."""
        try:
            # Simple Levenshtein-like similarity
            if name1 == name2:
                return 1.0
            
            # Check for substring matches
            if name1 in name2 or name2 in name1:
                shorter = min(len(name1), len(name2))
                longer = max(len(name1), len(name2))
                return shorter / longer
            
            # Check for word overlap
            words1 = set(name1.replace('-', ' ').replace('_', ' ').split())
            words2 = set(name2.replace('-', ' ').replace('_', ' ').split())
            
            if words1 and words2:
                intersection = len(words1.intersection(words2))
                union = len(words1.union(words2))
                return intersection / union if union > 0 else 0.0
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating name similarity: {e}")
            return 0.0