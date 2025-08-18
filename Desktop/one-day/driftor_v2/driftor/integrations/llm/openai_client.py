"""
OpenAI LLM client for fallback support.
"""
import time
from typing import Dict, List, Optional, Any
import openai
import structlog

from .base import BaseLLMProvider, LLMRequest, LLMResponse, LLMProvider, PromptTemplates
from .base import LLMError, ConnectionError, GenerationError, RateLimitError, ModelNotFoundError
from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class OpenAIClient(BaseLLMProvider):
    """OpenAI LLM client implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        self.api_key = config.get("api_key")
        self.organization = config.get("organization")
        self.base_url = config.get("base_url")  # For Azure OpenAI
        self.api_version = config.get("api_version")  # For Azure OpenAI
        
        self.default_model = config.get("model", "gpt-4")
        self.max_retries = config.get("max_retries", 3)
        
        # Default parameters
        self.default_max_tokens = config.get("max_tokens", 4000)
        self.default_temperature = config.get("temperature", 0.1)
        
        self.provider_type = LLMProvider.OPENAI
        
        # Initialize OpenAI client
        client_kwargs = {}
        if self.api_key:
            client_kwargs["api_key"] = self.api_key
        if self.organization:
            client_kwargs["organization"] = self.organization
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        
        self.client = openai.AsyncOpenAI(**client_kwargs)
    
    async def connect(self) -> bool:
        """Connect to OpenAI API."""
        try:
            if not self.api_key:
                logger.error("OpenAI API key not provided")
                return False
            
            # Test connection with a simple request
            models = await self.client.models.list()
            
            available_models = [model.id for model in models.data]
            
            # Check if default model is available
            if self.default_model not in available_models:
                logger.warning(
                    "Default model not found in OpenAI",
                    default_model=self.default_model,
                    available_count=len(available_models)
                )
                # Keep the default model anyway as it might be a valid model
                # that's just not in the public list
            
            self._connected = True
            
            logger.info(
                "OpenAI connection established",
                default_model=self.default_model,
                available_models=len(available_models)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "OpenAI connection error",
                error=str(e)
            )
            self._connected = False
            raise ConnectionError(f"Failed to connect to OpenAI: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from OpenAI."""
        try:
            if self.client:
                await self.client.close()
                self._connected = False
                logger.info("OpenAI client disconnected")
        except Exception as e:
            logger.warning("Error during OpenAI disconnect", error=str(e))
    
    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate response using OpenAI."""
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
            
            # Build messages
            messages = []
            
            if request.system_message:
                messages.append({
                    "role": "system",
                    "content": request.system_message
                })
            
            messages.append({
                "role": "user", 
                "content": formatted_prompt
            })
            
            # Make request with retries
            response = await self._make_request_with_retry(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            processing_time = time.time() - start_time
            
            # Extract response content
            content = response.choices[0].message.content or ""
            
            # Calculate confidence based on response quality and finish reason
            confidence = self._calculate_confidence(
                content, 
                request.prompt_type,
                response.choices[0].finish_reason
            )
            
            # Get token usage
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            # Audit the LLM usage
            if request.tenant_id:
                await audit(
                    event_type=AuditEventType.AI_USAGE,
                    tenant_id=request.tenant_id,
                    resource_type="llm_generation",
                    resource_id=f"{model}_{request.prompt_type.value}",
                    details={
                        "provider": "openai",
                        "model": model,
                        "prompt_type": request.prompt_type.value,
                        "tokens_used": tokens_used,
                        "processing_time": processing_time,
                        "confidence": confidence,
                        "finish_reason": response.choices[0].finish_reason
                    }
                )
            
            logger.info(
                "OpenAI response generated",
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
                provider="openai",
                model=model,
                tokens_used=tokens_used,
                processing_time=processing_time,
                success=True,
                metadata={
                    "prompt_type": request.prompt_type.value,
                    "finish_reason": response.choices[0].finish_reason,
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0
                }
            )
            
        except openai.RateLimitError as e:
            processing_time = time.time() - start_time
            logger.warning("OpenAI rate limit exceeded", error=str(e))
            
            return LLMResponse(
                content="",
                confidence=0.0,
                provider="openai",
                model=self.default_model,
                tokens_used=0,
                processing_time=processing_time,
                success=False,
                error=f"Rate limit exceeded: {str(e)}"
            )
            
        except openai.NotFoundError as e:
            processing_time = time.time() - start_time
            logger.error("OpenAI model not found", error=str(e))
            
            return LLMResponse(
                content="",
                confidence=0.0,
                provider="openai",
                model=self.default_model,
                tokens_used=0,
                processing_time=processing_time,
                success=False,
                error=f"Model not found: {str(e)}"
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            logger.error(
                "OpenAI response generation failed",
                error=str(e),
                processing_time=processing_time,
                tenant_id=request.tenant_id
            )
            
            return LLMResponse(
                content="",
                confidence=0.0,
                provider="openai",
                model=self.default_model,
                tokens_used=0,
                processing_time=processing_time,
                success=False,
                error=str(e)
            )
    
    async def _make_request_with_retry(self, **kwargs) -> Any:
        """Make OpenAI request with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                return response
                
            except openai.RateLimitError as e:
                last_error = RateLimitError(str(e))
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limited, retrying in {wait_time}s", attempt=attempt + 1)
                    await asyncio.sleep(wait_time)
                continue
                
            except openai.APIConnectionError as e:
                last_error = ConnectionError(str(e))
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Connection error, retrying in {wait_time}s", attempt=attempt + 1)
                    await asyncio.sleep(wait_time)
                continue
                
            except openai.NotFoundError as e:
                # Don't retry for model not found
                raise ModelNotFoundError(str(e))
                
            except Exception as e:
                last_error = GenerationError(str(e))
                break
        
        if last_error:
            raise last_error
        else:
            raise GenerationError("All retry attempts failed")
    
    def _calculate_confidence(self, content: str, prompt_type: PromptType, finish_reason: str) -> float:
        """Calculate confidence score based on response quality."""
        if not content or len(content.strip()) < 10:
            return 0.0
        
        # Base confidence from finish reason
        if finish_reason == "stop":
            confidence = 0.8  # Completed normally
        elif finish_reason == "length":
            confidence = 0.6  # Hit max tokens
        else:
            confidence = 0.4  # Other reasons
        
        # Length-based scoring
        content_length = len(content.strip())
        if content_length > 100:
            confidence += 0.1
        if content_length > 500:
            confidence += 0.1
        
        # Structure-based scoring for different prompt types
        if prompt_type == PromptType.CODE_ANALYSIS:
            if any(keyword in content.lower() for keyword in ["root cause", "analysis", "code", "bug"]):
                confidence += 0.1
        elif prompt_type == PromptType.FIX_GENERATION:
            if any(keyword in content.lower() for keyword in ["fix", "solution", "change", "implement"]):
                confidence += 0.1
        elif prompt_type == PromptType.EXPLANATION:
            if any(keyword in content.lower() for keyword in ["because", "therefore", "this means", "explanation"]):
                confidence += 0.1
        
        return max(0.0, min(1.0, confidence))
    
    async def health_check(self) -> Dict[str, Any]:
        """Check OpenAI API health and model availability."""
        try:
            if not self.is_connected():
                return {
                    "healthy": False,
                    "status": "disconnected",
                    "error": "Not connected to OpenAI"
                }
            
            # Get available models
            models = await self.client.models.list()
            available_models = [model.id for model in models.data]
            
            # Test with a simple completion
            test_response = await self.client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "Say 'OK' if you are working."}],
                max_tokens=10,
                timeout=30.0
            )
            
            generation_working = bool(test_response.choices[0].message.content)
            
            return {
                "healthy": True,
                "status": "connected",
                "default_model": self.default_model,
                "available_models": len(available_models),
                "generation_test": generation_working,
                "organization": self.organization,
                "base_url": self.base_url
            }
            
        except Exception as e:
            logger.error("OpenAI health check failed", error=str(e))
            return {
                "healthy": False,
                "status": "error",
                "error": str(e)
            }
    
    def get_supported_models(self) -> List[str]:
        """Get list of supported OpenAI models."""
        return [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ]


import asyncio