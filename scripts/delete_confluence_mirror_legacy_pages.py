# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx"]
# ///
"""
Delete legacy Confluence pages whose titles used the old ``Mirror …`` naming.

Examples removed: ``Mirror Quick Start``, ``Mirror — Platform Guide``.

Canonical wiki-backed pages use titles from ``wiki_sidebar_order.confluence_wiki_child_title``
(no ``Mirror`` prefix). Orphan ``Mirror*`` pages are left over when both old and new titles
existed as siblings.

  uv run scripts/delete_confluence_mirror_legacy_pages.py --dry-run
  uv run scripts/delete_confluence_mirror_legacy_pages.py

Env: same as ``publish_confluence_wiki_tree.py`` (``CONFLUENCE_BASE_URL``, ``CONFLUENCE_USER``,
``CONFLUENCE_API_TOKEN``, ``CONFLUENCE_SPACE_KEY``).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]


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


def _api_base(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/wiki/rest/api"


_LEGACY_MIRROR = re.compile(
    r"(?is)^mirror(\s+[—–-]\s+\S|\s+\S)",
)


def is_legacy_mirror_page_title(title: str) -> bool:
    """True for old mirror-style titles; false for unrelated pages (e.g. ``Mirroring …``)."""
    t = title.strip()
    if not t:
        return False
    return bool(_LEGACY_MIRROR.match(t))


def _search_mirror_pages(
    client: httpx.Client,
    api: str,
    *,
    space_key: str,
) -> list[dict]:
    """Return current pages in the space whose CQL title search matches ``Mirror``."""
    cql = f'space = "{space_key}" AND type = page AND title ~ "Mirror"'
    out: list[dict] = []
    start = 0
    limit = 50
    while True:
        r = client.get(
            f"{api}/content/search",
            params={
                "cql": cql,
                "limit": limit,
                "start": start,
                "expand": "ancestors",
            },
        )
        if r.status_code != 200:
            print(r.text[:2000], file=sys.stderr)
            r.raise_for_status()
        data = r.json()
        batch = list(data.get("results") or [])
        out.extend(batch)
        if len(batch) < limit:
            break
        start += limit
    return out


def _delete_page(client: httpx.Client, api: str, page_id: str) -> None:
    r = client.delete(f"{api}/content/{page_id}", params={"status": "current"})
    if r.status_code not in (200, 204):
        print(r.text[:2000], file=sys.stderr)
        r.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trash legacy Confluence pages titled Mirror … in a space.",
    )
    parser.add_argument("--dry-run", action="store_true", help="List targets only; no DELETE.")
    args = parser.parse_args()

    _load_repo_dotenv()
    base_url = os.environ.get("CONFLUENCE_BASE_URL", "https://exstreamtv2.atlassian.net")
    user = os.environ.get("CONFLUENCE_USER") or os.environ.get("CONFLUENCE_USERNAME", "")
    token = os.environ.get("CONFLUENCE_API_TOKEN", "")
    space_key = os.environ.get("CONFLUENCE_SPACE_KEY", "ESTV")

    if not args.dry_run and (not user or not token):
        raise SystemExit("Set CONFLUENCE_USER and CONFLUENCE_API_TOKEN (or use --dry-run)")

    api = _api_base(base_url)
    headers = {"Accept": "application/json"}
    auth = (user, token)

    with httpx.Client(timeout=120.0, auth=auth, headers=headers) as client:
        raw = _search_mirror_pages(client, api, space_key=space_key)
        candidates = [p for p in raw if is_legacy_mirror_page_title(str(p.get("title") or ""))]

        def depth(p: dict) -> int:
            return len(p.get("ancestors") or [])

        candidates.sort(key=depth, reverse=True)

        if not candidates:
            print(f"No legacy Mirror-titled pages in space {space_key!r}.")
            return

        print(f"Found {len(candidates)} legacy Mirror page(s) in {space_key!r}:")
        for p in candidates:
            pid = str(p.get("id") or "")
            title = str(p.get("title") or "")
            print(f"  id={pid} title={title!r}")

        if args.dry_run:
            print("Dry run — no DELETE performed.")
            return

        for p in candidates:
            pid = str(p["id"])
            title = str(p.get("title") or "")
            _delete_page(client, api, pid)
            print(f"Trashed: {title!r} ({pid})")

    print("Done.")


if __name__ == "__main__":
    main()
