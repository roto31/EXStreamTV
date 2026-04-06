#!/usr/bin/env python3
"""Build JSONL manifest of ADF bodies for Atlassian MCP Confluence (optional / legacy path).

Output: docs/confluence/atlassian-mcp-mirror.manifest.jsonl
Each line: {"key": str, "title": str, "body": str}  # body is JSON string for createConfluencePage (ADF)

Note: Atlassian MCP uses ADF; wiki bodies are embedded as a single Markdown code block, so Mermaid
does **not** render. For GitHub-like rendering and Mermaid in Confluence storage format, run:

  uv run scripts/publish_confluence_wiki_tree.py

Run from repo root:
  uv run python scripts/build_atlassian_adf_manifest.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from wiki_sidebar_order import SIDEBAR_STEMS, confluence_wiki_child_title, display_title

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "confluence" / "atlassian-mcp-mirror.manifest.jsonl"
WIKI = ROOT / "EXStreamTV.wiki"
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"
GITHUB_WIKI = "https://github.com/roto31/EXStreamTV/wiki"


def _rewrite_wiki_links(text: str) -> str:
    def wiki_name_to_url(name: str) -> str:
        return f"{GITHUB_WIKI}/{name.replace(' ', '-')}"

    def repl_double(m: re.Match[str]) -> str:
        inner = m.group(1).split("|")[-1].strip()
        return f"[{inner}]({wiki_name_to_url(inner)})"

    return re.sub(r"\[\[([^\]]+)\]\]", repl_double, text)


def _rewrite_screenshot_paths(text: str) -> str:
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
    return _rewrite_screenshot_paths(_rewrite_wiki_links(raw))


def _adf_doc_with_markdown_code_block(title: str, preamble: str, md: str) -> str:
    adf: dict = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 1},
                "content": [{"type": "text", "text": title}],
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": preamble}],
            },
            {"type": "codeBlock", "attrs": {"language": "markdown"}, "content": [{"type": "text", "text": md}]},
        ],
    }
    return json.dumps(adf, ensure_ascii=False)


def main() -> None:
    if not WIKI.is_dir():
        raise SystemExit(f"Missing wiki: {WIKI}")

    ver_m = re.search(r'version\s*=\s*"([^"]+)"', PYPROJECT.read_text(encoding="utf-8"))
    version = ver_m.group(1) if ver_m else "unknown"
    readme = README.read_text(encoding="utf-8", errors="replace")

    OUT.parent.mkdir(parents=True, exist_ok=True)

    toc_lines = []
    for stem in SIDEBAR_STEMS:
        if (WIKI / f"{stem}.md").is_file():
            toc_lines.append(
                f"- [{display_title(stem)}]({GITHUB_WIKI}/{stem}) — Confluence child: **{confluence_wiki_child_title(stem)}**"
            )

    index_md = (
        f"# EXStreamTV\n\n"
        f"**Version:** `{version}`\n\n"
        f"- [GitHub repository](https://github.com/roto31/EXStreamTV)\n"
        f"- [GitHub Wiki]({GITHUB_WIKI})\n"
        f"- [Confluence ESTV](https://exstreamtv2.atlassian.net/wiki/spaces/ESTV/overview)\n\n"
        f"For rendered Markdown and Mermaid on Confluence, use "
        f"`uv run scripts/publish_confluence_wiki_tree.py` (storage format). "
        f"This MCP manifest keeps wiki text in a Markdown code block per page.\n\n"
        f"## Wiki pages (sidebar order)\n\n"
        + "\n".join(toc_lines)
    )
    index_body = _adf_doc_with_markdown_code_block(
        "EXStreamTV",
        "Documentation index. Open a child page for wiki source (Markdown in a code block).",
        index_md,
    )

    records: list[dict[str, str]] = [
        {"key": "INDEX", "title": "EXStreamTV", "body": index_body},
        {
            "key": "README",
            "title": "README",
            "body": _adf_doc_with_markdown_code_block(
                "README",
                "Repository README. Source: https://github.com/roto31/EXStreamTV/blob/main/README.md",
                readme,
            ),
        },
    ]

    for stem in SIDEBAR_STEMS:
        raw = _load_wiki_page(stem)
        if raw is None:
            continue
        title = confluence_wiki_child_title(stem)
        preamble = (
            f"Wiki `{stem}.md`. Source: {GITHUB_WIKI}/{stem.replace(' ', '-')}"
        )
        records.append(
            {
                "key": stem,
                "title": title,
                "body": _adf_doc_with_markdown_code_block(display_title(stem), preamble, raw),
            }
        )

    with OUT.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} records to {OUT}")


if __name__ == "__main__":
    main()
