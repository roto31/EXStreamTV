"""
Troubleshooting Scripts API endpoints
"""

import logging
import os
import platform
import socket
import subprocess
import urllib.request
from pathlib import Path

from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Scripts"])

# Get base directory (project root)
BASE_DIR = Path(__file__).parent.parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"

# Available troubleshooting scripts
TROUBLESHOOTING_SCRIPTS = {
    "check_python": {
        "name": "Check Python Installation",
        "description": "Verifies Python installation and version",
        "script": "check_python.py",
        "type": "diagnostic",
    },
    "check_ffmpeg": {
        "name": "Check FFmpeg Installation",
        "description": "Verifies FFmpeg installation and version",
        "script": "check_ffmpeg.py",
        "type": "diagnostic",
    },
    "check_database": {
        "name": "Check Database",
        "description": "Checks database integrity and connectivity",
        "script": "check_database.py",
        "type": "diagnostic",
    },
    "check_ports": {
        "name": "Check Ports",
        "description": "Checks if required ports are available",
        "script": "check_ports.py",
        "type": "diagnostic",
    },
    "test_connectivity": {
        "name": "Test Connectivity",
        "description": "Tests network connectivity to media sources",
        "script": "test_connectivity.py",
        "type": "diagnostic",
    },
    "repair_database": {
        "name": "Repair Database",
        "description": "Attempts to repair corrupted database",
        "script": "repair_database.py",
        "type": "repair",
    },
    "clear_cache": {
        "name": "Clear Cache",
        "description": "Clears application cache",
        "script": "clear_cache.py",
        "type": "maintenance",
    },
}


@router.get("/scripts/list")
async def list_scripts() -> dict[str, Any]:
    """List all available troubleshooting scripts.

    Returns:
        dict[str, Any]: Dictionary with scripts list
    """
    return {"scripts": TROUBLESHOOTING_SCRIPTS}


@router.post("/scripts/{script_id}/run")
async def run_script(script_id: str, request: Request) -> dict[str, Any]:
    """Run a troubleshooting script.

    Args:
        script_id: Identifier of the script to run
        request: FastAPI request object

    Returns:
        dict[str, Any]: Script execution results with success, stdout, stderr, return_code

    Raises:
        HTTPException: If script not found, execution fails, or times out
    """
    if script_id not in TROUBLESHOOTING_SCRIPTS:
        raise HTTPException(status_code=404, detail="Script not found")

    script_info = TROUBLESHOOTING_SCRIPTS[script_id]
    script_path = SCRIPTS_DIR / script_info["script"]

    if not script_path.exists():
        # Try to create a simple diagnostic script on the fly
        if script_id == "check_python":
            return await _run_check_python()
        elif script_id == "check_ffmpeg":
            return await _run_check_ffmpeg()
        elif script_id == "check_database":
            return await _run_check_database()
        elif script_id == "check_ports":
            return await _run_check_ports()
        elif script_id == "test_connectivity":
            return await _run_test_connectivity()
        else:
            raise HTTPException(status_code=404, detail="Script file not found")

    try:
        # Run the script
        result = subprocess.run(
            ["python3", str(script_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(BASE_DIR),
        )

        return {
            "success": result.returncode == 0,
            "script_id": script_id,
            "script_name": script_info["name"],
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Script execution timed out")
    except Exception as e:
        logger.exception(f"Error running script {script_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error running script: {e!s}")


@router.post("/scripts/{script_id}/apply-fixes")
async def apply_fixes(script_id: str, request: Request) -> dict[str, Any]:
    """Apply automatic fixes recommended by a script.

    Args:
        script_id: Identifier of the script
        request: FastAPI request object with JSON body containing fixes to apply

    Returns:
        dict[str, Any]: Results of applying fixes with success status and applied/failed fixes

    Raises:
        HTTPException: If script not found, no fixes specified, or fix application fails
    """
    if script_id not in TROUBLESHOOTING_SCRIPTS:
        raise HTTPException(status_code=404, detail="Script not found")

    # Get the request body to see which fixes to apply
    try:
        body = await request.json()
        fixes_to_apply = body.get("fixes", [])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not fixes_to_apply:
        raise HTTPException(status_code=400, detail="No fixes specified")

    # Run the script first to get current recommendations
    script_result = await run_script(script_id, request)

    if "auto_fixes" not in script_result:
        return {
            "success": False,
            "message": "No automatic fixes available for this script",
            "script_result": script_result,
        }

    # Apply the requested fixes
    applied_fixes = []
    failed_fixes = []

    for fix_action in fixes_to_apply:
        # Find the fix definition
        fix_def = next(
            (f for f in script_result.get("auto_fixes", []) if f["action"] == fix_action), None
        )
        if not fix_def:
            failed_fixes.append({"action": fix_action, "error": "Fix definition not found"})
            continue

        try:
            # Execute the fix command
            if fix_def["requires_sudo"]:
                # For sudo commands, we need to use osascript on macOS to prompt for password
                if platform.system() == "Darwin":
                    # Use osascript to run sudo command with password prompt
                    # Escape quotes in the command
                    escaped_cmd = fix_def["command"].replace('"', '\\"')
                    apple_script = f'do shell script "{escaped_cmd}" with administrator privileges'
                    result = subprocess.run(
                        ["osascript", "-e", apple_script],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                else:
                    # On Linux, we can't easily prompt for sudo, so skip
                    failed_fixes.append(
                        {
                            "action": fix_action,
                            "error": "Sudo commands require manual execution on Linux",
                        }
                    )
                    continue
            else:
                # Non-sudo command - handle pip install specially
                cmd_parts = fix_def["command"].split()
                if cmd_parts[0] == "pip" and len(cmd_parts) > 1:
                    # Check if we're in a virtual environment
                    import sys

                    venv_python = sys.executable
                    # Use the current Python interpreter (which should be the venv if active)
                    cmd_parts = [venv_python, "-m", "pip", *cmd_parts[1:]]

                result = subprocess.run(
                    cmd_parts,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,  # Increased timeout for pip installs
                    cwd=str(BASE_DIR),
                    env=dict(os.environ, PYTHONUNBUFFERED="1"),  # Ensure output is not buffered
                )

            if result.returncode == 0:
                applied_fixes.append(
                    {
                        "action": fix_action,
                        "description": fix_def["description"],
                        "output": result.stdout,
                    }
                )
            else:
                failed_fixes.append(
                    {
                        "action": fix_action,
                        "description": fix_def["description"],
                        "error": result.stderr or "Command failed",
                    }
                )
        except subprocess.TimeoutExpired:
            failed_fixes.append({"action": fix_action, "error": "Command timed out"})
        except Exception as e:
            failed_fixes.append({"action": fix_action, "error": str(e)})

    return {
        "success": len(failed_fixes) == 0,
        "applied_fixes": applied_fixes,
        "failed_fixes": failed_fixes,
        "script_result": script_result,
    }



async def _run_check_python() -> dict[str, Any]:
    """Check Python installation.

    Returns:
        dict[str, Any]: Script execution results with Python version and path
    """
    import sys

    return {
        "success": True,
        "script_id": "check_python",
        "script_name": "Check Python Installation",
        "stdout": f"Python {sys.version}\nPath: {sys.executable}",
        "stderr": "",
        "return_code": 0,
    }


async def _run_check_ffmpeg() -> dict[str, Any]:
    """Check FFmpeg installation.

    Returns:
        dict[str, Any]: Script execution results with FFmpeg version and path
    """
    import shutil
    import subprocess

    ffmpeg_path = shutil.which("ffmpeg")

    if not ffmpeg_path:
        return {
            "success": False,
            "script_id": "check_ffmpeg",
            "script_name": "Check FFmpeg Installation",
            "stdout": "FFmpeg not found in PATH",
            "stderr": "Please install FFmpeg",
            "return_code": 1,
        }

    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], check=False, capture_output=True, text=True, timeout=5
        )
        version_line = result.stdout.split("\n")[0] if result.stdout else "Unknown version"
        return {
            "success": True,
            "script_id": "check_ffmpeg",
            "script_name": "Check FFmpeg Installation",
            "stdout": f"FFmpeg found at: {ffmpeg_path}\n{version_line}",
            "stderr": result.stderr,
            "return_code": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "script_id": "check_ffmpeg",
            "script_name": "Check FFmpeg Installation",
            "stdout": f"FFmpeg found at: {ffmpeg_path}",
            "stderr": f"Error checking version: {e!s}",
            "return_code": 1,
        }


async def _run_check_database() -> dict[str, Any]:
    """Check database connection and status.

    Returns:
        dict[str, Any]: Script execution results with database status and channel count
    """
    try:
        from exstreamtv.database.models import Channel
        from exstreamtv.database.session import SessionLocal

        db = SessionLocal()
        try:
            count = db.query(Channel).count()
            return {
                "success": True,
                "script_id": "check_database",
                "script_name": "Check Database",
                "stdout": f"Database connection OK\nChannels in database: {count}",
                "stderr": "",
                "return_code": 0,
            }
        finally:
            db.close()
    except Exception as e:
        return {
            "success": False,
            "script_id": "check_database",
            "script_name": "Check Database",
            "stdout": "",
            "stderr": f"Database error: {e!s}",
            "return_code": 1,
        }


async def _run_check_ports() -> dict[str, Any]:
    """Check if required ports are in use.

    Returns:
        dict[str, Any]: Script execution results with port status
    """
    import socket

    from exstreamtv.config import config

    output = []
    errors = []
    success = True

    from ..constants import HDHOMERUN_DEFAULT_PORT

    # HDHomeRun typically uses port 5004, but check config if available
    hdhr_port = (
        getattr(config.hdhr, "port", HDHOMERUN_DEFAULT_PORT)
        if hasattr(config, "hdhr")
        else HDHOMERUN_DEFAULT_PORT
    )

    ports_to_check = [
        (config.server.port, "StreamTV Server"),
        (hdhr_port, "HDHomeRun (if enabled)"),
    ]

    for port, name in ports_to_check:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()

        if result == 0:
            output.append(f"✓ Port {port} ({name}) is in use")
        else:
            output.append(f"✗ Port {port} ({name}) is available")

    return {
        "success": success,
        "script_id": "check_ports",
        "script_name": "Check Ports",
        "stdout": "\n".join(output),
        "stderr": "\n".join(errors) if errors else "",
        "return_code": 0 if success else 1,
    }


async def _run_test_connectivity() -> dict[str, Any]:
    """Test network connectivity and DNS resolution.

    Returns:
        dict[str, Any]: Script execution results with connectivity test results
    """
    output = []
    errors = []
    success = True

    # Test DNS resolution
    output.append("=== DNS Resolution Tests ===")
    domains = ["youtube.com", "www.youtube.com", "googlevideo.com", "archive.org", "google.com"]
    dns_ok = True

    for domain in domains:
        try:
            ip = socket.gethostbyname(domain)
            output.append(f"✓ {domain} -> {ip}")
        except socket.gaierror as e:
            output.append(f"✗ {domain} -> DNS ERROR: {e}")
            errors.append(f"DNS resolution failed for {domain}: {e}")
            dns_ok = False
            success = False
        except Exception as e:
            output.append(f"✗ {domain} -> ERROR: {e}")
            errors.append(f"Error resolving {domain}: {e}")
            dns_ok = False
            success = False

    # Test basic connectivity
    output.append("\n=== Basic Connectivity Tests ===")
    try:
        response = urllib.request.urlopen("https://www.google.com", timeout=10)
        output.append(f"✓ HTTP connectivity OK (status: {response.status})")
    except Exception as e:
        output.append(f"✗ HTTP connectivity FAILED: {e}")
        errors.append(f"HTTP connectivity error: {e}")
        success = False

    # Test YouTube accessibility
    output.append("\n=== YouTube Accessibility Tests ===")
    youtube_ok = True
    for domain in ["youtube.com", "www.youtube.com", "googlevideo.com"]:
        try:
            ip = socket.gethostbyname(domain)
            # Test port 443
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, 443))
            sock.close()
            if result == 0:
                output.append(f"✓ {domain} -> {ip} (port 443 accessible)")
            else:
                output.append(f"✗ {domain} -> {ip} (port 443 NOT accessible)")
                youtube_ok = False
                success = False
        except socket.gaierror as e:
            output.append(f"✗ {domain} -> DNS ERROR: {e}")
            errors.append(f"DNS error for {domain}: {e}")
            youtube_ok = False
            success = False
        except Exception as e:
            output.append(f"✗ {domain} -> ERROR: {e}")
            errors.append(f"Error testing {domain}: {e}")
            youtube_ok = False
            success = False

    # Test yt-dlp
    output.append("\n=== yt-dlp Test ===")
    ytdlp_installed = False
    try:
        import yt_dlp

        ytdlp_installed = True
        ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False)
            if info:
                output.append("✓ yt-dlp can access YouTube API")
            else:
                output.append("✗ yt-dlp connected but no data")
                success = False
    except ImportError:
        output.append("✗ yt-dlp not installed")
        errors.append("yt-dlp not installed - run: pip install yt-dlp")
        success = False
    except Exception as e:
        error_msg = str(e)
        if "nodename" in error_msg.lower() or "servname" in error_msg.lower():
            output.append(f"✗ yt-dlp DNS ERROR: {e}")
            errors.append(f"DNS resolution error in yt-dlp: {e}")
            errors.append("This matches your error! Try flushing DNS cache.")
            ytdlp_installed = True  # It's installed but has DNS issues
        else:
            output.append(f"✗ yt-dlp ERROR: {e}")
            errors.append(f"yt-dlp error: {e}")
        success = False

    # Recommendations and auto-fixable actions
    output.append("\n=== Recommendations ===")
    auto_fixes = []

    if not dns_ok:
        output.append("DNS Resolution Issues Detected:")
        if platform.system() == "Darwin":
            output.append("  Run: sudo dscacheutil -flushcache")
            output.append("  Run: sudo killall -HUP mDNSResponder")
            # Add auto-fix for DNS flush
            auto_fixes.append(
                {
                    "action": "flush_dns_cache",
                    "description": "Flush DNS cache (requires sudo password)",
                    "command": "dscacheutil -flushcache && killall -HUP mDNSResponder",
                    "requires_sudo": True,
                }
            )
        output.append("  Check DNS servers in System Preferences")
        output.append("  Try using Google DNS (8.8.8.8, 8.8.4.4)")

    # Add auto-fix for yt-dlp installation if not installed
    if not ytdlp_installed:
        output.append("yt-dlp Installation Required:")
        output.append("  yt-dlp is required for YouTube streaming")
        output.append("  Install with: pip install yt-dlp")
        # Add auto-fix for installing yt-dlp
        auto_fixes.append(
            {
                "action": "install_ytdlp",
                "description": "Install yt-dlp (required for YouTube streaming)",
                "command": "pip install yt-dlp",
                "requires_sudo": False,
            }
        )

    if not youtube_ok:
        output.append("YouTube Access Issues:")
        output.append("  The '[Errno 8] nodename nor servname provided' error is a DNS issue")
        output.append("  Flush DNS cache (see above)")
        output.append("  Check if YouTube works in browser")
        if ytdlp_installed:
            output.append("  Update yt-dlp: pip install --upgrade yt-dlp")
            # Add auto-fix for yt-dlp update only if it's already installed
            auto_fixes.append(
                {
                    "action": "update_ytdlp",
                    "description": "Update yt-dlp to latest version",
                    "command": "pip install --upgrade yt-dlp",
                    "requires_sudo": False,
                }
            )

    if success:
        output.append("All connectivity tests passed!")

    result = {
        "success": success,
        "script_id": "test_connectivity",
        "script_name": "Test Connectivity",
        "stdout": "\n".join(output),
        "stderr": "\n".join(errors) if errors else "",
        "return_code": 0 if success else 1,
    }

    # Add auto-fixes if available
    if auto_fixes:
        result["auto_fixes"] = auto_fixes

    return result
