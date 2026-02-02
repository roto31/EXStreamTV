"""
OpenRouter Cloud Provider

Provides access to 100+ AI models through a unified API.
- $5 free credit on signup
- Access to free models (Llama, Mistral variants)
- Pay-as-you-go for premium models

Best used when you need access to specific models or as a fallback.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class OpenRouterModel:
    """Information about an OpenRouter model."""
    id: str
    name: str
    context_window: int
    description: str
    pricing_input: float  # per million tokens
    pricing_output: float  # per million tokens
    is_free: bool = False


# Popular OpenRouter models
OPENROUTER_MODELS = {
    # Free models
    "meta-llama/llama-3.2-3b-instruct:free": OpenRouterModel(
        id="meta-llama/llama-3.2-3b-instruct:free",
        name="Llama 3.2 3B (Free)",
        context_window=128000,
        description="Free lightweight model for basic tasks",
        pricing_input=0,
        pricing_output=0,
        is_free=True,
    ),
    "mistralai/mistral-7b-instruct:free": OpenRouterModel(
        id="mistralai/mistral-7b-instruct:free",
        name="Mistral 7B (Free)",
        context_window=32768,
        description="Free balanced model",
        pricing_input=0,
        pricing_output=0,
        is_free=True,
    ),
    # Paid models (low cost)
    "meta-llama/llama-3.3-70b-instruct": OpenRouterModel(
        id="meta-llama/llama-3.3-70b-instruct",
        name="Llama 3.3 70B",
        context_window=128000,
        description="Best open-source model for channel creation",
        pricing_input=0.12,
        pricing_output=0.30,
    ),
    "qwen/qwen-2.5-72b-instruct": OpenRouterModel(
        id="qwen/qwen-2.5-72b-instruct",
        name="Qwen 2.5 72B",
        context_window=128000,
        description="Excellent for structured output",
        pricing_input=0.15,
        pricing_output=0.40,
    ),
    "anthropic/claude-3.5-haiku": OpenRouterModel(
        id="anthropic/claude-3.5-haiku",
        name="Claude 3.5 Haiku",
        context_window=200000,
        description="Fast, affordable Claude model",
        pricing_input=0.80,
        pricing_output=4.00,
    ),
    "google/gemini-2.0-flash-exp:free": OpenRouterModel(
        id="google/gemini-2.0-flash-exp:free",
        name="Gemini 2.0 Flash (Free)",
        context_window=1048576,
        description="Google's fast model with huge context",
        pricing_input=0,
        pricing_output=0,
        is_free=True,
    ),
}


class OpenRouterProvider:
    """
    OpenRouter Cloud AI Provider.
    
    Aggregator that provides access to 100+ models through a single API.
    Includes free models and $5 credit on signup for paid models.
    
    Example:
        provider = OpenRouterProvider(api_key="sk-or-...")
        response = await provider.generate("Create a movie channel")
    """
    
    BASE_URL = "https://openrouter.ai/api/v1"
    PROVIDER_ID = "openrouter"
    PROVIDER_NAME = "OpenRouter"
    
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "meta-llama/llama-3.3-70b-instruct",
        timeout: float = 60.0,
        site_url: str = "https://exstreamtv.local",
        site_name: str = "EXStreamTV",
    ):
        """
        Initialize OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key. If not provided, reads from OPENROUTER_API_KEY env var.
            model: Model to use
            timeout: Request timeout in seconds
            site_url: Your site URL (for rankings)
            site_name: Your site name (for rankings)
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.timeout = timeout
        self.site_url = site_url
        self.site_name = site_name
        
        if not self.api_key:
            logger.warning("OpenRouter API key not provided. Set OPENROUTER_API_KEY or pass api_key parameter.")
    
    @property
    def is_configured(self) -> bool:
        """Check if the provider is properly configured."""
        return bool(self.api_key)
    
    @classmethod
    def get_models(cls) -> dict[str, OpenRouterModel]:
        """Get popular models."""
        return OPENROUTER_MODELS
    
    @classmethod
    def get_free_models(cls) -> list[str]:
        """Get list of free model IDs."""
        return [m.id for m in OPENROUTER_MODELS.values() if m.is_free]
    
    @classmethod
    def get_recommended_model(cls) -> str:
        """Get the recommended model ID."""
        return "meta-llama/llama-3.3-70b-instruct"
    
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
            raise ValueError("OpenRouter API key not configured")
        
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
            raise ValueError("OpenRouter API key not configured")
        
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
                    "HTTP-Referer": self.site_url,
                    "X-Title": self.site_name,
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
                    f"{self.BASE_URL}/auth/key",
                    headers={"Authorization": f"Bearer {key_to_test}"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"API key validation failed: {e}")
            return False
    
    async def get_credits(self) -> float | None:
        """Get remaining credits for the API key."""
        if not self.api_key:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/auth/key",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", {}).get("limit_remaining")
                return None
        except Exception as e:
            logger.warning(f"Failed to get credits: {e}")
            return None
    
    async def get_available_models(self) -> list[dict[str, Any]]:
        """Get list of all available models from OpenRouter."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.BASE_URL}/models")
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                return []
        except Exception as e:
            logger.warning(f"Failed to fetch models: {e}")
            return []
    
    def to_dict(self) -> dict[str, Any]:
        """Convert provider state to dictionary."""
        return {
            "provider_id": self.PROVIDER_ID,
            "provider_name": self.PROVIDER_NAME,
            "model": self.model,
            "is_configured": self.is_configured,
            "available_models": list(OPENROUTER_MODELS.keys()),
            "free_models": self.get_free_models(),
        }
