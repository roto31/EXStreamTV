"""
Unified AI Provider Manager

Provides a single interface for all AI providers (cloud and local).
Supports automatic failover and hybrid mode (cloud primary, local fallback).
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .providers import GroqProvider, OpenRouterProvider, SambanovaProvider

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """AI provider type selection."""
    CLOUD = "cloud"
    LOCAL = "local"
    HYBRID = "hybrid"


class CloudProviderID(Enum):
    """Available cloud provider identifiers."""
    GROQ = "groq"
    SAMBANOVA = "sambanova"
    OPENROUTER = "openrouter"


@dataclass
class AIConfig:
    """Configuration for the AI provider manager."""
    provider_type: ProviderType = ProviderType.CLOUD
    
    # Cloud provider settings
    cloud_provider: CloudProviderID = CloudProviderID.GROQ
    cloud_api_key: str = ""
    cloud_model: str = "llama-3.3-70b-versatile"
    
    # Cloud fallback providers
    fallback_providers: list[dict[str, str]] = field(default_factory=list)
    
    # Local provider settings (Ollama)
    local_host: str = "http://localhost:11434"
    local_model: str = "auto"  # Auto-select based on RAM
    
    # Generation settings
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: float = 30.0
    
    @classmethod
    def from_dict(cls, config: dict) -> "AIConfig":
        """Create config from dictionary."""
        ai_config = config.get("ai_agent", {})
        
        return cls(
            provider_type=ProviderType(ai_config.get("provider_type", "cloud")),
            cloud_provider=CloudProviderID(ai_config.get("cloud", {}).get("provider", "groq")),
            cloud_api_key=ai_config.get("cloud", {}).get("api_key", os.getenv("GROQ_API_KEY", "")),
            cloud_model=ai_config.get("cloud", {}).get("model", "llama-3.3-70b-versatile"),
            fallback_providers=ai_config.get("cloud", {}).get("fallback", []),
            local_host=ai_config.get("local", {}).get("host", "http://localhost:11434"),
            local_model=ai_config.get("local", {}).get("model", "auto"),
            temperature=ai_config.get("settings", {}).get("temperature", 0.3),
            max_tokens=ai_config.get("settings", {}).get("max_tokens", 4096),
            timeout=ai_config.get("settings", {}).get("timeout", 30.0),
        )


class UnifiedAIProvider:
    """
    Unified interface for all AI providers.
    
    Supports:
    - Cloud providers (Groq, SambaNova, OpenRouter)
    - Local provider (Ollama)
    - Hybrid mode with automatic fallback
    
    Example:
        config = AIConfig(provider_type=ProviderType.CLOUD, cloud_api_key="...")
        provider = UnifiedAIProvider(config)
        response = await provider.generate("Create a classic TV channel")
    """
    
    def __init__(self, config: AIConfig):
        """Initialize the unified provider with configuration."""
        self.config = config
        self._cloud_provider = None
        self._fallback_providers = []
        self._init_providers()
    
    def _init_providers(self):
        """Initialize configured providers."""
        # Initialize primary cloud provider
        if self.config.provider_type in (ProviderType.CLOUD, ProviderType.HYBRID):
            self._cloud_provider = self._create_cloud_provider(
                self.config.cloud_provider,
                self.config.cloud_api_key,
                self.config.cloud_model,
            )
            
            # Initialize fallback providers
            for fallback in self.config.fallback_providers:
                provider_id = CloudProviderID(fallback.get("provider", "sambanova"))
                api_key = fallback.get("api_key", "")
                model = fallback.get("model", "")
                
                if api_key or os.getenv(f"{provider_id.value.upper()}_API_KEY"):
                    try:
                        provider = self._create_cloud_provider(provider_id, api_key, model)
                        if provider:
                            self._fallback_providers.append(provider)
                    except Exception as e:
                        logger.warning(f"Failed to initialize fallback provider {provider_id.value}: {e}")
    
    def _create_cloud_provider(
        self,
        provider_id: CloudProviderID,
        api_key: str,
        model: str = "",
    ):
        """Create a cloud provider instance."""
        if provider_id == CloudProviderID.GROQ:
            return GroqProvider(
                api_key=api_key,
                model=model or "llama-3.3-70b-versatile",
                timeout=self.config.timeout,
            )
        elif provider_id == CloudProviderID.SAMBANOVA:
            return SambanovaProvider(
                api_key=api_key,
                model=model or "Meta-Llama-3.3-70B-Instruct",
                timeout=self.config.timeout,
            )
        elif provider_id == CloudProviderID.OPENROUTER:
            return OpenRouterProvider(
                api_key=api_key,
                model=model or "meta-llama/llama-3.3-70b-instruct",
                timeout=self.config.timeout,
            )
        return None
    
    @property
    def is_configured(self) -> bool:
        """Check if at least one provider is configured."""
        if self.config.provider_type == ProviderType.CLOUD:
            return self._cloud_provider is not None and self._cloud_provider.is_configured
        elif self.config.provider_type == ProviderType.LOCAL:
            return True  # Ollama availability checked at runtime
        else:  # Hybrid
            cloud_ok = self._cloud_provider is not None and self._cloud_provider.is_configured
            return cloud_ok  # Local is always available as fallback
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """
        Generate a response from the appropriate provider.
        
        Routes to cloud, local, or hybrid based on configuration.
        Includes automatic fallback in hybrid mode.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Generated text response
        """
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        
        if self.config.provider_type == ProviderType.CLOUD:
            return await self._cloud_generate(prompt, system_prompt, temp, tokens, **kwargs)
        elif self.config.provider_type == ProviderType.LOCAL:
            return await self._local_generate(prompt, system_prompt, temp, tokens, **kwargs)
        else:  # Hybrid
            try:
                return await self._cloud_generate(prompt, system_prompt, temp, tokens, **kwargs)
            except Exception as e:
                logger.warning(f"Cloud provider failed, falling back to local: {e}")
                return await self._local_generate(prompt, system_prompt, temp, tokens, **kwargs)
    
    async def _cloud_generate(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> str:
        """Generate using cloud provider with fallback support."""
        if not self._cloud_provider:
            raise ValueError("No cloud provider configured")
        
        # Try primary provider
        try:
            return await self._cloud_provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as e:
            logger.warning(f"Primary cloud provider failed: {e}")
            
            # Try fallback providers
            for fallback in self._fallback_providers:
                try:
                    logger.info(f"Trying fallback provider: {fallback.PROVIDER_ID}")
                    return await fallback.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs,
                    )
                except Exception as fallback_error:
                    logger.warning(f"Fallback provider {fallback.PROVIDER_ID} failed: {fallback_error}")
                    continue
            
            # All providers failed
            raise RuntimeError("All cloud providers failed") from e
    
    async def _local_generate(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> str:
        """Generate using local Ollama provider."""
        import httpx
        
        model = self.config.local_model
        if model == "auto":
            model = self._get_auto_model()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        async with httpx.AsyncClient(timeout=self.config.timeout * 2) as client:
            response = await client.post(
                f"{self.config.local_host}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
    
    def _get_auto_model(self) -> str:
        """Auto-select local model based on system RAM."""
        import subprocess
        
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                ram_bytes = int(result.stdout.strip())
                ram_gb = ram_bytes / (1024 ** 3)
                
                if ram_gb < 6:
                    return "phi4-mini:3.8b-q4"
                elif ram_gb < 12:
                    return "granite3.1:2b-instruct"
                elif ram_gb < 24:
                    return "qwen2.5:7b"
                else:
                    return "qwen2.5:14b"
        except Exception:
            pass
        
        return "qwen2.5:7b"  # Default fallback
    
    async def validate(self) -> dict[str, Any]:
        """
        Validate provider configuration.
        
        Returns:
            Validation result with status and details
        """
        result = {
            "provider_type": self.config.provider_type.value,
            "configured": self.is_configured,
            "cloud_provider": None,
            "fallback_providers": [],
            "local_model": None,
            "errors": [],
        }
        
        # Validate cloud provider
        if self._cloud_provider:
            result["cloud_provider"] = {
                "id": self._cloud_provider.PROVIDER_ID,
                "name": self._cloud_provider.PROVIDER_NAME,
                "model": self._cloud_provider.model,
                "is_configured": self._cloud_provider.is_configured,
            }
            
            if self._cloud_provider.is_configured:
                try:
                    is_valid = await self._cloud_provider.validate_api_key()
                    result["cloud_provider"]["api_key_valid"] = is_valid
                    if not is_valid:
                        result["errors"].append("Cloud provider API key is invalid")
                except Exception as e:
                    result["errors"].append(f"Failed to validate cloud API key: {e}")
        
        # Validate fallback providers
        for provider in self._fallback_providers:
            fallback_info = {
                "id": provider.PROVIDER_ID,
                "name": provider.PROVIDER_NAME,
                "is_configured": provider.is_configured,
            }
            result["fallback_providers"].append(fallback_info)
        
        # Validate local model
        if self.config.provider_type in (ProviderType.LOCAL, ProviderType.HYBRID):
            model = self.config.local_model
            if model == "auto":
                model = self._get_auto_model()
            result["local_model"] = model
            
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self.config.local_host}/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        installed = [m["name"] for m in data.get("models", [])]
                        result["local_available"] = model in installed or any(model in m for m in installed)
                        result["local_installed_models"] = installed
                    else:
                        result["errors"].append("Ollama is not responding")
            except Exception as e:
                result["local_available"] = False
                result["errors"].append(f"Cannot connect to Ollama: {e}")
        
        return result
    
    def to_dict(self) -> dict[str, Any]:
        """Convert provider state to dictionary."""
        return {
            "provider_type": self.config.provider_type.value,
            "is_configured": self.is_configured,
            "cloud_provider": self._cloud_provider.to_dict() if self._cloud_provider else None,
            "fallback_count": len(self._fallback_providers),
            "local_host": self.config.local_host,
            "local_model": self.config.local_model,
        }
