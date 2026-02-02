"""
Documentation and Troubleshooting API endpoints
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documentation"])

# Get base directory (project root)
BASE_DIR = Path(__file__).parent.parent.parent
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Try to import markdown, fallback to simple conversion if not available
try:
    import markdown

    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    logger.warning("markdown library not available, using basic markdown conversion")


def markdown_to_html(markdown_content: str) -> str:
    """Convert markdown to HTML with script link support"""
    import re

    def build_script_button(script_id: str, label: str) -> str:
        """Generate a troubleshooting button without inline JS."""
        safe_script_id = html.escape(script_id, quote=True)
        args_attr = html.escape(json.dumps([script_id]), quote=True)
        safe_label = html.escape(label, quote=False)
        return (
            '<button class="troubleshooting-script-btn" '
            f'data-script-id="{safe_script_id}" '
            'data-action="runTroubleshootingScript" '
            f'data-args="{args_attr}">'
            '<span class="material-icons">play_arrow</span>'
            f"<span>{safe_label}</span>"
            "</button>"
        )

    # First, extract script links with their full context (including text after the link)
    # Pattern: - [Run Script: script_id](script:script_id) - Description text
    # We need to capture the full line to preserve the description
    script_link_pattern = r"(- \[Run Script: ([^\]]+)\]\(script:([^\)]+)\))(\s*-\s*)?(.*?)(?=\n|$)"

    def extract_script_link(match):
        """Extract script link info before markdown conversion"""
        script_id = match.group(3)
        link_text = match.group(2)
        description = match.group(5).strip() if match.group(5) else ""

        # Store for later replacement
        if not hasattr(markdown_to_html, "_script_links"):
            markdown_to_html._script_links = []

        # Create placeholder that will be replaced after markdown conversion
        placeholder = f"__SCRIPT_BUTTON_{len(markdown_to_html._script_links)}__"
        markdown_to_html._script_links.append(
            {
                "placeholder": placeholder,
                "script_id": script_id,
                "link_text": link_text,
                "description": description,
            }
        )

        # Replace with just placeholder (description will be added to button)
        return f"- {placeholder}"

    # Extract script links before markdown conversion
    if not hasattr(markdown_to_html, "_script_links"):
        markdown_to_html._script_links = []
    else:
        markdown_to_html._script_links = []

    markdown_content = re.sub(
        script_link_pattern, extract_script_link, markdown_content, flags=re.MULTILINE
    )

    if MARKDOWN_AVAILABLE:
        md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
        html_content = md.convert(markdown_content)
    else:
        # Basic markdown conversion
        html = markdown_content
        # Headers
        html = re.sub(r"^# (.*?)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.*?)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^### (.*?)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        # Code blocks
        html = re.sub(r"```(\w+)?\n(.*?)```", r"<pre><code>\2</code></pre>", html, flags=re.DOTALL)
        # Inline code
        html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
        # Images (must come before links - matches ![alt](url))
        html = re.sub(r"!\[([^\]]*)\]\(([^\)]+)\)", r'<img src="\2" alt="\1" style="max-width: 100%; border-radius: 8px; margin: 16px 0;">', html)
        # Links (but skip script: links as they're already handled)
        html = re.sub(r"\[([^\]]+)\]\((?!script:)([^\)]+)\)", r'<a href="\2">\1</a>', html)
        # Bold
        html = re.sub(r"\*\*([^\*]+)\*\*", r"<strong>\1</strong>", html)
        # Lists
        html = re.sub(r"^\* (.*?)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        html = re.sub(r"(<li>.*</li>)", r"<ul>\1</ul>", html, flags=re.DOTALL)
        # Paragraphs
        html = re.sub(r"\n\n", r"</p><p>", html)
        html = "<p>" + html + "</p>"
        html_content = html

    # Replace placeholders with actual script buttons
    for script_info in markdown_to_html._script_links:
        clean_text = script_info["link_text"].replace("Run Script: ", "").strip()
        # Combine script ID and description nicely
        if script_info["description"]:
            # Remove leading dash and spaces from description
            desc = script_info["description"].lstrip(" -")
            full_text = f"{clean_text} - {desc}"
        else:
            full_text = clean_text
        button_html = build_script_button(script_info["script_id"], full_text)
        html_content = html_content.replace(script_info["placeholder"], button_html)

    # Also handle any remaining script: links that weren't caught by the pattern
    script_pattern = r'<a href="script:([^"]+)">([^<]+)</a>'

    def replace_script_link(match):
        script_id = match.group(1)
        link_text = match.group(2)
        clean_text = link_text.replace("Run Script: ", "").strip()
        return build_script_button(script_id, clean_text)

    html_content = re.sub(script_pattern, replace_script_link, html_content)

    # Clear script links for next call
    markdown_to_html._script_links = []

    return html_content


# Comprehensive documentation files mapping
# Maps doc_type routes to actual markdown files in the docs folder
DOCS_FILES = {
    # Main Guides
    "beginner": "docs/BEGINNER_GUIDE.md",
    "intermediate": "docs/INTERMEDIATE_GUIDE.md",
    "expert": "docs/EXPERT_GUIDE.md",
    # Installation Guides
    "installation": "docs/INSTALLATION.md",
    "quick_start": "docs/installation/QUICK_START.md",
    "path_independence": "docs/implementation/PATH_INDEPENDENCE.md",
    # GUI Installers
    "gui_installer": "docs/installation/GUI_INSTALLER_README.md",
    "swiftui_installer": "docs/installation/SWIFTUI_INSTALLER_README.md",
    "swiftui_readme": "docs/swiftui/README_SWIFTUI.md",
    "swiftui_quick_start": "docs/installation/QUICK_START_SWIFTUI.md",
    "swiftui_build": "docs/swiftui/BUILD_SWIFTUI.md",
    # API & Integration
    "api": "docs/API.md",
    "hdhomerun": "docs/HDHOMERUN.md",
    "schedules": "docs/SCHEDULES.md",
    "yaml_validation": "docs/YAML_VALIDATION.md",
    "ersatztv_integration": "docs/ERSATZTV_INTEGRATION.md",
    "ersatztv_complete": "docs/ERSATZTV_COMPLETE_INTEGRATION.md",
    # Authentication
    "authentication": "docs/AUTHENTICATION.md",
    "authentication_system": "docs/AUTHENTICATION_SYSTEM.md",
    "passkey_authentication": "docs/PASSKEY_AUTHENTICATION.md",
    # Plex Integration
    "plex_setup": "docs/plex/PLEX_SETUP_COMPLETE.md",
    "plex_integration": "docs/plex/PLEX_INTEGRATION_COMPLETE.md",
    "plex_api_schedule": "docs/plex/PLEX_API_SCHEDULE_INTEGRATION_COMPLETE.md",
    "plex_epg": "docs/plex/PLEX_EPG_INTEGRATION.md",
    "plex_schedule": "docs/plex/PLEX_SCHEDULE_INTEGRATION.md",
    "plex_connection_fix": "docs/plex/PLEX_CONNECTION_FIX.md",
    "plex_channel_scan_fix": "docs/plex/PLEX_CHANNEL_SCAN_FIX.md",
    "plex": "docs/plex/README.md",
    # Logging
    "logging": "docs/LOGGING.md",
    "logging_quickstart": "docs/logging/LOGGING_QUICKSTART.md",
    "logging_system": "docs/logging/LOGGING_SYSTEM_SUMMARY.md",
    "logging_implementation": "docs/logging/LOGGING_IMPLEMENTATION_COMPLETE.md",
    "logging_summary": "docs/logging/LOGGING_COMPLETE_SUMMARY.md",
    # Archive Parser
    "archive_parser": "docs/archive-parser/README.md",
    "archive_parser_quick": "docs/archive-parser/QUICK_REFERENCE_ARCHIVE_PARSER.md",
    "archive_parser_magnum": "docs/archive-parser/MAGNUM_PI_CHANNEL_COMPLETE.md",
    "archive_parser_usage": "docs/archive-parser/USAGE_EXAMPLES.md",
    "archive_parser_implementation": "docs/archive-parser/ARCHIVE_PARSER_IMPLEMENTATION_SUMMARY.md",
    "archive_parser_redirect": "docs/archive-parser/ARCHIVE_ORG_REDIRECT_FIX.md",
    "archive_parser_restart": "docs/archive-parser/MAGNUM_PI_RESTART_COMPLETE.md",
    # Implementation & Technical
    "implementation": "docs/implementation/README.md",
    "project_structure": "docs/implementation/PROJECT_STRUCTURE.md",
    "ersatztv_status": "docs/implementation/ERSATZTV_INTEGRATION_STATUS.md",
    "ersatztv_summary": "docs/implementation/ERSATZTV_INTEGRATION_SUMMARY.md",
    "security_audit": "docs/implementation/SECURITY_AUDIT_REPORT.md",
    "security_fixes": "docs/implementation/SECURITY_FIXES_IMPLEMENTED.md",
    "github_pages": "docs/implementation/GITHUB_PAGE_SUMMARY.md",
    "schedule_breaks_fix": "docs/implementation/SCHEDULE_BREAKS_FIX.md",
    "schedule_file_naming": "docs/implementation/SCHEDULE_FILE_NAMING.md",
    "ffmpeg_hwaccel_fix": "docs/implementation/FFMPEG_HWACCEL_FIX.md",
    # Features
    "auto_healer": "docs/AUTO_HEALER.md",
    "comparison": "docs/COMPARISON.md",
    "metadata_enrichment": "docs/guides/METADATA_ENRICHMENT.md",
    # Troubleshooting
    "troubleshooting": "docs/TROUBLESHOOTING.md",
    "troubleshooting_scripts": "docs/TROUBLESHOOTING_SCRIPTS.md",
    # Navigation & Channel Guides
    "navigation": "docs/guides/NAVIGATION_GUIDE.md",
    "channel_creation": "docs/guides/CHANNEL_CREATION_GUIDE.md",
    # Installation sub-pages
    "youtube_api_setup": "docs/installation/YOUTUBE_API_SETUP.md",
    "install_macos": "docs/installation/INSTALL_MACOS.md",
    # SwiftUI
    "swiftui": "docs/swiftui/README.md",
    # Index
    "index": "docs/INDEX.md",
    "readme": "docs/README.md",
}

# Legacy mapping for backward compatibility
DOCS_FILES_MACOS = DOCS_FILES


@router.get("/docs/{doc_type}", response_class=HTMLResponse)
async def get_documentation(doc_type: str, request: Request) -> HTMLResponse:
    """Get documentation page.

    Args:
        doc_type: Documentation type identifier
        request: FastAPI request object

    Returns:
        HTMLResponse: Documentation page

    Raises:
        HTTPException: If documentation loading fails
    """
    doc_file = DOCS_FILES.get(doc_type)

    if doc_file:
        doc_path = BASE_DIR / doc_file
        if doc_path.exists():
            try:
                with open(doc_path, encoding="utf-8") as f:
                    markdown_content = f.read()

                html_content = markdown_to_html(markdown_content)

                # Get title from first h1 or use doc_type
                title_match = markdown_content.split("\n")[0] if markdown_content else None
                if title_match and title_match.startswith("#"):
                    title = title_match.replace("#", "").strip()
                else:
                    title = doc_type.replace("_", " ").title()

                return templates.TemplateResponse(
                    "documentation.html",
                    {
                        "request": request,
                        "title": title,
                        "content": html_content,
                        "doc_type": doc_type,
                    },
                )
            except Exception as e:
                logger.exception(f"Error reading documentation file: {e}")
                raise HTTPException(status_code=500, detail=f"Error loading documentation: {e!s}")
        else:
            logger.warning(f"Documentation file not found: {doc_path}")

    # If not found, return a placeholder
    return templates.TemplateResponse(
        "documentation.html",
        {
            "request": request,
            "title": doc_type.replace("_", " ").title(),
            "content": f"<h1>{doc_type.replace('_', ' ').title()}</h1><p>Documentation for {doc_type} is coming soon.</p><p><em>File path checked: {doc_file if doc_file else 'No mapping found'}</em></p>",
            "doc_type": doc_type,
        },
    )


@router.get("/documentation", response_class=HTMLResponse)
async def docs_index(request: Request) -> HTMLResponse:
    """Documentation index page - shows main docs/README.md if available.

    Args:
        request: FastAPI request object

    Returns:
        HTMLResponse: Documentation index page
    """
    # Try to load the main docs README
    docs_readme = BASE_DIR / "docs" / "README.md"
    if docs_readme.exists():
        try:
            with open(docs_readme, encoding="utf-8") as f:
                markdown_content = f.read()
            html_content = markdown_to_html(markdown_content)
            return templates.TemplateResponse(
                "documentation.html",
                {
                    "request": request,
                    "title": "StreamTV Documentation",
                    "content": html_content,
                    "doc_type": "index",
                },
            )
        except Exception as e:
            logger.exception(f"Error reading docs README: {e}")

    # Fallback to basic index
    return templates.TemplateResponse(
        "documentation.html",
        {
            "request": request,
            "title": "Documentation",
            "content": "<h1>StreamTV Documentation</h1><p>Select a documentation section from the sidebar.</p>",
            "doc_type": "index",
        },
    )
