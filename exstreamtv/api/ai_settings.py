"""
AI Settings API endpoints

Provides unified configuration for AI features including:
- Provider configuration (cloud/local/hybrid)
- Troubleshooting settings
- Persona preferences
- One-click setup operations
"""

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from exstreamtv.config import get_config, reload_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Settings"])


class AIProviderSettings(BaseModel):
    """AI provider configuration."""

    provider_type: str = "cloud"  # cloud, local, hybrid
    cloud_provider: str = "groq"
    cloud_api_key: str = ""
    cloud_model: str = "llama-3.3-70b-versatile"
    local_host: str = "http://localhost:11434"
    local_model: str = "auto"


class TroubleshootingSettings(BaseModel):
    """Troubleshooting configuration."""

    enabled: bool = True
    auto_fix: bool = False
    learning_enabled: bool = True
    include_app_logs: bool = True
    include_plex_logs: bool = True
    include_browser_logs: bool = True
    include_ollama_logs: bool = True


class AISettingsRequest(BaseModel):
    """Complete AI settings update request."""

    provider: AIProviderSettings | None = None
    troubleshooting: TroubleshootingSettings | None = None
    default_persona: str | None = None


class AISettingsResponse(BaseModel):
    """AI settings response."""

    provider: dict[str, Any]
    troubleshooting: dict[str, Any]
    default_persona: str
    ollama_status: dict[str, Any]
    personas: list[dict[str, Any]]


@router.get("/settings")
async def get_ai_settings() -> dict[str, Any]:
    """Get current AI configuration.

    Returns:
        dict[str, Any]: Current AI settings
    """
    config = get_config()

    # Get Ollama status
    ollama_status = await _get_ollama_status()

    # Get available personas
    from exstreamtv.ai_agent.persona_manager import get_persona_manager

    pm = get_persona_manager()
    personas = [p.to_dict() for p in pm.get_all_personas()]

    return {
        "provider": {
            "type": getattr(config.ai_agent, "provider_type", "cloud"),
            "cloud": {
                "provider": getattr(config.ai_agent, "cloud", {}).get("provider", "groq")
                if hasattr(config.ai_agent, "cloud")
                else "groq",
                "model": getattr(config.ai_agent, "cloud", {}).get("model", "llama-3.3-70b-versatile")
                if hasattr(config.ai_agent, "cloud")
                else "llama-3.3-70b-versatile",
                "api_key_set": bool(os.getenv("GROQ_API_KEY")),
            },
            "local": {
                "host": config.ai_agent.ollama.host,
                "model": config.ai_agent.ollama.model,
            },
        },
        "troubleshooting": {
            "enabled": config.auto_healer.enabled,
            "auto_fix": config.auto_healer.auto_fix,
            "learning_enabled": config.auto_healer.learning_enabled,
        },
        "default_persona": "tv_executive",
        "ollama_status": ollama_status,
        "personas": personas,
    }


async def _get_ollama_status() -> dict[str, Any]:
    """Get Ollama installation and server status."""
    from exstreamtv.api.ollama import (
        check_ollama_installed,
        check_ollama_server_running,
        get_installed_ollama_models,
        get_system_info,
    )

    installed = check_ollama_installed()
    server_running = check_ollama_server_running() if installed else False
    system_info = get_system_info()
    installed_models = get_installed_ollama_models() if installed and server_running else []

    return {
        "installed": installed,
        "server_running": server_running,
        "system_info": system_info,
        "installed_models": installed_models,
    }


@router.put("/settings")
async def update_ai_settings(settings: AISettingsRequest) -> dict[str, Any]:
    """Update AI configuration.

    Note: This updates in-memory config. To persist, config.yaml must be updated.

    Args:
        settings: New AI settings

    Returns:
        dict[str, Any]: Updated settings
    """
    config = get_config()

    if settings.provider:
        # Update provider settings
        if hasattr(config.ai_agent, "provider_type"):
            config.ai_agent.provider_type = settings.provider.provider_type

        config.ai_agent.ollama.host = settings.provider.local_host
        if settings.provider.local_model != "auto":
            config.ai_agent.ollama.model = settings.provider.local_model

    if settings.troubleshooting:
        config.auto_healer.enabled = settings.troubleshooting.enabled
        config.auto_healer.auto_fix = settings.troubleshooting.auto_fix
        config.auto_healer.learning_enabled = settings.troubleshooting.learning_enabled

    return await get_ai_settings()


@router.post("/settings/one-click/local")
async def setup_local_ai() -> dict[str, Any]:
    """One-click local AI setup (install Ollama, pull recommended model).

    Returns:
        dict[str, Any]: Setup result
    """
    from exstreamtv.api.ollama import (
        check_ollama_installed,
        check_ollama_server_running,
        get_recommended_models,
        get_system_info,
    )

    steps_completed = []
    errors = []

    # Step 1: Check/Install Ollama
    if not check_ollama_installed():
        try:
            result = await _install_ollama()
            if result["success"]:
                steps_completed.append("Ollama installed")
            else:
                errors.append(f"Ollama installation failed: {result.get('message')}")
                return {"success": False, "steps": steps_completed, "errors": errors}
        except Exception as e:
            errors.append(f"Ollama installation error: {e}")
            return {"success": False, "steps": steps_completed, "errors": errors}
    else:
        steps_completed.append("Ollama already installed")

    # Step 2: Check if server is running
    if not check_ollama_server_running():
        steps_completed.append("Note: Ollama server not running - start it manually")

    # Step 3: Recommend model based on system
    system_info = get_system_info()
    recommended = get_recommended_models(system_info)

    # Find best installable model
    best_model = None
    for model in recommended:
        if model.get("can_install", False):
            best_model = model
            break

    if best_model:
        steps_completed.append(f"Recommended model: {best_model['name']} ({best_model['id']})")

    return {
        "success": len(errors) == 0,
        "steps": steps_completed,
        "errors": errors,
        "recommended_model": best_model,
        "system_info": system_info,
    }


async def _install_ollama() -> dict[str, Any]:
    """Install Ollama."""
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # Try Homebrew first
            result = subprocess.run(
                ["brew", "--version"], check=False, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                result = subprocess.run(
                    ["brew", "install", "ollama"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if result.returncode == 0:
                    return {"success": True, "message": "Installed via Homebrew"}

            # Fallback to curl
            return {"success": False, "message": "Please install Ollama from https://ollama.com"}

        elif system == "Linux":
            return {"success": False, "message": "Please run: curl -fsSL https://ollama.com/install.sh | sh"}

        else:
            return {"success": False, "message": f"Unsupported platform: {system}"}

    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/settings/one-click/cloud")
async def setup_cloud_ai(request: Request) -> dict[str, Any]:
    """One-click cloud AI setup.

    Args:
        request: Request with provider and api_key

    Returns:
        dict[str, Any]: Setup result
    """
    body = await request.json()
    provider = body.get("provider", "groq")
    api_key = body.get("api_key", "")

    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    # Validate API key by making a test request
    try:
        if provider == "groq":
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0,
                )
                if response.status_code != 200:
                    return {
                        "success": False,
                        "message": f"Invalid API key: {response.status_code}",
                    }

        # Set environment variable
        os.environ[f"{provider.upper()}_API_KEY"] = api_key

        return {
            "success": True,
            "message": f"{provider.title()} API configured successfully",
            "provider": provider,
        }

    except Exception as e:
        return {"success": False, "message": f"Error validating API key: {e}"}


@router.post("/settings/one-click/troubleshooting")
async def setup_troubleshooting() -> dict[str, Any]:
    """One-click troubleshooting setup.

    Enables all troubleshooting features with safe defaults.

    Returns:
        dict[str, Any]: Setup result
    """
    config = get_config()

    # Enable troubleshooting with safe defaults
    config.auto_healer.enabled = True
    config.auto_healer.auto_fix = False  # Safe: require approval
    config.auto_healer.learning_enabled = True
    config.auto_healer.dry_run = True  # Safe: don't apply changes

    return {
        "success": True,
        "message": "Troubleshooting enabled with safe defaults",
        "settings": {
            "enabled": True,
            "auto_fix": False,
            "learning_enabled": True,
            "dry_run": True,
        },
    }


@router.get("/settings/test-connection")
async def test_ai_connection() -> dict[str, Any]:
    """Test AI provider connection.

    Returns:
        dict[str, Any]: Connection test results
    """
    results = {
        "ollama": {"available": False, "message": ""},
        "cloud": {"available": False, "message": ""},
    }

    # Test Ollama
    try:
        from exstreamtv.api.ollama import check_ollama_server_running

        if check_ollama_server_running():
            results["ollama"] = {"available": True, "message": "Ollama server is running"}
        else:
            results["ollama"] = {"available": False, "message": "Ollama server not responding"}
    except Exception as e:
        results["ollama"] = {"available": False, "message": str(e)}

    # Test cloud (Groq)
    try:
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    results["cloud"] = {"available": True, "message": "Groq API connected"}
                else:
                    results["cloud"] = {
                        "available": False,
                        "message": f"Groq API error: {response.status_code}",
                    }
        else:
            results["cloud"] = {"available": False, "message": "No API key configured"}
    except Exception as e:
        results["cloud"] = {"available": False, "message": str(e)}

    return results
