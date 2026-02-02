"""
AI Provider Module

Provides unified access to multiple AI backends:
- Cloud providers: Groq (recommended), SambaNova, OpenRouter
- Local provider: Ollama

Usage:
    from exstreamtv.ai_agent.providers import (
        GroqProvider,
        SambanovaProvider,
        OpenRouterProvider,
        get_provider,
        list_providers,
    )
"""

from exstreamtv.ai_agent.providers.groq_provider import GroqProvider
from exstreamtv.ai_agent.providers.sambanova_provider import SambanovaProvider
from exstreamtv.ai_agent.providers.openrouter_provider import OpenRouterProvider

__all__ = [
    "GroqProvider",
    "SambanovaProvider", 
    "OpenRouterProvider",
    "get_provider",
    "list_providers",
    "CLOUD_PROVIDERS",
]

# Provider registry
CLOUD_PROVIDERS = {
    "groq": {
        "name": "Groq",
        "class": GroqProvider,
        "description": "Free, fastest inference - recommended default",
        "free_tier": True,
        "signup_url": "https://console.groq.com/keys",
        "limits": {
            "requests_per_minute": 30,
            "requests_per_day": 14400,
            "tokens_per_minute": 6000,
        },
    },
    "sambanova": {
        "name": "SambaNova",
        "class": SambanovaProvider,
        "description": "Free backup provider - 1M tokens/day",
        "free_tier": True,
        "signup_url": "https://cloud.sambanova.ai",
        "limits": {
            "tokens_per_day": 1000000,
            "requests_per_minute": 120,
        },
    },
    "openrouter": {
        "name": "OpenRouter",
        "class": OpenRouterProvider,
        "description": "Aggregator with $5 free credit - access 100+ models",
        "free_tier": True,
        "signup_url": "https://openrouter.ai/keys",
        "limits": {
            "free_credit": 5.00,
        },
    },
}


def get_provider(provider_id: str, api_key: str | None = None, **kwargs):
    """
    Get a provider instance by ID.
    
    Args:
        provider_id: Provider identifier (groq, sambanova, openrouter)
        api_key: API key for the provider
        **kwargs: Additional provider-specific arguments
        
    Returns:
        Provider instance
        
    Raises:
        ValueError: If provider_id is not recognized
    """
    if provider_id not in CLOUD_PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_id}. Available: {list(CLOUD_PROVIDERS.keys())}")
    
    provider_class = CLOUD_PROVIDERS[provider_id]["class"]
    return provider_class(api_key=api_key, **kwargs)


def list_providers() -> list[dict]:
    """
    List all available cloud providers.
    
    Returns:
        List of provider info dictionaries
    """
    return [
        {
            "id": provider_id,
            "name": info["name"],
            "description": info["description"],
            "free_tier": info["free_tier"],
            "signup_url": info["signup_url"],
            "limits": info["limits"],
        }
        for provider_id, info in CLOUD_PROVIDERS.items()
    ]
