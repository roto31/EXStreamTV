# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx"]
# ///
"""
Verify EXStreamTV.wiki content and (optionally) Kroki Mermaid renders before/after Confluence publish.

  uv run scripts/verify_wiki_confluence_docs.py
  uv run scripts/verify_wiki_confluence_docs.py --kroki

Exit code 1 if: a ``SIDEBAR_STEMS`` page is missing; or ``--kroki`` is set and any
Mermaid block fails to render.

Optional ``--warn-thin N`` warns (stderr, still exit 0) on pages shorter than *N*
chars (except allowlisted stub stems).

Ref: docs/LESSONS_LEARNED.md LL-036, RULE DOC-07 / DOC-08.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import httpx

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from wiki_sidebar_order import SIDEBAR_STEMS

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "EXStreamTV.wiki"

_MERMAID_FENCE = re.compile(r"^```mermaid\s*\n(.*?)```", re.DOTALL | re.MULTILINE)

# Stems allowed to stay short (wiki landing stub; Confluence child "EXStreamTV Wiki").
_THIN_OK_STEMS = frozenset({"EXStreamTV"})
def _mermaid_blocks(text: str) -> list[str]:
    return [m.strip() for m in _MERMAID_FENCE.findall(text) if m.strip()]


def _kroki_svg(client: httpx.Client, source: str, url: str) -> bool:
    try:
        r = client.post(
            url,
            content=source.strip().encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
            timeout=120.0,
        )
    except OSError:
        return False
    return r.status_code == 200 and b"<svg" in r.content[:4000]


def main() -> None:
    p = argparse.ArgumentParser(description="Verify wiki files and optional Kroki Mermaid.")
    p.add_argument(
        "--kroki",
        action="store_true",
        help="POST each Mermaid block to Kroki (slower; catches unsupported syntax).",
    )
    p.add_argument(
        "--kroki-url",
        default="https://kroki.io/mermaid/svg",
        help="Kroki Mermaid endpoint (default: https://kroki.io/mermaid/svg).",
    )
    p.add_argument(
        "--warn-thin",
        type=int,
        metavar="N",
        default=0,
        help="If > 0, warn when a page body is shorter than N chars (except stub stems).",
    )
    args = p.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    mermaid_total = 0
    kroki_ok = 0
    kroki_fail: list[tuple[str, int, str]] = []

    if not WIKI.is_dir():
        raise SystemExit(f"Missing wiki directory: {WIKI}")

    for stem in SIDEBAR_STEMS:
        path = WIKI / f"{stem}.md"
        if not path.is_file():
            errors.append(f"MISSING {stem}.md (in SIDEBAR_STEMS but no file)")
            continue

        raw = path.read_text(encoding="utf-8", errors="replace")
        stripped = raw.strip()
        n = len(stripped)
        if (
            args.warn_thin > 0
            and stem not in _THIN_OK_STEMS
            and n < args.warn_thin
        ):
            warnings.append(
                f"THIN {stem}.md — {n} chars (threshold {args.warn_thin}); expand if page should not look empty on Confluence"
            )

        blocks = _mermaid_blocks(raw)
        mermaid_total += len(blocks)
        if blocks:
            print(f"{stem}.md: {len(blocks)} Mermaid block(s)")

        if args.kroki and blocks:
            with httpx.Client(timeout=180.0, follow_redirects=True) as client:
                for i, body in enumerate(blocks, start=1):
                    if _kroki_svg(client, body, args.kroki_url):
                        kroki_ok += 1
                    else:
                        head = body.split("\n", 1)[0][:100]
                        kroki_fail.append((stem, i, head))
                        errors.append(f"KROKI_FAIL {stem}.md block {i}: {head!r}")

    print()
    print(f"Summary: {len(SIDEBAR_STEMS)} sidebar pages checked, {mermaid_total} Mermaid block(s) total.")
    if args.kroki:
        print(f"Kroki: {kroki_ok} ok, {len(kroki_fail)} failed")

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)

    if errors:
        raise SystemExit(1)
    if warnings:
        print("(Warnings only — exit 0)", file=sys.stderr)


if __name__ == "__main__":
    main()
