---
name: exstreamtv-confluence-publish
description: >-
  Publishes EXStreamTV README and EXStreamTV.wiki to Confluence Cloud with GitHub-like
  layout, storage-format Markdown, and Mermaid via code macros. Covers when to use REST
  scripts vs Atlassian MCP, uv run invocation, space keys, title rules, and attachment
  behavior. Use when editing Confluence publishing scripts, docs/confluence/, EXStreamTV.wiki/,
  or when the user asks to mirror the wiki to Confluence, update ESTV docs, or fix
  Mermaid/rendering on Confluence.
---

# EXStreamTV Confluence & Wiki Publishing

## Lessons (see `docs/LESSONS_LEARNED.md`)

| ID | Topic |
| --- | --- |
| LL-031 | Atlassian MCP uses **ADF**; full Markdown + Mermaid needs **REST + storage** |
| LL-032 | **`uv run scripts/…`** for PEP 723 deps — not `uv run python scripts/…` |
| LL-033 | Unique titles per space — **`EXStreamTV`** root vs **`EXStreamTV Wiki`** child |
| LL-034 | **`httpx.Client`**: no default **`Content-Type: application/json`** if the same client uploads attachments — else Confluence **415** on all files (SVG + screenshots) |

## When to Use Which Publisher

| Goal | Command |
| --- | --- |
| **Landing + wiki children**, Mermaid as **SVG attachments** (Kroki), screenshots | `uv run scripts/publish_confluence_wiki_tree.py` |
| **Single bundled page** | `build_confluence_mirror_doc.py` then `uv run scripts/publish_confluence_mirror.py` (Mermaid: code macro unless you extend it) |
| **ADF manifest (MCP)** | `uv run python scripts/build_atlassian_adf_manifest.py` — not for rendered diagrams |

### Mermaid / diagrams

- Wiki tree publisher calls **Kroki** (`POST` diagram → SVG), uploads `mermaid-{hash}.svg` to the **same Confluence page** **before** saving storage HTML that references `ri:attachment`.
- Offline or blocked Kroki: `CONFLUENCE_SKIP_KROKI=1` (code macro only) or fix network; override URL with `CONFLUENCE_KROKI_URL`.

## Environment (REST)

```bash
export CONFLUENCE_BASE_URL=https://exstreamtv2.atlassian.net
export CONFLUENCE_USER=email@example.com
export CONFLUENCE_API_TOKEN=...
export CONFLUENCE_SPACE_KEY=ESTV
# optional: CONFLUENCE_PARENT_PAGE_ID, CONFLUENCE_ROOT_PAGE_ID
```

## Key Files

- `scripts/publish_confluence_wiki_tree.py` — tree publish (recommended for “GitHub feel”).
- `scripts/publish_confluence_mirror.py` — single-page bundle.
- `scripts/confluence_markdown_storage.py` — Markdown → storage (Mermaid + code + images).
- `scripts/wiki_sidebar_order.py` — `SIDEBAR_STEMS`, `display_title`, `confluence_wiki_child_title`.
- `docs/confluence/README.md` — human runbook.

## Checklist Before Changing Publishers

1. **Mermaid**: still using `confluence_markdown_storage.markdown_to_storage` / same macro shape?
2. **uv**: docs and examples use `uv run scripts/<name>.py`?
3. **Titles**: any new wiki stem that equals root title? Extend `confluence_wiki_child_title` if needed.
4. **Sidebar**: add stems only in `wiki_sidebar_order.SIDEBAR_STEMS` once.
5. **Attachments / httpx**: Confluence `httpx.Client` must **not** set default **`Content-Type: application/json`** when `post(..., files=…)` is used — only **`Accept: application/json`** (RULE DOC-05, LL-034). If publishes log **`Attachment failed …: 415`**, check this first.

## Verification

- `uv run scripts/publish_confluence_wiki_tree.py --dry-run` — lists pages; writes `docs/confluence/_dry_run_wiki_tree_storage_snippet.xml` (confirm `mermaid` in macro if sample includes a mermaid page).
