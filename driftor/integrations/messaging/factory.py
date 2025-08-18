"""
Messaging platform factory and integration manager.
"""
from typing import Dict, Optional
import structlog

from .base import BaseMessagingPlatform, MessagePlatform, MessageCard, MessageResponse
from .teams import TeamsBot
from .slack import SlackBot
from driftor.integrations.base import IntegrationConfig
from driftor.security.encryption import get_encryption_manager

logger = structlog.get_logger(__name__)


class MessagingFactory:
    """Factory for creating messaging platform instances."""
    
    @staticmethod
    def create_platform(
        platform_type: MessagePlatform,
        tenant_id: str,
        credentials: Dict[str, str],
        api_base_url: Optional[str] = None
    ) -> BaseMessagingPlatform:
        """Create a messaging platform instance."""
        
        # Set default API base URLs
        default_urls = {
            MessagePlatform.TEAMS: "https://graph.microsoft.com/v1.0",
            MessagePlatform.SLACK: "https://slack.com/api"
        }
        
        # Create integration config
        config = IntegrationConfig(
            tenant_id=tenant_id,
            integration_type=f"messaging_{platform_type.value}",
            api_base_url=api_base_url or default_urls.get(platform_type, ""),
            timeout_seconds=30,
            max_retries=3,
            retry_delay_seconds=1
        )
        
        # Create platform instance
        if platform_type == MessagePlatform.TEAMS:
            return TeamsBot(config, credentials)
        elif platform_type == MessagePlatform.SLACK:
            return SlackBot(config, credentials)
        else:
            raise ValueError(f"Unsupported messaging platform: {platform_type}")
    
    @staticmethod
    async def create_from_tenant_config(
        tenant_id: str,
        platform_name: str,
        db_session
    ) -> Optional[BaseMessagingPlatform]:
        """Create platform from tenant configuration stored in database."""
        try:
            # TODO: Implement when integration configuration models are ready
            logger.warning(
                "Tenant messaging configuration not implemented yet",
                tenant_id=tenant_id,
                platform=platform_name
            )
            return None
            
        except Exception as e:
            logger.error(
                "Failed to create messaging platform from tenant config",
                tenant_id=tenant_id,
                platform=platform_name,
                error=str(e)
            )
            return None


class MessagingManager:
    """Manager for messaging integrations across multiple platforms."""
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.encryption_manager = get_encryption_manager()
        self._platform_cache: Dict[str, BaseMessagingPlatform] = {}
    
    def _get_cache_key(self, tenant_id: str, platform_name: str) -> str:
        """Generate cache key for platform instances."""
        return f"{tenant_id}:{platform_name}"
    
    async def get_platform(
        self, 
        tenant_id: str, 
        platform_name: str,
        force_refresh: bool = False
    ) -> Optional[BaseMessagingPlatform]:
        """Get or create a messaging platform for a tenant."""
        cache_key = self._get_cache_key(tenant_id, platform_name)
        
        # Check cache first
        if not force_refresh and cache_key in self._platform_cache:
            platform = self._platform_cache[cache_key]
            
            # Test if platform is still working
            if await platform.test_connection():
                return platform
            else:
                # Remove from cache if connection failed
                del self._platform_cache[cache_key]
        
        # Create new platform
        platform = await MessagingFactory.create_from_tenant_config(
            tenant_id, platform_name, self.db_session
        )
        
        if platform:
            # Test connection before caching
            if await platform.test_connection():
                self._platform_cache[cache_key] = platform
                return platform
            else:
                logger.warning(
                    "Messaging platform connection test failed",
                    tenant_id=tenant_id,
                    platform=platform_name
                )
        
        return None
    
    async def get_all_platforms(self, tenant_id: str) -> Dict[str, BaseMessagingPlatform]:
        """Get all configured messaging platforms for a tenant."""
        platforms = {}
        
        # TODO: Query database for all configured messaging integrations for tenant
        # For now, return empty dict
        
        return platforms
    
    async def get_primary_platform(self, tenant_id: str) -> Optional[BaseMessagingPlatform]:
        """Get the primary messaging platform for a tenant."""
        platforms = await self.get_all_platforms(tenant_id)
        
        # TODO: Implement platform priority logic
        # For now, return first available platform
        for platform_name, platform in platforms.items():
            if await platform.test_connection():
                return platform
        
        return None
    
    async def send_notification_to_user(
        self,
        tenant_id: str,
        user_id: str,
        ticket_data: Dict[str, any],
        analysis_results: Dict[str, any],
        preferred_platform: Optional[str] = None
    ) -> Dict[str, MessageResponse]:
        """Send notification to user across available platforms."""
        results = {}
        
        if preferred_platform:
            # Send to specific platform
            platform = await self.get_platform(tenant_id, preferred_platform)
            if platform:
                response = await platform.send_analysis_notification(
                    user_id, ticket_data, analysis_results, tenant_id
                )
                results[preferred_platform] = response
        else:
            # Send to primary platform
            platform = await self.get_primary_platform(tenant_id)
            if platform:
                response = await platform.send_analysis_notification(
                    user_id, ticket_data, analysis_results, tenant_id
                )
                results[platform.platform.value] = response
        
        return results
    
    async def send_error_notification(
        self,
        tenant_id: str,
        user_id: str,
        error_message: str,
        ticket_key: Optional[str] = None,
        preferred_platform: Optional[str] = None
    ) -> Dict[str, MessageResponse]:
        """Send error notification to user."""
        results = {}
        
        if preferred_platform:
            platform = await self.get_platform(tenant_id, preferred_platform)
            if platform:
                response = await platform.send_error_notification(
                    user_id, error_message, ticket_key, tenant_id
                )
                results[preferred_platform] = response
        else:
            platform = await self.get_primary_platform(tenant_id)
            if platform:
                response = await platform.send_error_notification(
                    user_id, error_message, ticket_key, tenant_id
                )
                results[platform.platform.value] = response
        
        return results
    
    async def handle_interaction(
        self,
        tenant_id: str,
        platform_name: str,
        interaction_data: Dict[str, any]
    ) -> Dict[str, any]:
        """Handle interactive component interactions."""
        try:
            platform = await self.get_platform(tenant_id, platform_name)
            if not platform:
                return {"status": "error", "error": "Platform not found"}
            
            return await platform.handle_interaction(interaction_data)
            
        except Exception as e:
            logger.error(
                "Failed to handle interaction",
                tenant_id=tenant_id,
                platform=platform_name,
                error=str(e)
            )
            return {"status": "error", "error": str(e)}
    
    async def test_all_connections(self, tenant_id: str) -> Dict[str, bool]:
        """Test connections for all messaging platforms for a tenant."""
        platforms = await self.get_all_platforms(tenant_id)
        results = {}
        
        for name, platform in platforms.items():
            try:
                results[name] = await platform.test_connection()
            except Exception as e:
                logger.error(
                    "Messaging platform connection test failed",
                    tenant_id=tenant_id,
                    platform=name,
                    error=str(e)
                )
                results[name] = False
        
        return results
    
    async def get_health_status(self, tenant_id: str) -> Dict[str, any]:
        """Get health status of all messaging integrations."""
        platforms = await self.get_all_platforms(tenant_id)
        
        status = {
            "total_platforms": len(platforms),
            "healthy_platforms": 0,
            "platforms": {}
        }
        
        for platform_name, platform in platforms.items():
            try:
                health = await platform.health_check()
                status["platforms"][platform_name] = health
                
                if health.get("healthy", False):
                    status["healthy_platforms"] += 1
                    
            except Exception as e:
                status["platforms"][platform_name] = {
                    "healthy": False,
                    "error": str(e)
                }
        
        return status
    
    def clear_cache(self, tenant_id: Optional[str] = None) -> None:
        """Clear platform cache."""
        if tenant_id:
            # Clear cache for specific tenant
            keys_to_remove = [
                key for key in self._platform_cache.keys() 
                if key.startswith(f"{tenant_id}:")
            ]
            for key in keys_to_remove:
                del self._platform_cache[key]
        else:
            # Clear all cache
            self._platform_cache.clear()


# Global instance
_messaging_manager: Optional[MessagingManager] = None


def get_messaging_manager(db_session=None) -> MessagingManager:
    """Get global messaging manager."""
    global _messaging_manager
    
    if _messaging_manager is None:
        _messaging_manager = MessagingManager(db_session)
    elif db_session and not _messaging_manager.db_session:
        _messaging_manager.db_session = db_session
    
    return _messaging_manager