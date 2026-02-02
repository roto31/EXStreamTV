"""
AI Provider Management API Endpoints

Provides REST API for configuring and managing AI providers.
"""

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..ai_agent.provider_manager import AIConfig, CloudProviderID, ProviderType, UnifiedAIProvider
from ..ai_agent.providers import CLOUD_PROVIDERS, list_providers
from ..config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Providers"])


# Request/Response Models

class ProviderConfigRequest(BaseModel):
    """Request model for configuring AI provider."""
    provider_type: str  # cloud, local, hybrid
    cloud_provider: str | None = None  # groq, sambanova, openrouter
    cloud_api_key: str | None = None
    cloud_model: str | None = None
    local_model: str | None = None
    fallback_providers: list[dict[str, str]] | None = None


class TestProviderRequest(BaseModel):
    """Request model for testing a provider."""
    provider_id: str  # groq, sambanova, openrouter
    api_key: str
    model: str | None = None


class GenerateRequest(BaseModel):
    """Request model for generating AI response."""
    prompt: str
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


# Provider instance (lazy loaded)
_provider_instance: UnifiedAIProvider | None = None


def get_ai_provider() -> UnifiedAIProvider:
    """Get or create the AI provider instance."""
    global _provider_instance
    
    if _provider_instance is None:
        config = get_config()
        ai_config = AIConfig.from_dict({"ai_agent": config.dict().get("ai_agent", {})})
        _provider_instance = UnifiedAIProvider(ai_config)
    
    return _provider_instance


def reset_provider():
    """Reset the provider instance (after config change)."""
    global _provider_instance
    _provider_instance = None


@router.get("/providers")
async def get_providers() -> dict[str, Any]:
    """
    List all available AI providers.
    
    Returns:
        List of cloud providers and local model options
    """
    from .ollama import OLLAMA_MODELS, get_system_info
    
    # Get cloud providers
    cloud_providers = list_providers()
    
    # Get local model recommendations
    system_info = get_system_info()
    ram_gb = system_info.get("ram_gb", 8)
    
    local_models = []
    for model_id, model_info in OLLAMA_MODELS.items():
        can_run = ram_gb >= model_info.get("ram_required_gb", 8)
        local_models.append({
            "id": model_id,
            "name": model_info.get("name", model_id),
            "size_gb": model_info.get("size_gb", 0),
            "ram_required_gb": model_info.get("ram_required_gb", 8),
            "description": model_info.get("description", ""),
            "recommended_for": model_info.get("recommended_for", ""),
            "tier": model_info.get("tier", 2),
            "capabilities": model_info.get("capabilities", []),
            "can_run": can_run,
        })
    
    # Sort by tier
    local_models.sort(key=lambda x: (x["tier"], x["size_gb"]))
    
    return {
        "cloud_providers": cloud_providers,
        "local_models": local_models,
        "system_info": system_info,
        "recommended_local_model": _get_recommended_model(ram_gb),
    }


def _get_recommended_model(ram_gb: float) -> str:
    """Get recommended local model based on RAM."""
    if ram_gb < 6:
        return "phi4-mini:3.8b-q4"
    elif ram_gb < 12:
        return "granite3.1:2b-instruct"
    elif ram_gb < 24:
        return "qwen2.5:7b"
    else:
        return "qwen2.5:14b"


@router.get("/status")
async def get_ai_status() -> dict[str, Any]:
    """
    Get current AI provider status.
    
    Returns:
        Current configuration and availability status
    """
    provider = get_ai_provider()
    validation = await provider.validate()
    
    return {
        "provider": provider.to_dict(),
        "validation": validation,
    }


@router.post("/configure")
async def configure_provider(request: ProviderConfigRequest) -> dict[str, Any]:
    """
    Configure the AI provider.
    
    This updates the runtime configuration. To persist, update config.yaml.
    
    Args:
        request: Provider configuration
        
    Returns:
        Updated configuration status
    """
    try:
        provider_type = ProviderType(request.provider_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider_type: {request.provider_type}")
    
    cloud_provider = None
    if request.cloud_provider:
        try:
            cloud_provider = CloudProviderID(request.cloud_provider)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid cloud_provider: {request.cloud_provider}")
    
    # Create new config
    config = AIConfig(
        provider_type=provider_type,
        cloud_provider=cloud_provider or CloudProviderID.GROQ,
        cloud_api_key=request.cloud_api_key or "",
        cloud_model=request.cloud_model or "llama-3.3-70b-versatile",
        local_model=request.local_model or "auto",
        fallback_providers=request.fallback_providers or [],
    )
    
    # Create new provider
    global _provider_instance
    _provider_instance = UnifiedAIProvider(config)
    
    # Validate
    validation = await _provider_instance.validate()
    
    return {
        "success": True,
        "provider": _provider_instance.to_dict(),
        "validation": validation,
    }


@router.post("/test")
async def test_provider(request: TestProviderRequest) -> dict[str, Any]:
    """
    Test a provider connection with an API key.
    
    Args:
        request: Provider ID and API key to test
        
    Returns:
        Test result
    """
    from ..ai_agent.providers import get_provider
    
    try:
        provider = get_provider(request.provider_id, api_key=request.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validate API key
    is_valid = await provider.validate_api_key(request.api_key)
    
    if not is_valid:
        return {
            "success": False,
            "provider_id": request.provider_id,
            "message": "API key is invalid or expired",
        }
    
    # Try a simple generation
    try:
        response = await provider.generate(
            prompt="Say 'Hello' in one word.",
            max_tokens=10,
        )
        
        return {
            "success": True,
            "provider_id": request.provider_id,
            "message": "Provider is working correctly",
            "test_response": response.strip(),
        }
    except Exception as e:
        return {
            "success": False,
            "provider_id": request.provider_id,
            "message": f"Provider test failed: {e}",
        }


@router.get("/models")
async def get_models(provider_id: str | None = None) -> dict[str, Any]:
    """
    Get available models for a provider.
    
    Args:
        provider_id: Optional provider ID (groq, sambanova, openrouter, ollama)
        
    Returns:
        List of available models
    """
    from .ollama import OLLAMA_MODELS, get_installed_ollama_models
    
    result = {}
    
    # Cloud provider models
    if not provider_id or provider_id == "groq":
        from ..ai_agent.providers.groq_provider import GROQ_MODELS
        result["groq"] = [
            {
                "id": m.id,
                "name": m.name,
                "context_window": m.context_window,
                "description": m.description,
                "recommended": m.recommended,
            }
            for m in GROQ_MODELS.values()
        ]
    
    if not provider_id or provider_id == "sambanova":
        from ..ai_agent.providers.sambanova_provider import SAMBANOVA_MODELS
        result["sambanova"] = [
            {
                "id": m.id,
                "name": m.name,
                "context_window": m.context_window,
                "description": m.description,
            }
            for m in SAMBANOVA_MODELS.values()
        ]
    
    if not provider_id or provider_id == "openrouter":
        from ..ai_agent.providers.openrouter_provider import OPENROUTER_MODELS
        result["openrouter"] = [
            {
                "id": m.id,
                "name": m.name,
                "context_window": m.context_window,
                "description": m.description,
                "is_free": m.is_free,
            }
            for m in OPENROUTER_MODELS.values()
        ]
    
    if not provider_id or provider_id == "ollama":
        installed = get_installed_ollama_models()
        result["ollama"] = [
            {
                "id": model_id,
                "name": info.get("name", model_id),
                "size_gb": info.get("size_gb", 0),
                "description": info.get("description", ""),
                "installed": model_id in installed or any(model_id in m for m in installed),
            }
            for model_id, info in OLLAMA_MODELS.items()
        ]
        result["ollama_installed"] = installed
    
    return result


@router.post("/generate")
async def generate_response(request: GenerateRequest) -> dict[str, Any]:
    """
    Generate a response using the configured AI provider.
    
    Args:
        request: Generation request with prompt and optional parameters
        
    Returns:
        Generated response
    """
    provider = get_ai_provider()
    
    if not provider.is_configured:
        raise HTTPException(
            status_code=400,
            detail="AI provider is not configured. Please configure an API key or local model.",
        )
    
    try:
        response = await provider.generate(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        
        return {
            "success": True,
            "response": response,
            "provider": provider.to_dict(),
        }
    except Exception as e:
        logger.error(f"AI generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")
