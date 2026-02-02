"""
Groq Cloud Provider

Provides access to Groq's ultra-fast inference API.
FREE tier includes:
- 30 requests/minute
- 14,400 requests/day
- 6,000 tokens/minute
- No credit card required

Recommended as the default cloud provider for EXStreamTV.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GroqModel:
    """Information about a Groq model."""
    id: str
    name: str
    context_window: int
    description: str
    recommended: bool = False


# Available Groq models
GROQ_MODELS = {
    "llama-3.3-70b-versatile": GroqModel(
        id="llama-3.3-70b-versatile",
        name="Llama 3.3 70B Versatile",
        context_window=128000,
        description="Best for channel creation personas - excellent reasoning and JSON output",
        recommended=True,
    ),
    "llama-3.1-70b-versatile": GroqModel(
        id="llama-3.1-70b-versatile",
        name="Llama 3.1 70B Versatile",
        context_window=128000,
        description="Previous generation, still excellent for complex tasks",
    ),
    "llama-3.1-8b-instant": GroqModel(
        id="llama-3.1-8b-instant",
        name="Llama 3.1 8B Instant",
        context_window=128000,
        description="Fast, good for troubleshooting and simple tasks",
    ),
    "mixtral-8x7b-32768": GroqModel(
        id="mixtral-8x7b-32768",
        name="Mixtral 8x7B",
        context_window=32768,
        description="Strong reasoning capabilities, good for analysis",
    ),
    "gemma2-9b-it": GroqModel(
        id="gemma2-9b-it",
        name="Gemma 2 9B",
        context_window=8192,
        description="Google's efficient model, good for quick tasks",
    ),
}


class GroqProvider:
    """
    Groq Cloud AI Provider.
    
    Provides access to Groq's ultra-fast LPU inference for various open-source models.
    The free tier is generous enough for personal use with no credit card required.
    
    Example:
        provider = GroqProvider(api_key="gsk_...")
        response = await provider.generate("Create a classic TV channel")
    """
    
    BASE_URL = "https://api.groq.com/openai/v1"
    PROVIDER_ID = "groq"
    PROVIDER_NAME = "Groq"
    
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "llama-3.3-70b-versatile",
        timeout: float = 30.0,
    ):
        """
        Initialize Groq provider.
        
        Args:
            api_key: Groq API key. If not provided, reads from GROQ_API_KEY env var.
            model: Model to use (default: llama-3.3-70b-versatile)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model
        self.timeout = timeout
        
        if not self.api_key:
            logger.warning("Groq API key not provided. Set GROQ_API_KEY or pass api_key parameter.")
    
    @property
    def is_configured(self) -> bool:
        """Check if the provider is properly configured."""
        return bool(self.api_key)
    
    @classmethod
    def get_models(cls) -> dict[str, GroqModel]:
        """Get available models."""
        return GROQ_MODELS
    
    @classmethod
    def get_recommended_model(cls) -> str:
        """Get the recommended model ID."""
        for model_id, model in GROQ_MODELS.items():
            if model.recommended:
                return model_id
        return "llama-3.3-70b-versatile"
    
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
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters passed to the API
            
        Returns:
            Generated text response
            
        Raises:
            ValueError: If API key is not configured
            httpx.HTTPError: If API request fails
        """
        if not self.api_key:
            raise ValueError("Groq API key not configured")
        
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
        response_format: dict | None = None,
        **kwargs,
    ) -> str:
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Optional response format (e.g., {"type": "json_object"})
            **kwargs: Additional parameters
            
        Returns:
            Generated text response
        """
        if not self.api_key:
            raise ValueError("Groq API key not configured")
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            payload["response_format"] = response_format
        
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
        """
        Validate an API key by making a test request.
        
        Args:
            api_key: API key to validate (uses instance key if not provided)
            
        Returns:
            True if the key is valid, False otherwise
        """
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
    
    async def get_available_models(self) -> list[dict[str, Any]]:
        """
        Get list of available models from the API.
        
        Returns:
            List of model info dictionaries
        """
        if not self.api_key:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                
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
            "available_models": list(GROQ_MODELS.keys()),
        }
