"""
Background tasks for project mapping and auto-discovery.
"""
from celery import current_task
from typing import Dict, Any
import logging

from app.tasks.celery_app import celery_app
from app.services.project_mapping.mapper import ProjectMapper
from app.services.integrations.jira_client import JiraClient

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def auto_discover_project_mappings(self, user_id: int = None) -> Dict[str, Any]:
    """Auto-discover project-to-repository mappings."""
    try:
        current_task.update_state(state='PROGRESS', meta={'step': 'Starting auto-discovery'})
        
        # Initialize services
        mapper = ProjectMapper()
        jira_client = JiraClient.from_settings()
        
        if not jira_client:
            raise ValueError("Jira client not configured")
        
        current_task.update_state(state='PROGRESS', meta={'step': 'Discovering mappings'})
        
        # Run auto-discovery
        import asyncio
        discovered_mappings = asyncio.run(mapper.auto_discover_mappings(
            jira_client=jira_client,
            user_id=user_id
        ))
        
        return {
            'status': 'completed',
            'discovered_count': len(discovered_mappings),
            'mappings': discovered_mappings,
            'user_id': user_id
        }
        
    except Exception as e:
        logger.error(f"Error in auto-discovery task: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise


@celery_app.task(bind=True)
def verify_project_mapping(self, mapping_id: int, user_id: int, verified: bool = True) -> Dict[str, Any]:
    """Verify or reject a project mapping."""
    try:
        current_task.update_state(state='PROGRESS', meta={'step': 'Verifying mapping'})
        
        # This would update the mapping verification status
        # Implementation would go here
        
        return {
            'status': 'completed',
            'mapping_id': mapping_id,
            'verified': verified,
            'verified_by': user_id
        }
        
    except Exception as e:
        logger.error(f"Error verifying mapping {mapping_id}: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'mapping_id': mapping_id}
        )
        raise