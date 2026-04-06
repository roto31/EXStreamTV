#!/usr/bin/env python3
"""Assemble a single Markdown document mirroring EXStreamTV.wiki + key repo context.

Output: docs/confluence/ESTV-GITHUB-WIKI-MIRROR.generated.md
Image references use basenames only (matches Confluence attachments after upload).

Run from repository root:
    python scripts/build_confluence_mirror_doc.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from wiki_sidebar_order import SIDEBAR_STEMS

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "EXStreamTV.wiki"
SCREENSHOTS = WIKI / "screenshots"
OUT = ROOT / "docs" / "confluence" / "ESTV-GITHUB-WIKI-MIRROR.generated.md"


def _rewrite_wiki_links(text: str) -> str:
    """Turn [[Page]] and [label](Page) into GitHub wiki URLs."""

    base = "https://github.com/roto31/EXStreamTV/wiki"

    def wiki_name_to_url(name: str) -> str:
        return f"{base}/{name.replace(' ', '-')}"

    def repl_double(m: re.Match[str]) -> str:
        inner = m.group(1).split("|")[-1].strip()
        return f"[{inner}]({wiki_name_to_url(inner)})"

    text = re.sub(r"\[\[([^\]]+)\]\]", repl_double, text)
    return text


def _rewrite_screenshot_paths(text: str) -> str:
    """Use attachment-friendly basenames for local/wiki screenshot paths only."""

    def repl(m: re.Match[str]) -> str:
        alt, path = m.group(1), m.group(2).strip()
        if path.startswith("http://") or path.startswith("https://"):
            return m.group(0)
        name = Path(path.split("?", maxsplit=1)[0]).name
        return f"![{alt}]({name})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, text)


def _load_wiki_page(stem: str) -> str | None:
    path = WIKI / f"{stem}.md"
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = _rewrite_screenshot_paths(_rewrite_wiki_links(raw))
    return raw


def main() -> None:
    if not WIKI.is_dir():
        raise SystemExit(f"Wiki directory missing: {WIKI}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
    ver_m = re.search(r'version\s*=\s*"([^"]+)"', pyproject)
    version = ver_m.group(1) if ver_m else "unknown"

    lines: list[str] = [
        "# EXStreamTV — GitHub repository & wiki mirror",
        "",
        "> **Generated for Confluence** (space [ESTV](https://exstreamtv2.atlassian.net/wiki/spaces/ESTV/overview)). "
        "Mermaid diagrams render if your site has a Mermaid macro/app (see "
        "[Confluence Marketplace](https://marketplace.atlassian.com/search?query=mermaid)) or paste blocks into [mermaid.live](https://mermaid.live).",
        "",
        f"- **Version (pyproject):** {version}",
        "- **Repository:** [github.com/roto31/EXStreamTV](https://github.com/roto31/EXStreamTV)",
        "- **Wiki:** [github.com/roto31/EXStreamTV/wiki](https://github.com/roto31/EXStreamTV/wiki)",
        "- **Source folder:** `EXStreamTV.wiki/` in clone",
        "",
        "---",
        "",
        "## README (repository root)",
        "",
        readme,
        "",
        "---",
        "",
    ]

    seen: set[str] = set()
    for stem in SIDEBAR_STEMS:
        body = _load_wiki_page(stem)
        if body is None:
            continue
        seen.add(stem)
        lines.append(f"## Wiki page: {stem.replace('-', ' ')}")
        lines.append("")
        lines.append(f"*Source: [`EXStreamTV.wiki/{stem}.md`](https://github.com/roto31/EXStreamTV/wiki/{stem})*")
        lines.append("")
        lines.append(body)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Any wiki .md not in sidebar
    for path in sorted(WIKI.glob("*.md")):
        stem = path.stem
        if stem.startswith("_") or stem in seen:
            continue
        body = _load_wiki_page(stem)
        if body is None:
            continue
        lines.append(f"## Wiki page: {stem.replace('-', ' ')}")
        lines.append("")
        lines.append(f"*Source: [`EXStreamTV.wiki/{stem}.md`](https://github.com/roto31/EXStreamTV/wiki/{stem})*")
        lines.append("")
        lines.append(body)
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Screenshot gallery (wiki `screenshots/`)")
    lines.append("")
    lines.append("Attachments use the same filenames as in `EXStreamTV.wiki/screenshots/`.")
    lines.append("")
    for img in sorted(SCREENSHOTS.iterdir()):
        if img.suffix.lower() not in {".png", ".gif", ".jpg", ".jpeg", ".webp"}:
            continue
        lines.append(f"### {img.name}")
        lines.append("")
        lines.append(f"![{img.stem}]({img.name})")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
