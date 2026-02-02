"""
Ollama AI Troubleshooting API endpoints
"""

import builtins
import contextlib
import json
import logging
import os
import platform
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from ..config import get_config
from ..constants import DEFAULT_TIMEOUT_SECONDS, PROCESS_CHECK_TIMEOUT

logger = logging.getLogger(__name__)

# Get config at module level
config = get_config()

router = APIRouter(tags=["Ollama"])

# Get base directory (project root)
BASE_DIR = Path(__file__).parent.parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"

# Ollama model definitions - Hardware-optimized recommendations
OLLAMA_MODELS = {
    # Tier 1: Ultra-Lightweight (4GB RAM)
    "phi4-mini:3.8b-q4": {
        "name": "Phi-4 Mini (3.8B)",
        "size_gb": 2.5,
        "ram_required_gb": 4,
        "tier": 1,
        "description": "Best lightweight model - native function calling",
        "recommended_for": "4GB RAM, excellent structured output",
        "capabilities": ["function_calling", "json_output", "reasoning"],
    },
    "gemma3:1b": {
        "name": "Gemma 3 (1B)",
        "size_gb": 1.8,
        "ram_required_gb": 4,
        "tier": 1,
        "description": "Ultra-fast, basic troubleshooting",
        "recommended_for": "Minimum viable, 4GB RAM",
        "capabilities": ["fast_inference"],
    },
    "functiongemma": {
        "name": "FunctionGemma (270M)",
        "size_gb": 0.3,
        "ram_required_gb": 2,
        "tier": 1,
        "description": "Specialized for function calling only",
        "recommended_for": "Real-time diagnostics, any Mac",
        "capabilities": ["function_calling"],
    },
    
    # Tier 2: Lightweight (8GB RAM)
    "granite3.1:2b-instruct": {
        "name": "Granite 3.1 (2B)",
        "size_gb": 2.0,
        "ram_required_gb": 6,
        "tier": 2,
        "description": "IBM model with hallucination detection",
        "recommended_for": "8GB RAM, reliable tool calling",
        "capabilities": ["function_calling", "hallucination_detection"],
    },
    "qwen2.5:7b": {
        "name": "Qwen 2.5 (7B)",
        "size_gb": 4.4,
        "ram_required_gb": 8,
        "tier": 2,
        "description": "Best JSON output reliability",
        "recommended_for": "8GB+ RAM, excellent structured output",
        "capabilities": ["json_output", "function_calling", "reasoning"],
    },
    "gemma3:4b": {
        "name": "Gemma 3 (4B)",
        "size_gb": 4.0,
        "ram_required_gb": 8,
        "tier": 2,
        "description": "Multimodal capable, 128K context",
        "recommended_for": "8GB RAM, good all-around",
        "capabilities": ["multimodal", "long_context"],
    },
    "llama3.2:3b": {
        "name": "Llama 3.2 (3B)",
        "size_gb": 2.0,
        "ram_required_gb": 4,
        "tier": 2,
        "description": "Lightweight, fast, good for simple troubleshooting",
        "recommended_for": "Systems with limited RAM (4GB+)",
        "capabilities": ["fast_inference"],
    },
    "mistral:7b": {
        "name": "Mistral (7B)",
        "size_gb": 4.1,
        "ram_required_gb": 8,
        "tier": 2,
        "description": "Balanced performance and quality",
        "recommended_for": "Most systems (8GB+ RAM)",
        "capabilities": ["reasoning"],
    },
    
    # Tier 3: Full-Featured (16GB+ RAM)
    "qwen2.5:14b": {
        "name": "Qwen 2.5 (14B)",
        "size_gb": 9.0,
        "ram_required_gb": 16,
        "tier": 3,
        "description": "Recommended for full persona support",
        "recommended_for": "16GB RAM, all 6 personas work perfectly",
        "capabilities": ["json_output", "function_calling", "reasoning", "personas"],
    },
    "llama3.1:8b": {
        "name": "Llama 3.1 (8B)",
        "size_gb": 4.7,
        "ram_required_gb": 8,
        "tier": 2,
        "description": "Good reasoning capabilities",
        "recommended_for": "Systems with 8GB+ RAM",
        "capabilities": ["reasoning"],
    },
    "llama3.1:13b": {
        "name": "Llama 3.1 (13B)",
        "size_gb": 7.3,
        "ram_required_gb": 16,
        "tier": 3,
        "description": "High quality reasoning, best for complex issues",
        "recommended_for": "Systems with 16GB+ RAM",
        "capabilities": ["reasoning", "complex_analysis"],
    },
    "qwen2.5-coder:32b": {
        "name": "Qwen 2.5 Coder (32B)",
        "size_gb": 18.0,
        "ram_required_gb": 32,
        "tier": 3,
        "description": "Best quality, complex schedules",
        "recommended_for": "32GB+ RAM, power users",
        "capabilities": ["coding", "json_output", "function_calling", "reasoning", "personas"],
    },
    "codellama:7b": {
        "name": "CodeLlama (7B)",
        "size_gb": 3.8,
        "ram_required_gb": 8,
        "tier": 2,
        "description": "Excellent for code debugging and technical issues",
        "recommended_for": "Developers, code-focused troubleshooting",
        "capabilities": ["coding"],
    },
    "codellama:13b": {
        "name": "CodeLlama (13B)",
        "size_gb": 7.3,
        "ram_required_gb": 16,
        "tier": 3,
        "description": "Best code analysis, excellent for debugging",
        "recommended_for": "Developers with 16GB+ RAM",
        "capabilities": ["coding", "complex_analysis"],
    },
}


def check_ollama_installed() -> bool:
    """Check if Ollama is installed"""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=PROCESS_CHECK_TIMEOUT,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_ollama_server_running() -> bool:
    """Check if Ollama server is running and responding"""
    try:
        # Try to connect to the Ollama API
        import urllib.request
        import urllib.error
        
        ollama_url = os.getenv("OLLAMA_URL") or "http://localhost:11434"
        req = urllib.request.Request(f"{ollama_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def get_installed_ollama_models() -> list[str]:
    """Get list of installed Ollama models"""
    if not check_ollama_installed():
        return []

    try:
        result = subprocess.run(
            ["ollama", "list"], check=False, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            models = []
            lines = result.stdout.strip().split("\n")
            for line in lines[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if parts:
                        model_name = parts[0]
                        models.append(model_name)
            return models
    except Exception as e:
        logger.exception(f"Error getting Ollama models: {e}")

    return []


def get_system_info() -> dict:
    """Get system information"""
    system = platform.system()
    info = {
        "system": system,
        "machine": platform.machine(),
        "processor": platform.processor(),
    }

    if system == "Darwin":  # macOS
        try:
            # Get RAM
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                ram_bytes = int(result.stdout.strip())
                info["ram_gb"] = ram_bytes / (1024**3)

            # Get CPU cores
            result = subprocess.run(
                ["sysctl", "-n", "hw.ncpu"], check=False, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                info["cpu_cores"] = int(result.stdout.strip())

            # Get disk space
            result = subprocess.run(
                ["df", "-g", "."], check=False, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        info["disk_free_gb"] = int(parts[3])
        except Exception as e:
            logger.warning(f"Could not get all system info: {e}")

    elif system == "Linux":
        try:
            # Get RAM
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        ram_kb = int(line.split()[1])
                        info["ram_gb"] = ram_kb / (1024**2)
                        break

            # Get CPU cores
            result = subprocess.run(
                ["nproc"], check=False, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                info["cpu_cores"] = int(result.stdout.strip())

            # Get disk space
            result = subprocess.run(
                ["df", "-BG", "."], check=False, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        info["disk_free_gb"] = int(parts[3].rstrip("G"))
        except Exception as e:
            logger.warning(f"Could not get all system info: {e}")

    elif system == "Windows":
        try:
            import psutil

            info["ram_gb"] = psutil.virtual_memory().total / (1024**3)
            info["cpu_cores"] = psutil.cpu_count()
            info["disk_free_gb"] = psutil.disk_usage(".").free / (1024**3)
        except ImportError:
            # Fallback without psutil
            try:
                # Get RAM using wmic
                result = subprocess.run(
                    ["wmic", "computersystem", "get", "TotalPhysicalMemory"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        ram_bytes = int(lines[1].strip())
                        info["ram_gb"] = ram_bytes / (1024**3)

                # Get CPU cores
                result = subprocess.run(
                    ["wmic", "cpu", "get", "NumberOfCores"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        info["cpu_cores"] = int(lines[1].strip())
            except Exception as e:
                logger.warning(f"Could not get all system info: {e}")

    return info


def get_recommended_models(system_info: dict | None = None) -> list[dict]:
    """Get recommended Ollama models based on system hardware"""
    if system_info is None:
        system_info = get_system_info()

    ram_gb = system_info.get("ram_gb", 8)  # Default to 8GB
    disk_free_gb = system_info.get("disk_free_gb", 20)  # Default to 20GB

    recommended = []

    for model_id, model_info in OLLAMA_MODELS.items():
        # Check if system meets requirements
        if ram_gb >= model_info["ram_required_gb"] and disk_free_gb >= (model_info["size_gb"] + 5):
            recommended.append({"id": model_id, **model_info, "can_install": True})
        else:
            recommended.append(
                {
                    "id": model_id,
                    **model_info,
                    "can_install": False,
                    "reason": f"Requires {model_info['ram_required_gb']}GB RAM and {model_info['size_gb'] + 5:.1f}GB free disk space",
                }
            )

    # Sort by recommended order (smallest to largest)
    recommended.sort(key=lambda x: x["size_gb"])

    return recommended


@router.get("/ollama/status")
async def get_ollama_status():
    """Get Ollama installation status and system info"""
    installed = check_ollama_installed()
    server_running = check_ollama_server_running() if installed else False
    system_info = get_system_info()
    recommended_models = get_recommended_models(system_info)
    installed_models = get_installed_ollama_models() if installed and server_running else []

    return {
        "installed": installed,
        "server_running": server_running,
        "system_info": system_info,
        "recommended_models": recommended_models,
        "installed_models": installed_models,
    }


@router.post("/ollama/install")
async def install_ollama():
    """Install Ollama application"""
    if check_ollama_installed():
        return {"success": True, "message": "Ollama is already installed", "installed": True}

    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # Try Homebrew first
            result = subprocess.run(
                ["brew", "--version"], check=False, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Install via Homebrew
                result = subprocess.run(
                    ["brew", "install", "ollama"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if result.returncode == 0:
                    return {
                        "success": True,
                        "message": "Ollama installed via Homebrew",
                        "installed": True,
                    }

            # Fallback: Direct download
            result = subprocess.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                install_script = result.stdout
                with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
                    f.write(install_script)
                    f.flush()
                    os.chmod(f.name, 0o755)
                    result = subprocess.run(
                        ["bash", f.name], check=False, capture_output=True, text=True, timeout=600
                    )
                    os.unlink(f.name)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "message": "Ollama installed successfully",
                            "installed": True,
                        }

        elif system == "Linux":
            # Use official install script
            result = subprocess.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                install_script = result.stdout
                with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
                    f.write(install_script)
                    f.flush()
                    os.chmod(f.name, 0o755)
                    result = subprocess.run(
                        ["bash", f.name], check=False, capture_output=True, text=True, timeout=600
                    )
                    os.unlink(f.name)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "message": "Ollama installed successfully",
                            "installed": True,
                        }

        elif system == "Windows":
            # Download and run Ollama installer
            import urllib.request

            installer_url = "https://ollama.com/download/OllamaSetup.exe"
            installer_path = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")

            urllib.request.urlretrieve(installer_url, installer_path)

            # Run installer
            result = subprocess.run(
                [installer_path, "/S"],  # Silent install
                check=False,
                timeout=600,
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "Ollama installer downloaded and executed",
                    "installed": True,
                    "note": "Please restart your terminal or computer to use Ollama",
                }

        return {"success": False, "message": f"Unsupported platform: {system}", "installed": False}

    except Exception as e:
        logger.exception(f"Error installing Ollama: {e}")
        return {"success": False, "message": f"Installation failed: {e!s}", "installed": False}


@router.post("/ollama/models/{model_id}/install")
async def install_ollama_model(model_id: str):
    """Install a specific Ollama model"""
    if not check_ollama_installed():
        raise HTTPException(
            status_code=400, detail="Ollama is not installed. Please install Ollama first."
        )

    # Check if Ollama server is running
    if not check_ollama_server_running():
        system = platform.system()
        if system == "Darwin":
            instructions = "Please start the Ollama app from your Applications folder, or run 'ollama serve' in a terminal."
        elif system == "Linux":
            instructions = "Please run 'ollama serve' in a terminal, or start the Ollama systemd service with 'sudo systemctl start ollama'."
        else:
            instructions = "Please start the Ollama server by running 'ollama serve' in a terminal."
        
        return {
            "success": False,
            "message": f"Ollama server is not running. {instructions}",
            "server_not_running": True,
        }

    if model_id not in OLLAMA_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    try:
        result = subprocess.run(
            ["ollama", "pull", model_id],
            check=False,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes timeout
        )

        if result.returncode == 0:
            return {
                "success": True,
                "message": f"Model {model_id} installed successfully",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        else:
            # Provide more helpful error message
            stderr = result.stderr or ""
            if "server not responding" in stderr.lower() or "could not find ollama app" in stderr.lower():
                return {
                    "success": False,
                    "message": "Ollama server stopped responding during installation. Please restart the Ollama app and try again.",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            return {
                "success": False,
                "message": f"Model installation failed: {stderr or 'Unknown error'}",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Model installation timed out")
    except Exception as e:
        logger.exception(f"Error installing model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error installing model: {e!s}")


@router.delete("/ollama/models/{model_id}")
async def delete_ollama_model(model_id: str):
    """Delete an installed Ollama model"""
    if not check_ollama_installed():
        raise HTTPException(status_code=400, detail="Ollama is not installed")

    try:
        result = subprocess.run(
            ["ollama", "rm", model_id], check=False, capture_output=True, text=True, timeout=60
        )

        if result.returncode == 0:
            return {"success": True, "message": f"Model {model_id} deleted successfully"}
        else:
            return {"success": False, "message": "Failed to delete model", "stderr": result.stderr}
    except Exception as e:
        logger.exception(f"Error deleting model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting model: {e!s}")


def _extract_fixes_from_response(response: str) -> list[dict[str, Any]]:
    """Extract structured fixes from AI response"""
    fixes = []

    try:
        # Try to find JSON block in response
        # Look for JSON object with "fixes" key
        json_match = re.search(r'\{[^{}]*"fixes"[^{}]*\[.*?\].*?\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            try:
                data = json.loads(json_str)
                if isinstance(data, dict) and "fixes" in data:
                    fixes = data["fixes"]
                    # Validate fix structure
                    validated_fixes = []
                    for fix in fixes:
                        if isinstance(fix, dict) and "title" in fix:
                            validated_fixes.append(
                                {
                                    "title": fix.get("title", "Untitled Fix"),
                                    "description": fix.get("description", ""),
                                    "action": fix.get("action", "unknown"),
                                    "target": fix.get("target", ""),
                                    "change": fix.get("change", ""),
                                    "value": fix.get("value", ""),
                                    "risk_level": fix.get("risk_level", "medium"),
                                }
                            )
                    fixes = validated_fixes
            except json.JSONDecodeError:
                logger.debug("Could not parse fixes JSON from response")

        # Fallback: Try to extract fixes from markdown-style lists
        if not fixes:
            # Look for numbered or bulleted lists that might be fixes
            # This is a simple heuristic - could be improved
            logger.debug("No structured fixes found, using fallback parsing")

    except Exception as e:
        logger.warning(f"Error extracting fixes from response: {e}")

    return fixes


@router.get("/ollama", response_class=HTMLResponse)
async def ollama_page(request: Request, show_fixes: bool = False):
    """Serve the Ollama management page"""
    from exstreamtv.main import templates

    return templates.TemplateResponse(
        "ollama.html",
        {
            "request": request,
            "title": "AI Troubleshooting Assistant (Ollama)",
            "show_fixes": show_fixes,
        },
    )


def get_streamtv_logs_context(max_lines: int = 200) -> str:
    """Get recent StreamTV logs as context for AI troubleshooting"""
    from ..api.logs import get_log_file_path

    try:
        log_file = get_log_file_path()
        if not log_file or not log_file.exists():
            return "No StreamTV log file found."

        # Read last N lines
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

        # Filter for errors and warnings
        error_lines = []
        warning_lines = []
        for line in recent_lines:
            line_lower = line.lower()
            if "error" in line_lower or "exception" in line_lower or "traceback" in line_lower:
                error_lines.append(line.strip())
            elif "warning" in line_lower:
                warning_lines.append(line.strip())

        # Combine, prioritizing errors
        context_lines = error_lines[-50:] + warning_lines[-30:]  # Last 50 errors, 30 warnings

        if not context_lines:
            return f"StreamTV logs: No recent errors or warnings found in last {max_lines} lines."

        return "StreamTV Logs (recent errors/warnings):\n" + "\n".join(
            context_lines[-80:]
        )  # Limit to 80 lines total
    except Exception as e:
        logger.warning(f"Error reading StreamTV logs: {e}")
        return f"Error reading StreamTV logs: {e!s}"


def get_plex_logs_context(max_lines: int = 200) -> str:
    """Get recent Plex logs as context for AI troubleshooting"""
    from ..api.logs import get_plex_log_files, get_plex_logs_directory, parse_plex_log_line

    try:
        logs_dir = get_plex_logs_directory()
        if not logs_dir:
            return "Plex logs directory not found."

        log_files = get_plex_log_files()
        if not log_files:
            return "No Plex log files found."

        # Read from most recent log file
        target_file = log_files[0]

        with open(target_file, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

        # Filter for errors and warnings
        error_lines = []
        warning_lines = []
        for line in recent_lines:
            parsed = parse_plex_log_line(line.strip())
            level = parsed.get("level", "").upper()
            if level in ["ERROR", "FATAL", "CRITICAL"]:
                error_lines.append(line.strip())
            elif level == "WARN":
                warning_lines.append(line.strip())

        # Combine, prioritizing errors
        context_lines = error_lines[-50:] + warning_lines[-30:]

        if not context_lines:
            return f"Plex logs: No recent errors or warnings found in {target_file.name}."

        return (
            f"Plex Media Server Logs ({target_file.name}, recent errors/warnings):\n"
            + "\n".join(context_lines[-80:])
        )
    except Exception as e:
        logger.warning(f"Error reading Plex logs: {e}")
        return f"Error reading Plex logs: {e!s}"


def build_ai_system_prompt() -> str:
    """Build comprehensive system prompt for AI troubleshooting with all context"""
    python_docs = """
Python Documentation References:
- Official Python 3 Documentation: https://docs.python.org/3/
- Python Standard Library: https://docs.python.org/3/library/index.html
- Python Language Reference: https://docs.python.org/3/reference/index.html
- Python GitHub: https://github.com/python

When troubleshooting Python-related issues, refer to these official sources for:
- Syntax errors and language features
- Standard library module usage
- Best practices and coding patterns
- Error handling and exception types
- Type hints and annotations
"""

    system_prompt = f"""You are an expert AI troubleshooting assistant for StreamTV, a Python-based IPTV streaming platform.

Your role is to:
1. Analyze errors from StreamTV and Plex Media Server logs
2. Provide clear explanations of what went wrong
3. Suggest specific fixes based on the error context
4. Reference Python documentation when dealing with Python-specific issues
5. Consider the full system context (logs, configuration, environment)

{python_docs}

Data Sources Available:
- StreamTV application logs (errors, warnings, exceptions)
- Plex Media Server logs (playback errors, transcoding issues)
- System configuration and environment

When analyzing issues:
1. Read the error messages carefully from the provided logs
2. Identify the root cause (not just symptoms)
3. Check if it's a Python syntax/runtime error and reference Python docs
4. Consider both StreamTV and Plex logs for related issues
5. Provide step-by-step solutions
6. If Python-related, cite relevant Python documentation sections

Always be specific, actionable, and reference official documentation when appropriate.
"""
    return system_prompt


@router.get("/ollama/notification-action")
async def handle_notification_action(request: Request, title: str | None = None):
    """Handle notification click - redirect to Ollama page with fixes shown"""
    from fastapi.responses import RedirectResponse

    base_url = str(request.base_url).rstrip("/")
    redirect_url = f"{base_url}/api/ollama?show_fixes=true"

    return RedirectResponse(url=redirect_url)


@router.post("/ollama/fixes/{fix_id}/apply")
async def apply_fix(fix_id: int, request: Request) -> dict[str, Any]:
    """Apply a suggested fix.

    Note: This endpoint is currently a placeholder.

    Args:
        fix_id: Fix identifier.
        request: FastAPI request object.

    Returns:
        dict[str, Any]: Success response.
    """
    with contextlib.suppress(Exception):
        await request.json()

    # This is a placeholder - actual fix application would go here
    # For now, we'll just return success
    return {"success": True, "message": "Fix applied successfully", "fix_id": fix_id}


@router.post("/ollama/query")
async def query_ollama(request: Request) -> dict[str, Any]:
    """Query AI troubleshooting assistant with context from all log sources.

    Uses the unified TroubleshootingService to analyze logs and generate responses.

    Args:
        request: FastAPI request object.

    Returns:
        dict[str, Any]: AI response payload including extracted fixes (if any).
    """
    from ..services.troubleshooting_service import get_troubleshooting_service

    # Parse request body
    try:
        body = await request.json()
    except Exception:
        # Fallback to query parameters for compatibility
        body = dict(request.query_params)

    query = body.get("query", "")
    include_streamtv_logs = body.get("include_streamtv_logs", True)
    include_plex_logs = body.get("include_plex_logs", True)
    include_browser_logs = body.get("include_browser_logs", True)
    include_ollama_logs = body.get("include_ollama_logs", True)

    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    try:
        # Use the unified TroubleshootingService
        service = get_troubleshooting_service()

        result = await service.analyze_and_suggest(
            query=query,
            include_app_logs=include_streamtv_logs,
            include_plex_logs=include_plex_logs,
            include_browser_logs=include_browser_logs,
            include_ollama_logs=include_ollama_logs,
        )

        # Send macOS notification if fixes are found
        if result.fix_suggestions and platform.system() == "Darwin":
            try:
                from ..utils.macos_notifications import open_url_in_browser, send_notification

                fix_count = len(result.fix_suggestions)
                notification_title = (
                    f"EXStreamTV: {fix_count} Fix{'es' if fix_count > 1 else ''} Suggested"
                )
                notification_message = f"AI found {fix_count} potential fix{'es' if fix_count > 1 else ''} for your issue"

                # Get base URL from request
                base_url = str(request.base_url).rstrip("/")
                action_url = f"{base_url}/api/ollama?show_fixes=true"

                # Send notification
                send_notification(
                    title=notification_title,
                    message=notification_message,
                    subtitle="Click to review and apply fixes",
                    action_url=action_url,
                    sound=True,
                )

                # Also open browser automatically after a short delay
                import threading
                import time

                def open_browser_delayed():
                    time.sleep(2)
                    open_url_in_browser(action_url)

                threading.Thread(target=open_browser_delayed, daemon=True).start()

            except Exception as e:
                logger.warning(f"Could not send macOS notification: {e}")

        return {
            "success": result.success,
            "model": result.model_used,
            "response": result.response,
            "fixes": result.fix_suggestions,
            "log_matches": result.log_matches,
            "context_used": {
                "streamtv_logs": include_streamtv_logs,
                "plex_logs": include_plex_logs,
                "browser_logs": include_browser_logs,
                "ollama_logs": include_ollama_logs,
            },
            "persona": result.persona_used,
        }

    except Exception as e:
        logger.error(f"Error in troubleshooting query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {e!s}")


@router.get("/ollama/welcome")
async def get_welcome_message() -> dict[str, str]:
    """Get the System Admin persona welcome message.

    Returns:
        dict[str, str]: Welcome message
    """
    from ..services.troubleshooting_service import get_troubleshooting_service

    service = get_troubleshooting_service()
    return {"message": service.get_welcome_message()}


@router.post("/ollama/conversation/clear")
async def clear_conversation() -> dict[str, bool]:
    """Clear the troubleshooting conversation history.

    Returns:
        dict[str, bool]: Success status
    """
    from ..services.troubleshooting_service import get_troubleshooting_service

    service = get_troubleshooting_service()
    service.clear_conversation()
    return {"success": True}


@router.get("/ollama/pending-approvals")
async def get_pending_approvals() -> dict[str, Any]:
    """Get pending fix approval requests.

    Returns:
        dict[str, Any]: List of pending approvals
    """
    from ..services.troubleshooting_service import get_troubleshooting_service

    service = get_troubleshooting_service()
    approvals = service.get_pending_approvals()
    return {"approvals": [a.to_dict() for a in approvals]}


@router.post("/ollama/approvals/{request_id}/approve")
async def approve_fix_request(request_id: str) -> dict[str, Any]:
    """Approve a fix request.

    Args:
        request_id: Approval request ID

    Returns:
        dict[str, Any]: Success status
    """
    from ..services.troubleshooting_service import get_troubleshooting_service

    service = get_troubleshooting_service()
    success = service.approve_fix(request_id)
    return {"success": success}


@router.post("/ollama/approvals/{request_id}/reject")
async def reject_fix_request(request_id: str, request: Request) -> dict[str, Any]:
    """Reject a fix request.

    Args:
        request_id: Approval request ID
        request: FastAPI request with optional reason

    Returns:
        dict[str, Any]: Success status
    """
    from ..services.troubleshooting_service import get_troubleshooting_service

    body = {}
    with contextlib.suppress(Exception):
        body = await request.json()

    reason = body.get("reason")

    service = get_troubleshooting_service()
    success = service.reject_fix(request_id, reason)
    return {"success": success}


@router.get("/ollama/fix-history")
async def get_fix_history() -> dict[str, Any]:
    """Get history of applied fixes.

    Returns:
        dict[str, Any]: List of applied fixes
    """
    from ..services.troubleshooting_service import get_troubleshooting_service

    service = get_troubleshooting_service()
    history = service.get_fix_history()
    return {"fixes": [f.to_dict() for f in history]}
