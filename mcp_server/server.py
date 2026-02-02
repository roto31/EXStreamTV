"""
EXStreamTV MCP Server.

Model Context Protocol server that exposes project documentation, config schema,
and API overview. Use with Cursor, Claude Desktop, or any MCP client via stdio.

Run: python -m mcp_server
Or:  uv run python -m mcp_server
"""

import logging
import re
from pathlib import Path
from typing import Any

# Resolve project root (parent of mcp_server package)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Use stderr for logging so stdout is reserved for MCP JSON-RPC
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s %(levelname)s: %(message)s",
    stream=__import__("sys").stderr,
)
logger = logging.getLogger("exstreamtv-mcp")

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    try:
        from mcp.server.mcpserver import MCPServer as FastMCP
    except ImportError:
        raise ImportError(
            "MCP SDK not found. Install with: pip install mcp  (requires Python 3.10+)"
        ) from None

mcp = FastMCP(
    "exstreamtv",
    instructions="EXStreamTV project context: docs, config, API. Use for integration and development.",
)


def _read_version() -> str:
    """Read project version from VERSION file or exstreamtv package."""
    version_file = _PROJECT_ROOT / "VERSION"
    if version_file.is_file():
        return version_file.read_text().strip()
    try:
        from exstreamtv import __version__
        return __version__
    except ImportError:
        return "0.0.0"


def _list_md_files(dir_path: Path, prefix: str = "") -> list[dict[str, str]]:
    """List markdown files under dir_path with relative path and title."""
    out: list[dict[str, str]] = []
    if not dir_path.is_dir():
        return out
    for p in sorted(dir_path.rglob("*.md")):
        if "screenshots" in p.parts or "node_modules" in str(p):
            continue
        try:
            rel = p.relative_to(_PROJECT_ROOT)
            first_line = p.read_text(encoding="utf-8", errors="replace").split("\n")[0]
            title = first_line.strip().lstrip("#").strip() if first_line else p.stem
            out.append({
                "path": str(rel),
                "title": title,
            })
        except (ValueError, OSError):
            continue
    return out


@mcp.tool()
def get_project_info() -> dict[str, Any]:
    """
    Get EXStreamTV project summary: name, version, description, and key features.

    Returns:
        Dict with name, version, description, features, and doc paths.
    """
    readme = _PROJECT_ROOT / "README.md"
    description = ""
    if readme.is_file():
        raw = readme.read_text(encoding="utf-8", errors="replace")
        for line in raw.split("\n"):
            if line.startswith("**EXStreamTV**") or line.startswith("# EXStreamTV"):
                continue
            if line.strip().startswith("*") or line.strip() == "":
                break
            description = line.strip()
            if description:
                break
    if not description:
        description = "Unified IPTV streaming platform (StreamTV + ErsatzTV)."

    features = [
        "Direct online streaming (YouTube, Archive.org)",
        "Local media (Plex, Jellyfin, Emby, local folders)",
        "Hardware transcoding (NVENC, QSV, VAAPI, VideoToolbox, AMF)",
        "HDHomeRun emulation for Plex/Emby/Jellyfin",
        "AI-powered channel creation and log analysis",
        "macOS menu bar app with onboarding wizard",
    ]

    docs_dir = _PROJECT_ROOT / "docs" / "guides"
    guides = _list_md_files(docs_dir) if docs_dir.is_dir() else []

    return {
        "name": "EXStreamTV",
        "version": _read_version(),
        "description": description,
        "features": features,
        "project_root": str(_PROJECT_ROOT),
        "documentation_guides": [g["path"] for g in guides[:20]],
    }


@mcp.tool()
def search_documentation(query: str) -> str:
    """
    Search project documentation (docs/, README) for a text query.

    Args:
        query: Search phrase (case-insensitive).

    Returns:
        Concatenated snippets from matching markdown files with file path and excerpt.
    """
    if not query or not query.strip():
        return "Please provide a non-empty search query."

    pattern = re.compile(re.escape(query.strip()), re.IGNORECASE)
    results: list[str] = []
    seen: set[str] = set()

    for base in ["README.md", "CONTRIBUTING.md", "docs", "exstreamtv"]:
        base_path = _PROJECT_ROOT / base
        if base_path.is_file():
            files = [base_path]
        elif base_path.is_dir():
            files = list(base_path.rglob("*.md"))
        else:
            continue
        for path in files:
            if "screenshots" in path.parts or path in seen:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            seen.add(str(path))
            rel = path.relative_to(_PROJECT_ROOT) if path.is_relative_to(_PROJECT_ROOT) else path.name
            for i, line in enumerate(text.split("\n")):
                if pattern.search(line):
                    snippet = line.strip()[:400]
                    results.append(f"**{rel}** (line ~{i + 1}): {snippet}")
                    if len(results) >= 25:
                        return "\n\n".join(results)
    return "\n\n".join(results) if results else f"No documentation matches for: {query!r}"


@mcp.tool()
def get_doc(path_or_name: str) -> str:
    """
    Get the full content of a documentation file by path or short name.

    Args:
        path_or_name: Relative path (e.g. docs/guides/INSTALLATION.md) or
                      short name (e.g. INSTALLATION, QUICK_START, README).

    Returns:
        File content or error message.
    """
    path_or_name = path_or_name.strip()
    if not path_or_name:
        return "Provide a path or doc name (e.g. INSTALLATION, docs/guides/QUICK_START.md)."

    # Short names for guides
    name_map = {
        "installation": "docs/guides/INSTALLATION.md",
        "quick_start": "docs/guides/QUICK_START.md",
        "quickstart": "docs/guides/QUICK_START.md",
        "onboarding": "docs/guides/ONBOARDING.md",
        "ai_setup": "docs/guides/AI_SETUP.md",
        "macos_app": "docs/guides/MACOS_APP_GUIDE.md",
        "local_media": "docs/guides/LOCAL_MEDIA.md",
        "hw_transcoding": "docs/guides/HW_TRANSCODING.md",
        "readme": "README.md",
        "contributing": "CONTRIBUTING.md",
    }
    key = path_or_name.lower().replace("-", "_").replace(" ", "_").replace(".md", "")
    resolved = name_map.get(key) or path_or_name

    target = _PROJECT_ROOT / resolved
    if not target.is_file():
        return f"File not found: {resolved} (resolved from {path_or_name!r})."
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"Could not read file: {e}"


@mcp.tool()
def list_docs() -> list[dict[str, str]]:
    """
    List available documentation files (path and title) under docs/ and root README.

    Returns:
        List of dicts with 'path' and 'title'.
    """
    out: list[dict[str, str]] = []
    for base in ["README.md", "CONTRIBUTING.md", "docs"]:
        base_path = _PROJECT_ROOT / base
        if base_path.is_file():
            try:
                first = base_path.read_text(encoding="utf-8", errors="replace").split("\n")[0]
                title = first.strip().lstrip("#").strip() if first else base_path.stem
                out.append({"path": base, "title": title})
            except OSError:
                out.append({"path": base, "title": base_path.stem})
        elif base_path.is_dir():
            out.extend(_list_md_files(base_path))
    return out


@mcp.tool()
def get_config_schema() -> str:
    """
    Get the example configuration (config.example.yaml) and short description of sections.

    Returns:
        Full YAML content and a brief overview of server, database, ffmpeg, streaming, HDHomeRun.
    """
    example = _PROJECT_ROOT / "config.example.yaml"
    if not example.is_file():
        return "config.example.yaml not found in project root."
    try:
        content = example.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"Could not read config: {e}"

    overview = """
Config sections: server (host, port, log_level), database (url), ffmpeg (path, hardware_acceleration, defaults, timeouts), streaming (buffer_size, mpegts, hls), hdhomerun (emulation), ai (optional).
"""
    return content.strip() + "\n" + overview


@mcp.tool()
def get_api_overview() -> dict[str, Any]:
    """
    Get an overview of the EXStreamTV API modules (exstreamtv.api) and main app routes.

    Returns:
        Dict with api_modules list and high-level route categories.
    """
    api_dir = _PROJECT_ROOT / "exstreamtv" / "api"
    modules: list[str] = []
    if api_dir.is_dir():
        for p in sorted(api_dir.glob("*.py")):
            if p.name.startswith("_"):
                continue
            modules.append(p.stem)

    return {
        "api_modules": modules,
        "description": "FastAPI app in exstreamtv.main; routes include channels, schedules, playouts, libraries, FFmpeg, HDHomeRun, IPTV/M3U, AI, dashboard, health.",
        "web_ui": "http://localhost:8411 (default port from config.server.port)",
        "openapi_docs": "http://localhost:8411/docs",
    }


# Optional: expose key docs as resources so clients can read them by URI
@mcp.resource("exstreamtv://docs/README")
def resource_readme() -> str:
    """README.md content."""
    p = _PROJECT_ROOT / "README.md"
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


@mcp.resource("exstreamtv://config/example")
def resource_config_example() -> str:
    """config.example.yaml content."""
    p = _PROJECT_ROOT / "config.example.yaml"
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def main() -> None:
    """Run the MCP server over stdio (for Cursor/Claude Desktop)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
