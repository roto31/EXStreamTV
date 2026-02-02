"""
SambaNova Cloud Provider

Provides access to SambaNova's high-performance inference API.
FREE tier includes:
- 1 million tokens/day
- 120 requests/minute for Llama 3.3 70B
- No credit card required

Recommended as a backup cloud provider for EXStreamTV.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SambanovaModel:
    """Information about a SambaNova model."""
    id: str
    name: str
    context_window: int
    description: str
    requests_per_minute: int
    requests_per_day: int


# Available SambaNova models (free tier)
SAMBANOVA_MODELS = {
    "Meta-Llama-3.3-70B-Instruct": SambanovaModel(
        id="Meta-Llama-3.3-70B-Instruct",
        name="Llama 3.3 70B Instruct",
        context_window=128000,
        description="Best quality, excellent for channel creation",
        requests_per_minute=120,
        requests_per_day=12000,
    ),
    "Meta-Llama-3.1-8B-Instruct": SambanovaModel(
        id="Meta-Llama-3.1-8B-Instruct",
        name="Llama 3.1 8B Instruct",
        context_window=128000,
        description="Fast, good for troubleshooting",
        requests_per_minute=480,
        requests_per_day=72000,
    ),
    "DeepSeek-R1": SambanovaModel(
        id="DeepSeek-R1",
        name="DeepSeek R1",
        context_window=128000,
        description="Strong reasoning model",
        requests_per_minute=30,
        requests_per_day=3000,
    ),
    "Qwen3-32B": SambanovaModel(
        id="Qwen3-32B",
        name="Qwen 3 32B",
        context_window=128000,
        description="Excellent for structured output",
        requests_per_minute=20,
        requests_per_day=3000,
    ),
}


class SambanovaProvider:
    """
    SambaNova Cloud AI Provider.
    
    Provides access to SambaNova's high-performance inference with generous free tier.
    Best used as a backup provider when Groq rate limits are hit.
    
    Example:
        provider = SambanovaProvider(api_key="...")
        response = await provider.generate("Analyze this error log")
    """
    
    BASE_URL = "https://api.sambanova.ai/v1"
    PROVIDER_ID = "sambanova"
    PROVIDER_NAME = "SambaNova"
    
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "Meta-Llama-3.3-70B-Instruct",
        timeout: float = 30.0,
    ):
        """
        Initialize SambaNova provider.
        
        Args:
            api_key: SambaNova API key. If not provided, reads from SAMBANOVA_API_KEY env var.
            model: Model to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("SAMBANOVA_API_KEY")
        self.model = model
        self.timeout = timeout
        
        if not self.api_key:
            logger.warning("SambaNova API key not provided. Set SAMBANOVA_API_KEY or pass api_key parameter.")
    
    @property
    def is_configured(self) -> bool:
        """Check if the provider is properly configured."""
        return bool(self.api_key)
    
    @classmethod
    def get_models(cls) -> dict[str, SambanovaModel]:
        """Get available models."""
        return SAMBANOVA_MODELS
    
    @classmethod
    def get_recommended_model(cls) -> str:
        """Get the recommended model ID."""
        return "Meta-Llama-3.3-70B-Instruct"
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        """
        Generate a response from the model.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Generated text response
        """
        if not self.api_key:
            raise ValueError("SambaNova API key not configured")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return await self.chat(messages, temperature=temperature, max_tokens=max_tokens, **kwargs)
    
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Generated text response
        """
        if not self.api_key:
            raise ValueError("SambaNova API key not configured")
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        payload.update(kwargs)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data["choices"][0]["message"]["content"]
    
    async def validate_api_key(self, api_key: str | None = None) -> bool:
        """Validate an API key."""
        key_to_test = api_key or self.api_key
        if not key_to_test:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/models",
                    headers={"Authorization": f"Bearer {key_to_test}"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"API key validation failed: {e}")
            return False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert provider state to dictionary."""
        return {
            "provider_id": self.PROVIDER_ID,
            "provider_name": self.PROVIDER_NAME,
            "model": self.model,
            "is_configured": self.is_configured,
            "available_models": list(SAMBANOVA_MODELS.keys()),
        }
