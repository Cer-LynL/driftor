"""
Base LLM interface for code analysis and fix generation.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"


class PromptType(Enum):
    """Types of prompts for different use cases."""
    CODE_ANALYSIS = "code_analysis"
    FIX_GENERATION = "fix_generation"
    EXPLANATION = "explanation"
    SIMILARITY_ANALYSIS = "similarity_analysis"
    DOCUMENTATION_SEARCH = "documentation_search"
    CHAT_RESPONSE = "chat_response"


@dataclass
class LLMRequest:
    """Request structure for LLM operations."""
    prompt: str
    context: Dict[str, Any]
    prompt_type: PromptType
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    system_message: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None


@dataclass
class LLMResponse:
    """Response structure from LLM operations."""
    content: str
    confidence: float
    provider: str
    model: str
    tokens_used: int
    processing_time: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_type = None
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the LLM provider."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the LLM provider."""
        pass
    
    @abstractmethod
    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate response from the LLM."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check provider health and availability."""
        pass
    
    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """Get list of supported models."""
        pass
    
    def is_connected(self) -> bool:
        """Check if connected to the provider."""
        return self._connected
    
    async def ensure_connected(self) -> bool:
        """Ensure provider connection is active."""
        if not self.is_connected():
            return await self.connect()
        return True


class PromptTemplates:
    """Template manager for different types of prompts."""
    
    CODE_ANALYSIS_TEMPLATE = """
You are an expert software engineer analyzing a bug report and related code. Your task is to analyze the issue and provide insights.

## Bug Report Information:
**Ticket**: {ticket_key}
**Summary**: {summary}
**Description**: {description}
**Component**: {component}
**Severity**: {severity}

## Related Code Files:
{code_files}

## Similar Past Issues:
{similar_tickets}

## Relevant Documentation:
{documentation}

Please analyze this bug report and provide:

1. **Root Cause Analysis**: What is likely causing this issue?
2. **Impact Assessment**: How severe is this bug and what systems are affected?
3. **Code Areas**: Which specific code areas should be investigated?
4. **Dependencies**: Are there any related systems or dependencies that might be involved?

Provide your analysis in a structured format with clear reasoning for each point.
"""

    FIX_GENERATION_TEMPLATE = """
You are an expert software engineer generating fix suggestions for a bug report.

## Bug Report:
**Ticket**: {ticket_key}
**Summary**: {summary}
**Description**: {description}
**Component**: {component}

## Code Analysis Results:
{code_analysis}

## Relevant Code Files:
{relevant_files}

## Similar Past Fixes:
{similar_fixes}

Please provide fix suggestions with the following structure:

1. **Recommended Fix**: The primary solution approach
2. **Code Changes**: Specific code modifications needed
3. **Testing Strategy**: How to test the fix
4. **Risk Assessment**: Potential risks and mitigation strategies
5. **Alternative Approaches**: Other possible solutions
6. **Confidence Level**: Your confidence in this fix (0-100%)

Focus on providing actionable, specific guidance that a developer can implement.
"""

    EXPLANATION_TEMPLATE = """
You are a helpful technical assistant explaining complex software issues in simple terms.

## Context:
{context}

## Question:
{question}

Please provide a clear, concise explanation that:
1. Explains the technical concepts involved
2. Uses examples where helpful
3. Suggests next steps or further resources
4. Is appropriate for the user's technical level

Keep your response focused and practical.
"""

    SIMILARITY_ANALYSIS_TEMPLATE = """
You are analyzing the similarity between bug reports to help identify patterns and solutions.

## Current Issue:
**Ticket**: {current_ticket}
**Summary**: {current_summary}
**Description**: {current_description}

## Potentially Similar Issues:
{similar_issues}

Please analyze these issues and provide:

1. **Similarity Assessment**: How similar are these issues? (0-100%)
2. **Common Patterns**: What patterns or root causes do they share?
3. **Solution Applicability**: Can solutions from similar issues be applied here?
4. **Key Differences**: What makes this issue unique?

Focus on actionable insights that can help resolve the current issue.
"""

    CHAT_RESPONSE_TEMPLATE = """
You are Driftor, an AI assistant specialized in helping developers with bug analysis and resolution.

## Conversation Context:
{conversation_history}

## Current User Message:
{user_message}

## Available Context:
- Ticket: {ticket_key}
- Analysis Results: {analysis_results}
- Code Information: {code_context}

Please provide a helpful response that:
1. Directly addresses the user's question
2. Uses the available context appropriately
3. Provides actionable guidance
4. Maintains a professional but friendly tone
5. Asks clarifying questions if needed

Keep responses concise but informative.
"""

    @classmethod
    def get_template(cls, prompt_type: PromptType) -> str:
        """Get template for a specific prompt type."""
        template_map = {
            PromptType.CODE_ANALYSIS: cls.CODE_ANALYSIS_TEMPLATE,
            PromptType.FIX_GENERATION: cls.FIX_GENERATION_TEMPLATE,
            PromptType.EXPLANATION: cls.EXPLANATION_TEMPLATE,
            PromptType.SIMILARITY_ANALYSIS: cls.SIMILARITY_ANALYSIS_TEMPLATE,
            PromptType.CHAT_RESPONSE: cls.CHAT_RESPONSE_TEMPLATE,
        }
        return template_map.get(prompt_type, "")

    @classmethod
    def format_prompt(cls, prompt_type: PromptType, context: Dict[str, Any]) -> str:
        """Format a prompt template with context data."""
        template = cls.get_template(prompt_type)
        if not template:
            return context.get("prompt", "")
        
        try:
            return template.format(**context)
        except KeyError as e:
            logger.warning(f"Missing context key for prompt formatting: {e}")
            return template
        except Exception as e:
            logger.error(f"Error formatting prompt: {e}")
            return context.get("prompt", template)


class LLMError(Exception):
    """Base exception for LLM operations."""
    pass


class ConnectionError(LLMError):
    """LLM provider connection error."""
    pass


class GenerationError(LLMError):
    """Response generation error."""
    pass


class RateLimitError(LLMError):
    """Rate limit exceeded error."""
    pass


class ModelNotFoundError(LLMError):
    """Model not available error."""
    pass