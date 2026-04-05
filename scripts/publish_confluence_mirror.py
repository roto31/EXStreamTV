# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx", "markdown"]
# ///
"""
Publish docs/confluence/ESTV-GITHUB-WIKI-MIRROR.generated.md to Confluence Cloud.

Prerequisites:
  1. Run: python scripts/build_confluence_mirror_doc.py
  2. Atlassian API token with Confluence write access
  3. Space key ESTV (or override)

Usage:
  uv run scripts/publish_confluence_mirror.py --dry-run
  CONFLUENCE_BASE_URL=https://exstreamtv2.atlassian.net \\
  CONFLUENCE_USER=you@example.com \\
  CONFLUENCE_API_TOKEN=xxxxx \\
  uv run scripts/publish_confluence_mirror.py

Optional:
  CONFLUENCE_SPACE_KEY=ESTV
  CONFLUENCE_PARENT_PAGE_ID=123456   # child of Overview / home
  CONFLUENCE_PLAIN_MARKDOWN=1        # legacy nl2br / plain code (see wiki tree publisher)

Ref: https://developer.atlassian.com/cloud/confluence/rest/v1/intro/
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import httpx

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from confluence_markdown_storage import (
    Presentation,
    fix_markdown_images_for_attachments,
    markdown_to_storage,
)

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "docs" / "confluence" / "ESTV-GITHUB-WIKI-MIRROR.generated.md"
SCREENSHOTS = ROOT / "EXStreamTV.wiki" / "screenshots"


def _load_repo_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


def publish(
    *,
    base_url: str,
    user: str,
    token: str,
    space_key: str,
    title: str,
    parent_id: str | None,
    dry_run: bool,
    presentation: Presentation,
) -> None:
    if not MD_PATH.is_file():
        raise SystemExit(f"Missing {MD_PATH}; run scripts/build_confluence_mirror_doc.py first")

    raw_md = MD_PATH.read_text(encoding="utf-8")
    raw_md = fix_markdown_images_for_attachments(raw_md)
    storage = markdown_to_storage(raw_md, presentation=presentation)

    if dry_run:
        out = ROOT / "docs" / "confluence" / "_dry_run_storage_snippet.xml"
        out.write_text(storage[:8000] + "\n<!-- truncated -->\n", encoding="utf-8")
        print(f"Dry run: wrote first ~8k of storage XML to {out}")
        return

    auth = (user, token)
    # Omit default Content-Type so screenshot uploads use multipart (not application/json → 415).
    headers = {"Accept": "application/json"}
    api = f"{base_url.rstrip('/')}/wiki/rest/api"

    body: dict = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {"storage": {"value": storage, "representation": "storage"}},
    }
    if parent_id:
        body["ancestors"] = [{"id": parent_id}]

    with httpx.Client(timeout=120.0) as client:
        r = client.post(f"{api}/content", auth=auth, headers=headers, json=body)
        if r.status_code not in (200, 201):
            print(r.text[:2000], file=sys.stderr)
            r.raise_for_status()
        page = r.json()
        page_id = page["id"]
        print(f"Created page id={page_id} {base_url}/wiki/spaces/{space_key}/pages/{page_id}")

        for img in sorted(SCREENSHOTS.iterdir()):
            if img.suffix.lower() not in {".png", ".gif", ".jpg", ".jpeg", ".webp"}:
                continue
            with img.open("rb") as f:
                up = client.post(
                    f"{api}/content/{page_id}/child/attachment",
                    auth=auth,
                    headers={"X-Atlassian-Token": "no-check", "Accept": "application/json"},
                    files={"file": (img.name, f, "application/octet-stream")},
                )
            if up.status_code not in (200, 201):
                print(f"Attachment failed {img.name}: {up.status_code} {up.text[:500]}", file=sys.stderr)
            else:
                print(f"Attached {img.name}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--title",
        default="EXStreamTV — GitHub repository & wiki mirror",
        help="Confluence page title",
    )
    args = p.parse_args()

    _load_repo_dotenv()
    base = os.environ.get("CONFLUENCE_BASE_URL", "https://exstreamtv2.atlassian.net")
    user = os.environ.get("CONFLUENCE_USER") or os.environ.get("CONFLUENCE_USERNAME", "")
    token = os.environ.get("CONFLUENCE_API_TOKEN", "")
    space = os.environ.get("CONFLUENCE_SPACE_KEY", "ESTV")
    parent = os.environ.get("CONFLUENCE_PARENT_PAGE_ID") or None

    if not args.dry_run and (not user or not token):
        raise SystemExit("Set CONFLUENCE_USER and CONFLUENCE_API_TOKEN (or use --dry-run)")

    presentation: Presentation = (
        "standard"
        if os.environ.get("CONFLUENCE_PLAIN_MARKDOWN", "").strip().lower() in ("1", "true", "yes")
        else "stakeholder"
    )

    publish(
        base_url=base,
        user=user,
        token=token,
        space_key=space,
        title=args.title,
        parent_id=parent,
        dry_run=args.dry_run,
        presentation=presentation,
    )


if __name__ == "__main__":
    main()
