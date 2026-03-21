---
name: exstreamtv-documentation-parity
description: >-
  Dual-target documentation: GitHub Wiki (EXStreamTV.wiki) plus Confluence ESTV, with mandatory
  verification (verify_wiki_confluence_docs.py --kroki). Use when the user asks to publish or
  update documentation, fix missing Mermaid on Confluence, blank wiki/Confluence pages, or
  achieve 100% doc completion across both surfaces.
---

# EXStreamTV — Documentation parity (GitHub Wiki + Confluence)

## Lesson

| ID | Topic |
| --- | --- |
| LL-036 | Wiki can be correct while Confluence **misses Mermaid** (upload/Kroki/JS) or looks **blank** (stubs); **two publish steps** + **verify** required |

## Mandatory workflow when user asks to publish / update documentation

1. **Edit** `EXStreamTV.wiki/*.md` (and repo `docs/` if applicable) — single source for wiki mirror.
2. **GitHub Wiki** — Commit and **push** `EXStreamTV.wiki/` to the GitHub Wiki (so https://github.com/…/wiki matches).
3. **Confluence** — From repo root:  
   `uv run scripts/publish_confluence_wiki_tree.py`  
   (`.env` with `CONFLUENCE_USER`, `CONFLUENCE_API_TOKEN`; optional `CONFLUENCE_ROOT_PAGE_ID`.)
4. **Verify (required before “done”)**  
   `uv run scripts/verify_wiki_confluence_docs.py --kroki`  
   Optional: `--warn-thin 200` to flag sparse pages. Exit **0** required.
5. **Browser spot-check** — Log into Confluence; allow Atlassian scripts; confirm diagrams on a heavy page (e.g. Platform Comparison, Architecture Diagrams).

## Missing Mermaid on Confluence — checklist

| Check | Action |
| --- | --- |
| Past **415** attachment errors | Republish after LL-034 fix; publisher now **aborts** if SVG upload fails |
| Log: `Kroki Mermaid render failed` | Fix diagram syntax or Kroki URL; or install Confluence Mermaid app for code macro |
| Broken images with good Kroki | Remove orphan `mermaid-*.svg` on page, republish |
| Confluence **JS load error** | Fix network/adblock; not a content bug |

## Scripts

| Script | Role |
| --- | --- |
| `scripts/verify_wiki_confluence_docs.py` | Missing sidebar files; per-file Mermaid count; `--kroki` validates Kroki |
| `scripts/publish_confluence_wiki_tree.py` | README + wiki tree → Confluence storage + SVG attachments |
| `scripts/wiki_sidebar_order.py` | `SIDEBAR_STEMS` — must match wiki files |

## Related skill

- `.cursor/skills/exstreamtv-confluence-publish/SKILL.md` — REST vs MCP, env, LL-031–035 technical detail
