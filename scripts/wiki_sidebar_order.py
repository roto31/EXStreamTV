"""Wiki page stems in EXStreamTV.wiki sidebar order (single source of truth)."""

from __future__ import annotations

SIDEBAR_STEMS: tuple[str, ...] = (
    "Home",
    "Platform-Guide",
    "Installation",
    "Quick-Start",
    "Onboarding",
    "AI-Setup",
    "Channel-Creation-Guide",
    "Local-Media",
    "Hardware-Transcoding",
    "macOS-App-Guide",
    "Navigation-Guide",
    "Streaming-Stability",
    "Advanced-Scheduling",
    "API-Reference",
    "System-Design",
    "Architecture-Diagrams",
    "Pattern-Refactor-Sources",
    "ADR-Channel-Manager-Database",
    "EXStreamTV-UI-Architecture",
    "Architecture",
    "Streaming-Internals",
    "HDHomeRun-Emulation",
    "Metadata-And-XMLTV",
    "AI-Agent-And-Containment",
    "Restart-Safety-Model",
    "Observability",
    "Troubleshooting",
    "Log-Interpretation",
    "Tunarr-DizqueTV-Integration",
    "Distribution",
    "Build-Progress",
    "Operational-Guide",
    "Feature-Flags",
    "Invariants",
    "CI-CD-And-Testing",
    "Deployment",
    "Production-Certification",
    "Changelog",
    "Integration-Plan",
    "Lessons-Learned",
    "StreamTV-Migration-QuickStart",
    "StreamTV-Schema-Mapping",
    "Platform-Comparison",
    "MCP-Server",
    "Documentation-Changelog",
    "EXStreamTV",
)


def display_title(stem: str) -> str:
    """Human title for Confluence (no Mirror prefix)."""
    return stem.replace("-", " ")


def confluence_wiki_child_title(stem: str) -> str:
    """Title for a wiki-backed Confluence page (must not collide with root landing title)."""
    if stem == "EXStreamTV":
        return "EXStreamTV Wiki"
    return display_title(stem)
