"""
LLM factory and management with fallback support.
"""
from typing import Dict, List, Optional, Any
import structlog

from .base import BaseLLMProvider, LLMProvider, LLMRequest, LLMResponse
from .ollama_client import OllamaClient
from .openai_client import OpenAIClient
from driftor.core.config import get_settings

logger = structlog.get_logger(__name__)


class LLMFactory:
    """Factory for creating LLM provider instances."""
    
    @staticmethod
    def create_provider(
        provider_type: LLMProvider,
        config: Dict[str, Any]
    ) -> BaseLLMProvider:
        """Create an LLM provider instance."""
        
        if provider_type == LLMProvider.OLLAMA:
            return OllamaClient(config)
        elif provider_type == LLMProvider.OPENAI:
            return OpenAIClient(config)
        elif provider_type == LLMProvider.AZURE_OPENAI:
            # Azure OpenAI uses the same client as OpenAI with different config
            return OpenAIClient(config)
        elif provider_type == LLMProvider.ANTHROPIC:
            # TODO: Implement Anthropic client
            raise NotImplementedError("Anthropic client not yet implemented")
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_type}")


class LLMManager:
    """Manager for LLM operations with fallback support."""
    
    def __init__(self):
        self.settings = get_settings()
        self._primary_provider: Optional[BaseLLMProvider] = None
        self._fallback_providers: List[BaseLLMProvider] = []
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize LLM providers."""
        try:
            providers_config = self._get_providers_config()
            
            # Initialize primary provider (Ollama)
            if providers_config.get("ollama"):
                ollama_provider = LLMFactory.create_provider(
                    LLMProvider.OLLAMA,
                    providers_config["ollama"]
                )
                
                if await ollama_provider.connect():
                    self._primary_provider = ollama_provider
                    logger.info("Primary LLM provider (Ollama) initialized")
                else:
                    logger.warning("Failed to connect to primary LLM provider (Ollama)")
            
            # Initialize fallback providers
            fallback_providers = []
            
            # OpenAI fallback
            if providers_config.get("openai"):
                try:
                    openai_provider = LLMFactory.create_provider(
                        LLMProvider.OPENAI,
                        providers_config["openai"]
                    )
                    
                    if await openai_provider.connect():
                        fallback_providers.append(openai_provider)
                        logger.info("OpenAI fallback provider initialized")
                except Exception as e:
                    logger.warning("Failed to initialize OpenAI fallback", error=str(e))
            
            # Azure OpenAI fallback (if configured separately)
            if providers_config.get("azure_openai"):
                try:
                    azure_provider = LLMFactory.create_provider(
                        LLMProvider.AZURE_OPENAI,
                        providers_config["azure_openai"]
                    )
                    
                    if await azure_provider.connect():
                        fallback_providers.append(azure_provider)
                        logger.info("Azure OpenAI fallback provider initialized")
                except Exception as e:
                    logger.warning("Failed to initialize Azure OpenAI fallback", error=str(e))
            
            self._fallback_providers = fallback_providers
            self._initialized = True
            
            logger.info(
                "LLM manager initialized",
                primary_available=self._primary_provider is not None,
                fallback_count=len(self._fallback_providers)
            )
            
            return True
            
        except Exception as e:
            logger.error("LLM manager initialization failed", error=str(e))
            return False
    
    def _get_providers_config(self) -> Dict[str, Dict[str, Any]]:
        """Get configuration for all LLM providers."""
        config = {}
        
        # Ollama configuration
        config["ollama"] = {
            "host": self.settings.llm.ollama_host,
            "model": self.settings.llm.ollama_model,
            "max_tokens": self.settings.llm.max_tokens,
            "temperature": self.settings.llm.temperature,
            "timeout": 120,
            "max_retries": 3
        }
        
        # OpenAI configuration
        if self.settings.llm.openai_api_key:
            config["openai"] = {
                "api_key": self.settings.llm.openai_api_key,
                "model": self.settings.llm.openai_model,
                "max_tokens": self.settings.llm.max_tokens,
                "temperature": self.settings.llm.temperature,
                "max_retries": 3
            }
        
        return config
    
    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate response with fallback support."""
        if not self._initialized:
            await self.initialize()
        
        # Try primary provider first
        if self._primary_provider:
            try:
                response = await self._primary_provider.generate_response(request)
                if response.success and response.confidence >= self.settings.llm.confidence_threshold:
                    return response
                else:
                    logger.info(
                        "Primary provider response below confidence threshold",
                        confidence=response.confidence,
                        threshold=self.settings.llm.confidence_threshold
                    )
            except Exception as e:
                logger.warning(
                    "Primary LLM provider failed, trying fallbacks",
                    error=str(e)
                )
        
        # Try fallback providers
        for i, provider in enumerate(self._fallback_providers):
            try:
                logger.info(f"Trying fallback provider {i + 1}")
                response = await provider.generate_response(request)
                
                if response.success:
                    logger.info(
                        "Fallback provider succeeded",
                        provider_index=i + 1,
                        confidence=response.confidence
                    )
                    return response
                    
            except Exception as e:
                logger.warning(
                    f"Fallback provider {i + 1} failed",
                    error=str(e)
                )
                continue
        
        # All providers failed
        logger.error("All LLM providers failed")
        return LLMResponse(
            content="I'm sorry, but I'm currently unable to process your request. Please try again later.",
            confidence=0.0,
            provider="none",
            model="none",
            tokens_used=0,
            processing_time=0.0,
            success=False,
            error="All LLM providers unavailable"
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all LLM providers."""
        health_status = {
            "overall_healthy": False,
            "primary_provider": None,
            "fallback_providers": [],
            "available_providers": 0
        }
        
        # Check primary provider
        if self._primary_provider:
            try:
                primary_health = await self._primary_provider.health_check()
                health_status["primary_provider"] = primary_health
                if primary_health.get("healthy"):
                    health_status["available_providers"] += 1
            except Exception as e:
                health_status["primary_provider"] = {
                    "healthy": False,
                    "error": str(e)
                }
        
        # Check fallback providers
        for i, provider in enumerate(self._fallback_providers):
            try:
                fallback_health = await provider.health_check()
                health_status["fallback_providers"].append({
                    "index": i,
                    "provider": fallback_health.get("provider", "unknown"),
                    "healthy": fallback_health.get("healthy", False),
                    "status": fallback_health.get("status", "unknown")
                })
                if fallback_health.get("healthy"):
                    health_status["available_providers"] += 1
            except Exception as e:
                health_status["fallback_providers"].append({
                    "index": i,
                    "healthy": False,
                    "error": str(e)
                })
        
        health_status["overall_healthy"] = health_status["available_providers"] > 0
        
        return health_status
    
    async def get_available_models(self) -> Dict[str, List[str]]:
        """Get available models from all providers."""
        models = {}
        
        if self._primary_provider:
            try:
                models["primary"] = self._primary_provider.get_supported_models()
            except Exception as e:
                logger.warning("Failed to get primary provider models", error=str(e))
                models["primary"] = []
        
        models["fallback"] = []
        for i, provider in enumerate(self._fallback_providers):
            try:
                provider_models = provider.get_supported_models()
                models["fallback"].extend(provider_models)
            except Exception as e:
                logger.warning(f"Failed to get fallback provider {i} models", error=str(e))
        
        return models
    
    async def disconnect(self) -> None:
        """Disconnect from all LLM providers."""
        if self._primary_provider:
            try:
                await self._primary_provider.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting primary provider", error=str(e))
        
        for provider in self._fallback_providers:
            try:
                await provider.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting fallback provider", error=str(e))
        
        self._primary_provider = None
        self._fallback_providers = []
        self._initialized = False
        
        logger.info("LLM manager disconnected")
    
    def is_available(self) -> bool:
        """Check if any LLM provider is available."""
        if self._primary_provider and self._primary_provider.is_connected():
            return True
        
        return any(provider.is_connected() for provider in self._fallback_providers)


# Global instance
_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Get global LLM manager."""
    global _llm_manager
    
    if _llm_manager is None:
        _llm_manager = LLMManager()
    
    return _llm_manager


class LLMService:
    """High-level service for LLM operations."""
    
    def __init__(self):
        self.manager = get_llm_manager()
    
    async def analyze_code(
        self,
        ticket_data: Dict[str, Any],
        classification: Dict[str, Any],
        code_files: List[Dict[str, Any]],
        similar_tickets: List[Dict[str, Any]],
        documentation: List[Dict[str, Any]],
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> LLMResponse:
        """Analyze code and generate insights."""
        
        # Prepare context
        context = {
            "ticket_key": ticket_data.get("key", ""),
            "summary": ticket_data.get("summary", ""),
            "description": ticket_data.get("description", ""),
            "component": classification.get("component", "unknown"),
            "severity": classification.get("severity", "unknown"),
            "code_files": self._format_code_files(code_files),
            "similar_tickets": self._format_similar_tickets(similar_tickets),
            "documentation": self._format_documentation(documentation)
        }
        
        # Create request
        request = LLMRequest(
            prompt="",  # Will be filled by template
            context=context,
            prompt_type=PromptType.CODE_ANALYSIS,
            system_message="You are an expert software engineer analyzing bug reports and code. Provide detailed technical analysis.",
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        return await self.manager.generate_response(request)
    
    async def generate_fix_suggestions(
        self,
        ticket_data: Dict[str, Any],
        code_analysis: str,
        relevant_files: List[Dict[str, Any]],
        similar_fixes: List[Dict[str, Any]],
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> LLMResponse:
        """Generate fix suggestions for the issue."""
        
        context = {
            "ticket_key": ticket_data.get("key", ""),
            "summary": ticket_data.get("summary", ""),
            "description": ticket_data.get("description", ""),
            "component": ticket_data.get("component", "unknown"),
            "code_analysis": code_analysis,
            "relevant_files": self._format_code_files(relevant_files),
            "similar_fixes": self._format_similar_fixes(similar_fixes)
        }
        
        request = LLMRequest(
            prompt="",
            context=context,
            prompt_type=PromptType.FIX_GENERATION,
            system_message="You are an expert software engineer generating precise fix suggestions. Focus on actionable solutions.",
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        return await self.manager.generate_response(request)
    
    async def chat_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        ticket_context: Optional[Dict[str, Any]] = None,
        analysis_context: Optional[Dict[str, Any]] = None,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> LLMResponse:
        """Generate chat response for user interaction."""
        
        context = {
            "user_message": user_message,
            "conversation_history": self._format_conversation_history(conversation_history),
            "ticket_key": ticket_context.get("key", "") if ticket_context else "",
            "analysis_results": analysis_context or {},
            "code_context": ticket_context or {}
        }
        
        request = LLMRequest(
            prompt="",
            context=context,
            prompt_type=PromptType.CHAT_RESPONSE,
            system_message="You are Driftor, a helpful AI assistant for developers. Be concise but informative.",
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        return await self.manager.generate_response(request)
    
    def _format_code_files(self, code_files: List[Dict[str, Any]]) -> str:
        """Format code files for LLM context."""
        if not code_files:
            return "No code files available."
        
        formatted = []
        for file_info in code_files[:5]:  # Limit to top 5 files
            path = file_info.get("path", "unknown")
            content = file_info.get("content", "")[:2000]  # Truncate large files
            
            formatted.append(f"**{path}:**\n```\n{content}\n```\n")
        
        return "\n".join(formatted)
    
    def _format_similar_tickets(self, similar_tickets: List[Dict[str, Any]]) -> str:
        """Format similar tickets for LLM context."""
        if not similar_tickets:
            return "No similar tickets found."
        
        formatted = []
        for ticket in similar_tickets[:3]:  # Limit to top 3
            metadata = ticket.get("metadata", {})
            key = metadata.get("ticket_key", "unknown")
            summary = metadata.get("summary", "")
            
            formatted.append(f"- **{key}**: {summary}")
        
        return "\n".join(formatted)
    
    def _format_documentation(self, documentation: List[Dict[str, Any]]) -> str:
        """Format documentation for LLM context."""
        if not documentation:
            return "No relevant documentation found."
        
        formatted = []
        for doc in documentation[:3]:  # Limit to top 3
            metadata = doc.get("metadata", {})
            title = metadata.get("title", "Unknown Document")
            url = metadata.get("url", "")
            
            formatted.append(f"- **{title}**: {url}")
        
        return "\n".join(formatted)
    
    def _format_similar_fixes(self, similar_fixes: List[Dict[str, Any]]) -> str:
        """Format similar fixes for LLM context."""
        if not similar_fixes:
            return "No similar fixes available."
        
        formatted = []
        for fix in similar_fixes[:3]:
            formatted.append(f"- {fix.get('description', 'Fix description not available')}")
        
        return "\n".join(formatted)
    
    def _format_conversation_history(self, history: List[Dict[str, str]]) -> str:
        """Format conversation history for LLM context."""
        if not history:
            return "No previous conversation."
        
        formatted = []
        for msg in history[-5:]:  # Last 5 messages
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:500]  # Truncate long messages
            
            formatted.append(f"{role.title()}: {content}")
        
        return "\n".join(formatted)


# Service instance
def get_llm_service() -> LLMService:
    """Get LLM service."""
    return LLMService()


from .base import PromptType