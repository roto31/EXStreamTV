# Confluence Documentation - EXStreamTV v2.6.0

This folder contains documentation formatted for Confluence upload.

## Upload Instructions

### Method 1: Copy/Paste (Simple)
1. Open the `.confluence.md` file
2. Copy the content
3. In Confluence, create a new page
4. Use "Insert" → "Markup" → "Markdown"
5. Paste the content

### Method 2: Import Markdown (Recommended)
1. Install the "Markdown Macro" app in Confluence
2. Create a new page
3. Use the Markdown macro
4. Paste the content from `.confluence.md` files

### Method 3: Confluence REST API
```bash
# Example using curl
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d @page-content.json \
  "https://your-domain.atlassian.net/wiki/rest/api/content"
```

## Mermaid Diagrams in Confluence

### Option 1: Mermaid Macro (Recommended)
Install the "Mermaid Diagrams for Confluence" app, then use:
```
{mermaid}
graph TD
    A --> B
{mermaid}
```

### Option 2: Draw.io Integration
1. Export Mermaid as SVG from mermaid.live
2. Import into Confluence using Draw.io macro

### Option 3: Pre-rendered Images
If Mermaid macros aren't available:
1. Visit https://mermaid.live
2. Paste the Mermaid code
3. Download as PNG/SVG
4. Upload image to Confluence

## ESTV space — full GitHub + wiki mirror (single page)

Use this when you want one Confluence page that mirrors the **current repo README**, **all `EXStreamTV.wiki` pages** (same order as the wiki sidebar), **every file in `EXStreamTV.wiki/screenshots/`**, and **all Mermaid diagrams** from those pages (via `{code:language=mermaid}` in storage — install a [Mermaid app](https://marketplace.atlassian.com/search?query=mermaid) if diagrams should render visually).

1. Regenerate the Markdown bundle:
   ```bash
   python scripts/build_confluence_mirror_doc.py
   ```
   Output: `docs/confluence/ESTV-GITHUB-WIKI-MIRROR.generated.md`

2. Publish to [ESTV](https://exstreamtv2.atlassian.net/wiki/spaces/ESTV/overview) with the REST helper (needs a valid [API token](https://id.atlassian.com/manage-profile/security/api-tokens)):
   ```bash
   export CONFLUENCE_BASE_URL=https://exstreamtv2.atlassian.net
   export CONFLUENCE_USER=your@email
   export CONFLUENCE_API_TOKEN=your_token
   # optional: export CONFLUENCE_PARENT_PAGE_ID=123456
   uv run scripts/publish_confluence_mirror.py
   ```

   Or use Cursor **mcp-atlassian** (`confluence_search`, `confluence_get_page`, `confluence_create_page`, `confluence_upload_attachment`, etc.). In `.cursor/mcp.json`, use [Confluence-only config](https://mcp-atlassian.soomiles.com/docs/configuration): `CONFLUENCE_URL` must include **`/wiki`** (e.g. `https://exstreamtv2.atlassian.net/wiki`). **Do not commit** `CONFLUENCE_API_TOKEN` in `mcp.json`. Set the same variable in your **shell or Cursor environment** (or in repo-root **`.env`**, gitignored) so both MCP and the publish scripts can authenticate, then reload MCP in Cursor.

   The REST publishers (`publish_confluence_wiki_tree.py`, `publish_confluence_mirror.py`) load **`CONFLUENCE_API_TOKEN`** and **`CONFLUENCE_USER`** from `.env` automatically if those keys are not already set in the environment. `CONFLUENCE_USERNAME` is accepted as an alias for `CONFLUENCE_USER` (matches mcp-atlassian).

3. If the create request fails with a body-size error, split the mirror (e.g. move half the wiki sections to a child page) or publish the prebuilt `docs/confluence/*.confluence.md` set as separate pages instead.

## ESTV space — GitHub-style landing + wiki tree (recommended)

Publishes a root page **EXStreamTV** (full `README.md` plus a wiki index table, top-level folder list, and Confluence links) and one child page per wiki file in sidebar order. Bodies use **storage** format. **Mermaid**: each ```mermaid``` block is sent to **[Kroki](https://kroki.io)** (`POST`), the returned **SVG** is uploaded to that page, and storage references it via **`ri:attachment`** so diagrams appear without a Mermaid Confluence app. Wiki screenshots are attached per page when referenced. Set `CONFLUENCE_SKIP_KROKI=1` to use code macros only (needs a Mermaid renderer app to display).

Titles match the wiki (e.g. **Platform Guide**), with no `Mirror —` prefix. Existing children named `Mirror — …` are reused and renamed on update. The wiki file `EXStreamTV.md` becomes **EXStreamTV Wiki** so it does not collide with the root title.

```bash
# Either export variables, or put CONFLUENCE_USER=… and CONFLUENCE_API_TOKEN=… in repo-root .env
export CONFLUENCE_BASE_URL=https://exstreamtv2.atlassian.net
export CONFLUENCE_USER=your@email
export CONFLUENCE_API_TOKEN=your_token
export CONFLUENCE_SPACE_KEY=ESTV
# optional: export CONFLUENCE_PARENT_PAGE_ID=123456
# optional: pin root (faster): export CONFLUENCE_ROOT_PAGE_ID=327995
# If unset, the script finds an existing page titled EXStreamTV in the space and reuses it.
uv run scripts/publish_confluence_wiki_tree.py
```

Use `uv run scripts/publish_confluence_wiki_tree.py --dry-run` to list planned pages and write a storage XML sample under `docs/confluence/`.

**If every attachment fails with HTTP 415:** the Confluence `httpx` client must not use a default `Content-Type: application/json` header when the same client uploads files (multipart). See **LL-034** in `docs/LESSONS_LEARNED.md` and **RULE DOC-05** in `.cursor/rules/exstreamtv-confluence.mdc`.

**Last Revised:** 2026-03-22

---

## File List

| File | Description | Confluence Space |
|------|-------------|------------------|
| `00-HOME.confluence.md` | Documentation home page | Root |
| `01-SYSTEM-DESIGN.confluence.md` | System architecture | Architecture |
| `02-TUNARR-INTEGRATION.confluence.md` | v2.6.0 integration | Architecture |
| `03-API-REFERENCE.confluence.md` | REST API documentation | API |
| `04-STREAMING-STABILITY.confluence.md` | Streaming features | Guides |
| `05-ADVANCED-SCHEDULING.confluence.md` | Scheduling features | Guides |
| `06-AI-SETUP.confluence.md` | AI configuration | Guides |
| `07-QUICK-START.confluence.md` | Getting started | Guides |
| `08-BUILD-PROGRESS.confluence.md` | Development status | Development |

## Suggested Confluence Structure

```
EXStreamTV Documentation (Space)
├── Home
├── Getting Started
│   ├── Quick Start
│   ├── Installation
│   └── Onboarding
├── User Guides
│   ├── AI Setup
│   ├── Streaming Stability
│   ├── Advanced Scheduling
│   ├── Channel Creation
│   └── Local Media
├── Architecture
│   ├── System Design
│   └── Tunarr/dizqueTV Integration
├── API Reference
│   └── REST API
└── Development
    ├── Build Progress
    ├── Contributing
    └── Changelog
```

## Version Info

- **Documentation Version:** 2.6.0
- **Last Updated:** 2026-01-31
- **Generated For:** Confluence Cloud/Server

**Last Revised:** 2026-03-20
