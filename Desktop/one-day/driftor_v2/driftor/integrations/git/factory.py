"""
Git provider factory for creating provider instances.
"""
from typing import Dict, Optional
import structlog

from .base import BaseGitProvider, GitProvider
from .github import GitHubProvider
from .gitlab import GitLabProvider
from .gitea import GiteaProvider
from driftor.integrations.base import IntegrationConfig
from driftor.models.tenant import Tenant
from driftor.security.encryption import get_encryption_manager

logger = structlog.get_logger(__name__)


class GitProviderFactory:
    """Factory for creating Git provider instances."""
    
    @staticmethod
    def create_provider(
        provider_type: GitProvider,
        tenant_id: str,
        credentials: Dict[str, str],
        api_base_url: Optional[str] = None
    ) -> BaseGitProvider:
        """Create a Git provider instance."""
        
        # Set default API base URLs
        default_urls = {
            GitProvider.GITHUB: "https://api.github.com",
            GitProvider.GITLAB: "https://gitlab.com/api/v4",
            GitProvider.GITEA: "https://gitea.com"  # Will be overridden for self-hosted
        }
        
        # Create integration config
        config = IntegrationConfig(
            tenant_id=tenant_id,
            integration_type=f"git_{provider_type.value}",
            api_base_url=api_base_url or default_urls.get(provider_type, ""),
            timeout_seconds=30,
            max_retries=3,
            retry_delay_seconds=1
        )
        
        # Create provider instance
        if provider_type == GitProvider.GITHUB:
            return GitHubProvider(config, credentials)
        elif provider_type == GitProvider.GITLAB:
            return GitLabProvider(config, credentials)
        elif provider_type == GitProvider.GITEA:
            return GiteaProvider(config, credentials)
        else:
            raise ValueError(f"Unsupported Git provider: {provider_type}")
    
    @staticmethod
    async def create_from_tenant_config(
        tenant_id: str,
        provider_name: str,
        db_session
    ) -> Optional[BaseGitProvider]:
        """Create provider from tenant configuration stored in database."""
        try:
            # TODO: Implement when integration configuration models are ready
            # This would query the database for tenant's Git integration config
            
            # For now, return None - this will be implemented when we add
            # the integration configuration models
            logger.warning(
                "Tenant Git configuration not implemented yet",
                tenant_id=tenant_id,
                provider=provider_name
            )
            return None
            
        except Exception as e:
            logger.error(
                "Failed to create Git provider from tenant config",
                tenant_id=tenant_id,
                provider=provider_name,
                error=str(e)
            )
            return None


class GitIntegrationManager:
    """Manager for Git integrations across multiple providers."""
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.encryption_manager = get_encryption_manager()
        self._provider_cache: Dict[str, BaseGitProvider] = {}
    
    def _get_cache_key(self, tenant_id: str, provider_name: str) -> str:
        """Generate cache key for provider instances."""
        return f"{tenant_id}:{provider_name}"
    
    async def get_provider(
        self, 
        tenant_id: str, 
        provider_name: str,
        force_refresh: bool = False
    ) -> Optional[BaseGitProvider]:
        """Get or create a Git provider for a tenant."""
        cache_key = self._get_cache_key(tenant_id, provider_name)
        
        # Check cache first
        if not force_refresh and cache_key in self._provider_cache:
            provider = self._provider_cache[cache_key]
            
            # Test if provider is still working
            if await provider.test_connection():
                return provider
            else:
                # Remove from cache if connection failed
                del self._provider_cache[cache_key]
        
        # Create new provider
        provider = await GitProviderFactory.create_from_tenant_config(
            tenant_id, provider_name, self.db_session
        )
        
        if provider:
            # Test connection before caching
            if await provider.test_connection():
                self._provider_cache[cache_key] = provider
                return provider
            else:
                logger.warning(
                    "Git provider connection test failed",
                    tenant_id=tenant_id,
                    provider=provider_name
                )
        
        return None
    
    async def get_all_providers(self, tenant_id: str) -> Dict[str, BaseGitProvider]:
        """Get all configured Git providers for a tenant."""
        providers = {}
        
        # TODO: Query database for all configured Git integrations for tenant
        # For now, return empty dict
        
        return providers
    
    async def test_all_connections(self, tenant_id: str) -> Dict[str, bool]:
        """Test connections for all Git providers for a tenant."""
        providers = await self.get_all_providers(tenant_id)
        results = {}
        
        for name, provider in providers.items():
            try:
                results[name] = await provider.test_connection()
            except Exception as e:
                logger.error(
                    "Git provider connection test failed",
                    tenant_id=tenant_id,
                    provider=name,
                    error=str(e)
                )
                results[name] = False
        
        return results
    
    async def find_repository(
        self, 
        tenant_id: str, 
        repo_identifier: str
    ) -> Optional[tuple[BaseGitProvider, str]]:
        """Find a repository across all configured providers."""
        providers = await self.get_all_providers(tenant_id)
        
        for provider_name, provider in providers.items():
            try:
                # Try to get repository
                repo = await provider.get_repository(repo_identifier)
                if repo:
                    return provider, repo.id
                
                # Also try searching by name in repositories list
                repos = await provider.list_repositories(limit=100)
                for repo in repos:
                    if (repo_identifier.lower() in repo.name.lower() or 
                        repo_identifier.lower() in repo.full_name.lower()):
                        return provider, repo.id
                        
            except Exception as e:
                logger.warning(
                    "Failed to search repository in provider",
                    tenant_id=tenant_id,
                    provider=provider_name,
                    repo_identifier=repo_identifier,
                    error=str(e)
                )
                continue
        
        return None
    
    async def search_code_across_providers(
        self,
        tenant_id: str,
        query: str,
        repository_filter: Optional[str] = None,
        limit_per_provider: int = 10
    ) -> Dict[str, list]:
        """Search code across all configured Git providers."""
        providers = await self.get_all_providers(tenant_id)
        results = {}
        
        for provider_name, provider in providers.items():
            try:
                provider_results = []
                
                # Get repositories to search
                if repository_filter:
                    # Search specific repository
                    repo_results = await provider.search_code(
                        repository_filter, query, limit=limit_per_provider
                    )
                    provider_results.extend(repo_results)
                else:
                    # Search across all accessible repositories
                    repos = await provider.list_repositories(limit=20)
                    
                    for repo in repos[:5]:  # Limit to avoid rate limits
                        try:
                            repo_results = await provider.search_code(
                                repo.id, query, limit=5
                            )
                            provider_results.extend(repo_results)
                            
                            if len(provider_results) >= limit_per_provider:
                                break
                                
                        except Exception as e:
                            logger.warning(
                                "Failed to search in repository",
                                repo=repo.name,
                                error=str(e)
                            )
                            continue
                
                if provider_results:
                    results[provider_name] = provider_results
                    
            except Exception as e:
                logger.error(
                    "Failed to search code in provider",
                    tenant_id=tenant_id,
                    provider=provider_name,
                    error=str(e)
                )
                continue
        
        return results
    
    async def get_health_status(self, tenant_id: str) -> Dict[str, any]:
        """Get health status of all Git integrations."""
        providers = await self.get_all_providers(tenant_id)
        
        status = {
            "total_providers": len(providers),
            "healthy_providers": 0,
            "providers": {}
        }
        
        for provider_name, provider in providers.items():
            try:
                health = await provider.health_check()
                status["providers"][provider_name] = health
                
                if health.get("healthy", False):
                    status["healthy_providers"] += 1
                    
            except Exception as e:
                status["providers"][provider_name] = {
                    "healthy": False,
                    "error": str(e)
                }
        
        return status
    
    def clear_cache(self, tenant_id: Optional[str] = None) -> None:
        """Clear provider cache."""
        if tenant_id:
            # Clear cache for specific tenant
            keys_to_remove = [
                key for key in self._provider_cache.keys() 
                if key.startswith(f"{tenant_id}:")
            ]
            for key in keys_to_remove:
                del self._provider_cache[key]
        else:
            # Clear all cache
            self._provider_cache.clear()


# Global instance
_git_manager: Optional[GitIntegrationManager] = None


def get_git_manager(db_session=None) -> GitIntegrationManager:
    """Get global Git integration manager."""
    global _git_manager
    
    if _git_manager is None:
        _git_manager = GitIntegrationManager(db_session)
    elif db_session and not _git_manager.db_session:
        _git_manager.db_session = db_session
    
    return _git_manager