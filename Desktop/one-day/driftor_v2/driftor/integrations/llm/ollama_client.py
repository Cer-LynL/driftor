"""
Ollama LLM client for on-premises deployment.
"""
import time
import json
from typing import Dict, List, Optional, Any
import httpx
import structlog

from .base import BaseLLMProvider, LLMRequest, LLMResponse, LLMProvider, PromptTemplates
from .base import LLMError, ConnectionError, GenerationError, RateLimitError, ModelNotFoundError
from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class OllamaClient(BaseLLMProvider):
    """Ollama LLM client implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        self.base_url = config.get("host", "http://localhost:11434").rstrip("/")
        self.default_model = config.get("model", "llama3.1:8b")
        self.timeout = config.get("timeout", 120)
        self.max_retries = config.get("max_retries", 3)
        
        # Default parameters
        self.default_max_tokens = config.get("max_tokens", 4000)
        self.default_temperature = config.get("temperature", 0.1)
        
        self.provider_type = LLMProvider.OLLAMA
        
        # HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
    
    async def connect(self) -> bool:
        """Connect to Ollama server."""
        try:
            # Test connection with a simple request
            response = await self.client.get(f"{self.base_url}/api/tags")
            
            if response.status_code == 200:
                models = response.json()
                available_models = [model["name"] for model in models.get("models", [])]
                
                # Check if default model is available
                if self.default_model not in available_models:
                    logger.warning(
                        "Default model not found in Ollama",
                        default_model=self.default_model,
                        available_models=available_models
                    )
                    # Use first available model as fallback
                    if available_models:
                        self.default_model = available_models[0]
                        logger.info(f"Using fallback model: {self.default_model}")
                    else:
                        logger.error("No models available in Ollama")
                        return False
                
                self._connected = True
                
                logger.info(
                    "Ollama connection established",
                    base_url=self.base_url,
                    default_model=self.default_model,
                    available_models=len(available_models)
                )
                
                return True
            else:
                logger.error(
                    "Ollama connection failed",
                    status_code=response.status_code,
                    response=response.text
                )
                return False
                
        except Exception as e:
            logger.error(
                "Ollama connection error",
                base_url=self.base_url,
                error=str(e)
            )
            self._connected = False
            raise ConnectionError(f"Failed to connect to Ollama: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from Ollama."""
        try:
            if self.client:
                await self.client.aclose()
                self._connected = False
                logger.info("Ollama client disconnected")
        except Exception as e:
            logger.warning("Error during Ollama disconnect", error=str(e))
    
    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate response using Ollama."""
        start_time = time.time()
        
        try:
            await self.ensure_connected()
            
            # Format prompt using template if needed
            formatted_prompt = PromptTemplates.format_prompt(
                request.prompt_type, 
                {"prompt": request.prompt, **request.context}
            )
            
            # Prepare request parameters
            model = request.context.get("model", self.default_model)
            max_tokens = request.max_tokens or self.default_max_tokens
            temperature = request.temperature if request.temperature is not None else self.default_temperature
            
            # Build Ollama request
            ollama_request = {
                "model": model,
                "prompt": formatted_prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            }
            
            # Add system message if provided
            if request.system_message:
                ollama_request["system"] = request.system_message
            
            # Make request with retries
            response_data = await self._make_request_with_retry(
                "POST",
                f"{self.base_url}/api/generate",
                json_data=ollama_request
            )
            
            processing_time = time.time() - start_time
            
            # Extract response content
            content = response_data.get("response", "")
            
            # Calculate confidence based on response quality
            confidence = self._calculate_confidence(content, request.prompt_type)
            
            # Get token usage (approximate for Ollama)
            tokens_used = self._estimate_token_usage(formatted_prompt, content)
            
            # Audit the LLM usage
            if request.tenant_id:
                await audit(
                    event_type=AuditEventType.AI_USAGE,
                    tenant_id=request.tenant_id,
                    resource_type="llm_generation",
                    resource_id=f"{model}_{request.prompt_type.value}",
                    details={
                        "provider": "ollama",
                        "model": model,
                        "prompt_type": request.prompt_type.value,
                        "tokens_used": tokens_used,
                        "processing_time": processing_time,
                        "confidence": confidence
                    }
                )
            
            logger.info(
                "Ollama response generated",
                model=model,
                prompt_type=request.prompt_type.value,
                tokens_used=tokens_used,
                processing_time=processing_time,
                confidence=confidence,
                tenant_id=request.tenant_id
            )
            
            return LLMResponse(
                content=content,
                confidence=confidence,
                provider="ollama",
                model=model,
                tokens_used=tokens_used,
                processing_time=processing_time,
                success=True,
                metadata={
                    "prompt_type": request.prompt_type.value,
                    "eval_count": response_data.get("eval_count", 0),
                    "eval_duration": response_data.get("eval_duration", 0),
                    "load_duration": response_data.get("load_duration", 0)
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            logger.error(
                "Ollama response generation failed",
                error=str(e),
                processing_time=processing_time,
                tenant_id=request.tenant_id
            )
            
            return LLMResponse(
                content="",
                confidence=0.0,
                provider="ollama",
                model=self.default_model,
                tokens_used=0,
                processing_time=processing_time,
                success=False,
                error=str(e)
            )
    
    async def _make_request_with_retry(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                if method.upper() == "GET":
                    response = await self.client.get(url, **kwargs)
                elif method.upper() == "POST":
                    response = await self.client.post(url, json=json_data, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    raise ModelNotFoundError(f"Model not found: {json_data.get('model', 'unknown')}")
                elif response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded")
                else:
                    raise GenerationError(f"HTTP {response.status_code}: {response.text}")
                    
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = ConnectionError(f"Connection error: {str(e)}")
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Request failed, retrying in {wait_time}s", attempt=attempt + 1)
                    await asyncio.sleep(wait_time)
                continue
            except Exception as e:
                last_error = e
                break
        
        if last_error:
            raise last_error
        else:
            raise GenerationError("All retry attempts failed")
    
    def _calculate_confidence(self, content: str, prompt_type: PromptType) -> float:
        """Calculate confidence score based on response quality."""
        if not content or len(content.strip()) < 10:
            return 0.0
        
        confidence = 0.5  # Base confidence
        
        # Length-based scoring
        content_length = len(content.strip())
        if content_length > 100:
            confidence += 0.2
        if content_length > 500:
            confidence += 0.1
        
        # Structure-based scoring for different prompt types
        if prompt_type == PromptType.CODE_ANALYSIS:
            if any(keyword in content.lower() for keyword in ["root cause", "analysis", "code", "bug"]):
                confidence += 0.2
        elif prompt_type == PromptType.FIX_GENERATION:
            if any(keyword in content.lower() for keyword in ["fix", "solution", "change", "implement"]):
                confidence += 0.2
        elif prompt_type == PromptType.EXPLANATION:
            if any(keyword in content.lower() for keyword in ["because", "therefore", "this means", "explanation"]):
                confidence += 0.2
        
        # Penalize for common failure patterns
        if any(pattern in content.lower() for pattern in ["i cannot", "i don't know", "sorry", "error"]):
            confidence -= 0.3
        
        return max(0.0, min(1.0, confidence))
    
    def _estimate_token_usage(self, prompt: str, response: str) -> int:
        """Estimate token usage (rough approximation)."""
        # Rough estimate: ~4 characters per token
        total_chars = len(prompt) + len(response)
        return max(1, total_chars // 4)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Ollama health and model availability."""
        try:
            if not self.is_connected():
                return {
                    "healthy": False,
                    "status": "disconnected",
                    "error": "Not connected to Ollama"
                }
            
            # Get available models
            response = await self.client.get(f"{self.base_url}/api/tags")
            
            if response.status_code == 200:
                models_data = response.json()
                models = models_data.get("models", [])
                
                # Test default model with a simple generation
                test_response = await self.client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.default_model,
                        "prompt": "Say 'OK' if you are working.",
                        "stream": False,
                        "options": {"num_predict": 10}
                    },
                    timeout=30.0
                )
                
                generation_working = test_response.status_code == 200
                
                return {
                    "healthy": True,
                    "status": "connected",
                    "base_url": self.base_url,
                    "default_model": self.default_model,
                    "available_models": len(models),
                    "models": [model["name"] for model in models],
                    "generation_test": generation_working
                }
            else:
                return {
                    "healthy": False,
                    "status": "api_error",
                    "error": f"API returned {response.status_code}"
                }
                
        except Exception as e:
            logger.error("Ollama health check failed", error=str(e))
            return {
                "healthy": False,
                "status": "error",
                "error": str(e)
            }
    
    def get_supported_models(self) -> List[str]:
        """Get list of supported Ollama models."""
        try:
            # This would typically be fetched from Ollama API
            # For now, return common models
            return [
                "llama3.1:8b",
                "llama3.1:70b", 
                "llama3.2:3b",
                "codellama:7b",
                "codellama:13b",
                "mistral:7b",
                "mixtral:8x7b",
                "phi3:mini",
                "qwen2.5:7b"
            ]
        except Exception as e:
            logger.warning("Failed to get supported models", error=str(e))
            return [self.default_model]
    
    async def pull_model(self, model_name: str) -> bool:
        """Pull/download a model in Ollama."""
        try:
            logger.info(f"Pulling Ollama model: {model_name}")
            
            response = await self.client.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                timeout=httpx.Timeout(600.0)  # 10 minutes for model download
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully pulled model: {model_name}")
                return True
            else:
                logger.error(
                    f"Failed to pull model: {model_name}",
                    status_code=response.status_code,
                    response=response.text
                )
                return False
                
        except Exception as e:
            logger.error(f"Error pulling model {model_name}", error=str(e))
            return False
    
    async def delete_model(self, model_name: str) -> bool:
        """Delete a model from Ollama."""
        try:
            response = await self.client.delete(
                f"{self.base_url}/api/delete",
                json={"name": model_name}
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully deleted model: {model_name}")
                return True
            else:
                logger.error(
                    f"Failed to delete model: {model_name}",
                    status_code=response.status_code
                )
                return False
                
        except Exception as e:
            logger.error(f"Error deleting model {model_name}", error=str(e))
            return False


import asyncio