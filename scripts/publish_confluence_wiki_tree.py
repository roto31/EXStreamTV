# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx", "markdown"]
# ///
"""
Publish EXStreamTV GitHub README + EXStreamTV.wiki as a Confluence page tree.

- Storage format: rendered Markdown, tables, fenced code, and Mermaid diagrams as **SVG
  attachments** (via Kroki POST) plus ``ri:attachment`` — works without a Mermaid
  marketplace app. If Kroki is unreachable, falls back per-diagram to the ``code`` macro
  with ``language=mermaid``.
- Landing page: repository README plus wiki index table and top-level folder list.
- Wiki child titles match the wiki (no ``Mirror —`` prefix).

  uv run scripts/publish_confluence_wiki_tree.py

Env:
  CONFLUENCE_SKIP_KROKI=1   — skip Kroki; Mermaid only as code macros
  CONFLUENCE_KROKI_URL      — default https://kroki.io/mermaid/svg
  CONFLUENCE_PLAIN_MARKDOWN=1 — legacy Markdown rendering (nl2br, no panels/expand/table classes)
  CONFLUENCE_ROOT_PAGE_ID   — optional; if unset, an existing root title match in the space is reused

Ref: https://developer.atlassian.com/cloud/confluence/rest/v1/intro/
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import time
from pathlib import Path

import httpx

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from confluence_markdown_storage import (
    Presentation,
    fix_markdown_images_for_attachments,
    markdown_to_storage,
    markdown_to_storage_with_mermaid_svgs,
)
from wiki_sidebar_order import SIDEBAR_STEMS, confluence_wiki_child_title, display_title

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "EXStreamTV.wiki"


def _load_repo_dotenv() -> None:
    """Populate os.environ from repo-root ``.env`` if present (does not override existing vars)."""
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
SCREENSHOTS = WIKI / "screenshots"
README_PATH = ROOT / "README.md"
PYPROJECT_PATH = ROOT / "pyproject.toml"
GITHUB_WIKI = "https://github.com/roto31/EXStreamTV/wiki"
GITHUB_REPO = "https://github.com/roto31/EXStreamTV"

_SKIP_DIRS = frozenset({
    ".git",
    ".cursor",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
})

_FOLDER_BLURB: dict[str, str] = {
    "exstreamtv": "Python backend — API, streaming, scheduling, FFmpeg, AI agent",
    "EXStreamTVApp": "macOS menu bar application (Swift)",
    "containers": "Docker and container deployment",
    "docs": "Repository documentation (Markdown)",
    "tests": "pytest suite",
    "scripts": "Automation, migration, and publishing tools",
    "EXStreamTV.wiki": "GitHub Wiki source (mirrored into Confluence child pages)",
}


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


def _image_basenames(md: str) -> set[str]:
    out: set[str] = set()

    def repl(m: re.Match[str]) -> str:
        path = m.group(2).strip()
        if path.startswith("http://") or path.startswith("https://"):
            return m.group(0)
        out.add(Path(path.split("?", maxsplit=1)[0]).name)
        return m.group(0)

    re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, md)
    return out


def _rewrite_github_wiki_urls(md: str, stem_to_page_url: dict[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        stem_key = m.group(1)
        if stem_key in stem_to_page_url:
            return stem_to_page_url[stem_key]
        return m.group(0)

    return re.sub(
        r"https://github\.com/roto31/EXStreamTV/wiki/([A-Za-z0-9-]+)",
        repl,
        md,
    )


def _list_repo_folders_md() -> str:
    rows = ["| Folder | Notes |", "| --- | --- |"]
    for p in sorted(ROOT.iterdir()):
        if not p.is_dir():
            continue
        name = p.name
        if name.startswith(".") or name in _SKIP_DIRS:
            continue
        blurb = _FOLDER_BLURB.get(name, "")
        rows.append(f"| `{name}/` | {blurb} |")
    return "\n".join(rows)


def _wiki_index_table_md(stem_to_url: dict[str, str]) -> str:
    lines = [
        "| Wiki page | GitHub Wiki | This space |",
        "| --- | --- | --- |",
    ]
    for stem in SIDEBAR_STEMS:
        if stem not in stem_to_url:
            continue
        label = confluence_wiki_child_title(stem)
        gh = f"{GITHUB_WIKI}/{stem}"
        cu = stem_to_url[stem]
        lines.append(f"| **{label}** | [{display_title(stem)}]({gh}) | [{label}]({cu}) |")
    return "\n".join(lines)


def _strip_repo_title_line(readme_text: str) -> str:
    lines = readme_text.splitlines()
    if lines and lines[0].strip() == "# EXStreamTV":
        i = 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        return "\n".join(lines[i:])
    return readme_text


def _landing_executive_prefix_storage(*, version: str) -> str:
    """Stakeholder-facing HTML (Confluence storage): overview + investment highlights."""
    gu = html.escape(GITHUB_REPO, quote=True)
    vv = html.escape(version, quote=True)
    return (
        '<ac:structured-macro ac:name="panel" ac:schema-version="1">'
        '<ac:parameter ac:name="panelColor">blue</ac:parameter>'
        '<ac:parameter ac:name="borderStyle">solid</ac:parameter>'
        '<ac:parameter ac:name="title">Platform overview</ac:parameter>'
        "<ac:rich-text-body>"
        "<p><strong>EXStreamTV</strong> turns online and library media into custom live TV channels. "
        "Plex DVR discovers it as an <strong>HDHomeRun</strong> tuner so viewers get a familiar "
        "lineup and tuning experience.</p>"
        f'<p><a href="{gu}">GitHub repository</a> · release <strong>{vv}</strong></p>'
        "</ac:rich-text-body>"
        "</ac:structured-macro>"
        '<p><br /></p>'
        '<ac:structured-macro ac:name="panel" ac:schema-version="1">'
        '<ac:parameter ac:name="panelColor">green</ac:parameter>'
        '<ac:parameter ac:name="borderStyle">solid</ac:parameter>'
        '<ac:parameter ac:name="title">Why this matters</ac:parameter>'
        "<ac:rich-text-body><ul>"
        "<li>Mainstream DVR path: HDHomeRun / Plex integration, not a niche IPTV-only stack.</li>"
        "<li>Production streaming: FFmpeg pipeline, hardware transcoding, throttling, and safety rails.</li>"
        "<li>Reach: YouTube &amp; Archive.org streams plus Plex, Jellyfin, Emby, and local folders.</li>"
        "<li>Product surface: FastAPI core and a native macOS menu bar app.</li>"
        "</ul></ac:rich-text-body>"
        "</ac:structured-macro>"
        "<hr />"
        "<p><br /></p>"
    )


def _build_landing_markdown(*, readme_text: str, stem_to_url: dict[str, str], version: str) -> str:
    body = _strip_repo_title_line(readme_text).lstrip()
    return (
        f"{body.rstrip()}\n\n---\n\n"
        "## Wiki documentation\n\n"
        "Mermaid diagrams from the wiki are published as **SVG images** (rendered via "
        "[Kroki](https://kroki.io)) so they display without a separate Confluence Mermaid app. "
        "If Kroki is unavailable during publish, a diagram may appear only as a Mermaid **code** block.\n\n"
        f"{_wiki_index_table_md(stem_to_url)}\n\n"
        "---\n\n"
        "## Top-level repository folders\n\n"
        f"{_list_repo_folders_md()}\n\n"
        "---\n\n"
        f"_Source: [{GITHUB_REPO}]({GITHUB_REPO}) · package version **{version}**._\n"
    )


def _api_base(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/wiki/rest/api"


def _find_page_id_by_title_in_space(
    client: httpx.Client,
    api: str,
    *,
    space_key: str,
    title: str,
    parent_id: str | None,
) -> str | None:
    """Return id of a current page with exact ``title`` in ``space_key``, if unique enough to reuse.

    If ``parent_id`` is set, prefer a page whose deepest ancestor matches ``parent_id`` (root under that parent).
    """
    r = client.get(
        f"{api}/content",
        params={
            "spaceKey": space_key,
            "title": title,
            "type": "page",
            "status": "current",
            "limit": 25,
            "expand": "ancestors",
        },
    )
    if r.status_code != 200:
        return None
    results: list[dict] = list(r.json().get("results") or [])
    if not results:
        return None

    def deepest_ancestor_id(page: dict) -> str | None:
        anc = page.get("ancestors") or []
        if not anc:
            return None
        return str(anc[-1].get("id") or "")

    if parent_id:
        for p in results:
            if deepest_ancestor_id(p) == str(parent_id):
                return str(p["id"])
        if len(results) == 1:
            return str(results[0]["id"])
        return None

    return str(results[0]["id"])


def _get_page(client: httpx.Client, api: str, page_id: str) -> dict:
    r = client.get(
        f"{api}/content/{page_id}",
        params={"expand": "body.storage,version,space"},
    )
    if r.status_code != 200:
        print(r.text[:2000], file=sys.stderr)
        r.raise_for_status()
    return r.json()


def _list_child_pages(client: httpx.Client, api: str, parent_id: str) -> list[dict]:
    r = client.get(
        f"{api}/content/{parent_id}/child/page",
        params={"limit": 250},
    )
    if r.status_code != 200:
        print(r.text[:2000], file=sys.stderr)
        r.raise_for_status()
    return list(r.json().get("results") or [])


def _find_child_id(children: list[dict], title: str) -> str | None:
    for p in children:
        if p.get("title") == title:
            return str(p["id"])
    return None


def _find_wiki_child_id(children: list[dict], stem: str) -> str | None:
    for title in (confluence_wiki_child_title(stem), f"Mirror — {display_title(stem)}"):
        pid = _find_child_id(children, title)
        if pid:
            return pid
    return None


def _create_page(
    client: httpx.Client,
    api: str,
    *,
    space_key: str,
    title: str,
    storage_html: str,
    parent_id: str | None,
) -> str:
    body: dict = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {"storage": {"value": storage_html, "representation": "storage"}},
    }
    if parent_id:
        body["ancestors"] = [{"id": parent_id}]
    r = client.post(f"{api}/content", json=body)
    if r.status_code not in (200, 201):
        print(r.text[:2000], file=sys.stderr)
        r.raise_for_status()
    return str(r.json()["id"])


def _update_page(
    client: httpx.Client,
    api: str,
    page_id: str,
    *,
    title: str,
    storage_html: str,
) -> None:
    for attempt in range(2):
        cur = _get_page(client, api, page_id)
        ver = int(cur["version"]["number"])
        sk = cur["space"]["key"]
        payload = {
            "id": page_id,
            "type": "page",
            "title": title,
            "space": {"key": sk},
            "body": {"storage": {"value": storage_html, "representation": "storage"}},
            "version": {"number": ver + 1, "message": "publish_confluence_wiki_tree"},
        }
        r = client.put(f"{api}/content/{page_id}", json=payload)
        if r.status_code == 200:
            return
        if r.status_code == 409 and attempt == 0:
            time.sleep(0.5)
            continue
        print(r.text[:2000], file=sys.stderr)
        r.raise_for_status()


def _existing_attachment_titles(client: httpx.Client, api: str, page_id: str) -> set[str]:
    r = client.get(f"{api}/content/{page_id}/child/attachment", params={"limit": 250})
    if r.status_code != 200:
        return set()
    return {str(a.get("title") or "") for a in (r.json().get("results") or [])}


def _upload_attachment_bytes(
    client: httpx.Client,
    api: str,
    page_id: str,
    filename: str,
    data: bytes,
    mime: str,
) -> bool:
    have = _existing_attachment_titles(client, api, page_id)
    if filename in have:
        return True
    files = {"file": (filename, data, mime)}
    r = client.post(
        f"{api}/content/{page_id}/child/attachment",
        headers={"X-Atlassian-Token": "no-check", "Accept": "application/json"},
        files=files,
    )
    if r.status_code not in (200, 201):
        print(f"Attachment failed {filename}: {r.status_code} {r.text[:500]}", file=sys.stderr)
        return False
    print(f"Attached {filename} → page {page_id}")
    return True


def _ensure_screenshot_attachments(
    client: httpx.Client,
    api: str,
    page_id: str,
    basenames: set[str],
) -> None:
    have = _existing_attachment_titles(client, api, page_id)
    for name in sorted(basenames):
        if name in have:
            continue
        path = SCREENSHOTS / name
        if not path.is_file():
            continue
        with path.open("rb") as f:
            data = f.read()
        _upload_attachment_bytes(
            client, api, page_id, name, data, "application/octet-stream",
        )


def _md_to_storage(
    md: str,
    kroki_client: httpx.Client,
    *,
    use_kroki: bool,
    kroki_url: str,
    presentation: Presentation,
) -> tuple[str, list[tuple[str, bytes]]]:
    if use_kroki:
        return markdown_to_storage_with_mermaid_svgs(
            md, kroki_client, kroki_url=kroki_url, presentation=presentation
        )
    return markdown_to_storage(md, presentation=presentation), []


def _publish_page_body(
    client: httpx.Client,
    api: str,
    page_id: str,
    *,
    title: str,
    md: str,
    kroki_client: httpx.Client,
    use_kroki: bool,
    kroki_url: str,
    presentation: Presentation,
    prepend_storage: str = "",
) -> None:
    storage, mermaid_svgs = _md_to_storage(
        md, kroki_client, use_kroki=use_kroki, kroki_url=kroki_url, presentation=presentation
    )
    if prepend_storage:
        storage = prepend_storage + storage
    failed_mermaid: list[str] = []
    for fname, blob in mermaid_svgs:
        time.sleep(0.05)
        if not _upload_attachment_bytes(client, api, page_id, fname, blob, "image/svg+xml"):
            failed_mermaid.append(fname)
    if failed_mermaid:
        raise RuntimeError(
            "Mermaid SVG attachment upload failed (page body not updated). "
            f"Files: {failed_mermaid}. Fix uploads (see LL-034 / multipart headers) then re-run."
        )
    imgs = _image_basenames(md)
    if imgs:
        _ensure_screenshot_attachments(client, api, page_id, imgs)
    _update_page(client, api, page_id, title=title, storage_html=storage)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish README + wiki tree to Confluence.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan only; no API writes.")
    args = parser.parse_args()

    if not WIKI.is_dir():
        raise SystemExit(f"Missing wiki directory: {WIKI}")
    if not README_PATH.is_file():
        raise SystemExit(f"Missing {README_PATH}")

    _load_repo_dotenv()
    base_url = os.environ.get("CONFLUENCE_BASE_URL", "https://exstreamtv2.atlassian.net")
    user = os.environ.get("CONFLUENCE_USER") or os.environ.get("CONFLUENCE_USERNAME", "")
    token = os.environ.get("CONFLUENCE_API_TOKEN", "")
    space_key = os.environ.get("CONFLUENCE_SPACE_KEY", "ESTV")
    parent_page_id = os.environ.get("CONFLUENCE_PARENT_PAGE_ID") or None
    root_page_id_env = os.environ.get("CONFLUENCE_ROOT_PAGE_ID") or None
    use_kroki = os.environ.get("CONFLUENCE_SKIP_KROKI", "").strip().lower() not in ("1", "true", "yes")
    kroki_url = os.environ.get("CONFLUENCE_KROKI_URL", "https://kroki.io/mermaid/svg").strip()
    presentation: Presentation = (
        "standard"
        if os.environ.get("CONFLUENCE_PLAIN_MARKDOWN", "").strip().lower() in ("1", "true", "yes")
        else "stakeholder"
    )

    if not args.dry_run and (not user or not token):
        raise SystemExit("Set CONFLUENCE_USER and CONFLUENCE_API_TOKEN (or use --dry-run)")

    ver_m = re.search(r'version\s*=\s*"([^"]+)"', PYPROJECT_PATH.read_text(encoding="utf-8"))
    version = ver_m.group(1) if ver_m else "unknown"

    stems_present: list[str] = []
    for stem in SIDEBAR_STEMS:
        if (WIKI / f"{stem}.md").is_file():
            stems_present.append(stem)

    root_title = "EXStreamTV"
    root_bootstrap_storage = "<p>EXStreamTV</p>"

    if args.dry_run:
        print("Dry run — planned pages:")
        print(f"  Kroki Mermaid SVG: {use_kroki} ({kroki_url})")
        print(f"  Presentation: {presentation}")
        print(f"  root: {root_title!r} under parent={parent_page_id!r}")
        for stem in stems_present:
            print(f"  child: {confluence_wiki_child_title(stem)!r} ← EXStreamTV.wiki/{stem}.md")
        sample = ""
        if stems_present:
            for st in stems_present:
                raw = _load_wiki_page(st) or ""
                if "```mermaid" in raw:
                    sample = raw
                    break
            if not sample:
                sample = _load_wiki_page(stems_present[0]) or ""
        if sample:
            snippet = fix_markdown_images_for_attachments(sample)[:12000]
            with httpx.Client(timeout=120.0) as kc:
                if use_kroki:
                    out, _atts = markdown_to_storage_with_mermaid_svgs(
                        snippet, kc, kroki_url=kroki_url, presentation=presentation
                    )
                else:
                    out = markdown_to_storage(snippet, presentation=presentation)
            p = ROOT / "docs" / "confluence" / "_dry_run_wiki_tree_storage_snippet.xml"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(out[:12000] + "\n<!-- truncated -->\n", encoding="utf-8")
            print(f"Wrote storage sample to {p}")
        return

    api = _api_base(base_url)
    auth = (user, token)
    # Do not set Content-Type on the client: multipart attachment uploads need
    # multipart/form-data; a default application/json causes Confluence 415.
    headers = {"Accept": "application/json"}

    failures: list[str] = []
    with httpx.Client(timeout=180.0, auth=auth, headers=headers) as client, httpx.Client(
        timeout=180.0,
        follow_redirects=True,
    ) as kroki_client:
        if root_page_id_env:
            root_id = root_page_id_env
            print(f"Using CONFLUENCE_ROOT_PAGE_ID={root_id}")
        else:
            existing_root = _find_page_id_by_title_in_space(
                client,
                api,
                space_key=space_key,
                title=root_title,
                parent_id=parent_page_id,
            )
            if existing_root:
                root_id = existing_root
                print(
                    f"Reuse root page id={root_id} title={root_title!r} "
                    f"(set CONFLUENCE_ROOT_PAGE_ID={root_id} to skip lookup)"
                )
            else:
                root_id = _create_page(
                    client,
                    api,
                    space_key=space_key,
                    title=root_title,
                    storage_html=root_bootstrap_storage,
                    parent_id=parent_page_id,
                )
                print(
                    f"Created root page id={root_id} ({base_url}/wiki/spaces/{space_key}/pages/{root_id})"
                )

        children = _list_child_pages(client, api, root_id)
        stem_to_id: dict[str, str] = {}

        for stem in stems_present:
            title = confluence_wiki_child_title(stem)
            existing = _find_wiki_child_id(children, stem)
            if existing:
                pid = existing
                print(f"Reuse child id={pid} title={title!r}")
            else:
                pid = _create_page(
                    client,
                    api,
                    space_key=space_key,
                    title=title,
                    storage_html="<p />",
                    parent_id=root_id,
                )
                print(f"Created child id={pid} title={title!r}")
            stem_to_id[stem] = pid

        stem_to_url = {
            s: f"{base_url.rstrip('/')}/wiki/spaces/{space_key}/pages/{pid}"
            for s, pid in stem_to_id.items()
        }

        for stem in stems_present:
            pid = stem_to_id[stem]
            raw = _load_wiki_page(stem)
            assert raw is not None
            md = _rewrite_github_wiki_urls(raw, stem_to_url)
            md = fix_markdown_images_for_attachments(md)
            t = confluence_wiki_child_title(stem)
            try:
                _publish_page_body(
                    client,
                    api,
                    pid,
                    title=t,
                    md=md,
                    kroki_client=kroki_client,
                    use_kroki=use_kroki,
                    kroki_url=kroki_url,
                    presentation=presentation,
                )
                print(f"Published: {t} ({pid})")
            except Exception as exc:
                print(f"FAILED {t} ({pid}): {exc}", file=sys.stderr)
                failures.append(stem)

        readme_raw = README_PATH.read_text(encoding="utf-8", errors="replace")
        readme_raw = fix_markdown_images_for_attachments(readme_raw)
        landing_md = _build_landing_markdown(
            readme_text=readme_raw,
            stem_to_url=stem_to_url,
            version=version,
        )
        landing_md = _rewrite_github_wiki_urls(landing_md, stem_to_url)
        landing_prepend = (
            _landing_executive_prefix_storage(version=version)
            if presentation == "stakeholder"
            else ""
        )
        try:
            _publish_page_body(
                client,
                api,
                root_id,
                title=root_title,
                md=landing_md,
                kroki_client=kroki_client,
                use_kroki=use_kroki,
                kroki_url=kroki_url,
                presentation=presentation,
                prepend_storage=landing_prepend,
            )
            print(f"Published landing: {root_title} ({root_id})")
        except Exception as exc:
            print(f"FAILED landing page: {exc}", file=sys.stderr)
            failures.append("__landing__")

    if failures:
        raise SystemExit(f"Completed with failures for: {failures!r}")
    print("Done.")


if __name__ == "__main__":
    main()
