#!/usr/bin/env python3
"""
Sync EXStreamTV documentation to GitHub Wiki format.

Reads docs from the repo, rewrites internal links to Wiki page names,
preserves Mermaid blocks, and writes Markdown files suitable for
pushing to https://github.com/roto31/EXStreamTV.wiki.git.

Usage:
  # From project root, with wiki repo cloned alongside or in --wiki-dir
  python scripts/sync_docs_to_wiki.py [--wiki-dir path/to/EXStreamTV.wiki]

If --wiki-dir is omitted, writes to ./wiki_out/; copy contents into
your wiki clone and push.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from typing import Final

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"

# Map: Wiki page filename (no .md) -> source path relative to project root
WIKI_PAGE_SOURCES: Final[dict[str, str]] = {
    "Home": "docs/README.md",
    "Installation": "docs/guides/INSTALLATION.md",
    "Quick-Start": "docs/guides/QUICK_START.md",
    "Onboarding": "docs/guides/ONBOARDING.md",
    "AI-Setup": "docs/guides/AI_SETUP.md",
    "Channel-Creation-Guide": "docs/guides/CHANNEL_CREATION_GUIDE.md",
    "Local-Media": "docs/guides/LOCAL_MEDIA.md",
    "Hardware-Transcoding": "docs/guides/HW_TRANSCODING.md",
    "macOS-App-Guide": "docs/guides/MACOS_APP_GUIDE.md",
    "Navigation-Guide": "docs/guides/NAVIGATION_GUIDE.md",
    "Streaming-Stability": "docs/guides/STREAMING_STABILITY.md",
    "Advanced-Scheduling": "docs/guides/ADVANCED_SCHEDULING.md",
    "API-Reference": "docs/api/README.md",
    "System-Design": "docs/architecture/SYSTEM_DESIGN.md",
    "Tunarr-DizqueTV-Integration": "docs/architecture/TUNARR_DIZQUETV_INTEGRATION.md",
    "Distribution": "docs/development/DISTRIBUTION.md",
    "Build-Progress": "docs/BUILD_PROGRESS.md",
    "Changelog": "CHANGELOG.md",
    "Integration-Plan": "docs/INTEGRATION_PLAN.md",
    "Lessons-Learned": "docs/LESSONS_LEARNED.md",
    "StreamTV-Migration-QuickStart": "docs/StreamTV_Migration_QuickStart.md",
    "StreamTV-Schema-Mapping": "docs/StreamTV_Schema_Mapping.md",
    "Platform-Comparison": "docs/PLATFORM_COMPARISON.txt",
    "MCP-Server": "docs/mcp/README.md",
    "Documentation-Changelog": "docs/CHANGELOG.md",
}

# Reverse: normalize doc path -> Wiki page name (for link rewriting)
_PATH_TO_WIKI_PAGE: dict[str, str] = {}
for _page, _src in WIKI_PAGE_SOURCES.items():
    _path = _src.replace("\\", "/").strip("/")
    for _p in (_path, _path.lower(), _path.replace(".md", "").replace(".txt", "")):
        _PATH_TO_WIKI_PAGE[_p] = _page
    # Links from inside docs/ often omit docs/ prefix
    if _path.startswith("docs/"):
        _rel = _path[5:]  # strip "docs/"
        _PATH_TO_WIKI_PAGE[_rel] = _page
        _PATH_TO_WIKI_PAGE[_rel.replace(".md", "").replace(".txt", "")] = _page

# Common link patterns: ](path) where path is relative to repo or docs/
LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")


def path_to_wiki_page(link_path: str) -> str | None:
    """Convert a doc path in a link to a Wiki page name, or None if no mapping."""
    p = link_path.strip().replace("\\", "/").lstrip("/")
    # Remove anchor
    if "#" in p:
        p, anchor = p.split("#", 1)
        p = p.strip("/")
    else:
        anchor = ""
    if not p:
        return None
    if p in _PATH_TO_WIKI_PAGE:
        page = _PATH_TO_WIKI_PAGE[p]
        return f"{page}#{anchor}" if anchor else page
    # Try without extension
    base = p.replace(".md", "").replace(".txt", "")
    if base in _PATH_TO_WIKI_PAGE:
        page = _PATH_TO_WIKI_PAGE[base]
        return f"{page}#{anchor}" if anchor else page
    # Try key by path suffix
    for src_path, page in _PATH_TO_WIKI_PAGE.items():
        if p.endswith(src_path) or base.endswith(src_path.replace(".md", "").replace(".txt", "")):
            return f"{page}#{anchor}" if anchor else page
    return None


def rewrite_links(content: str, base_dir: Path) -> str:
    """Rewrite ](path) links to Wiki page names where we have a mapping."""
    def repl(match: re.Match) -> str:
        path = match.group(1)
        if path.startswith("http") or path.startswith("mailto:") or path.startswith("#"):
            return match.group(0)
        wiki = path_to_wiki_page(path)
        if wiki:
            return f"]({wiki})"
        return match.group(0)

    return LINK_PATTERN.sub(repl, content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync docs to GitHub Wiki format.")
    parser.add_argument(
        "--wiki-dir",
        type=Path,
        default=PROJECT_ROOT / "wiki_out",
        help="Output directory (wiki repo clone or wiki_out)",
    )
    parser.add_argument(
        "--sidebar",
        action="store_true",
        default=True,
        help="Write _Sidebar.md with links to all pages (default: True)",
    )
    args = parser.parse_args()
    out = args.wiki_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    for page_name, src_rel in WIKI_PAGE_SOURCES.items():
        src = PROJECT_ROOT / src_rel
        if not src.exists():
            print(f"Skip (missing): {src_rel}")
            continue
        raw = src.read_text(encoding="utf-8", errors="replace")
        rewritten = rewrite_links(raw, src.parent)
        out_file = out / f"{page_name}.md"
        out_file.write_text(rewritten, encoding="utf-8")
        print(f"Wrote: {page_name}.md <- {src_rel}")

    if args.sidebar:
        sidebar_lines = ["# Documentation\n", "\n", "[[Home]]\n", "\n"]
        for page_name in WIKI_PAGE_SOURCES:
            if page_name == "Home":
                continue
            sidebar_lines.append(f"[[{page_name}]]\n")
        (out / "_Sidebar.md").write_text("".join(sidebar_lines), encoding="utf-8")
        print("Wrote: _Sidebar.md")

    # Copy screenshots so wiki pages can reference them
    screenshots_src = PROJECT_ROOT / "docs" / "guides" / "screenshots"
    screenshots_dst = out / "screenshots"
    if screenshots_src.is_dir():
        if screenshots_dst.exists():
            shutil.rmtree(screenshots_dst)
        shutil.copytree(screenshots_src, screenshots_dst)
        print("Copied: docs/guides/screenshots -> wiki/screenshots")

    print(f"\nDone. Output in {out}")
    print("To push to GitHub Wiki: clone https://github.com/roto31/EXStreamTV.wiki.git,")
    print("  copy these .md files into it, then git add / commit / push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
