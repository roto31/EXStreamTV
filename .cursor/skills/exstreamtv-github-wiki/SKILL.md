---
name: exstreamtv-github-wiki
description: >-
  GitHub Wiki appears missing from the repo sidebar, or confusion between EXStreamTV.wiki/ in the
  main repo and the live github.com/.../wiki site. Use for wiki tab not visible, 404 wiki, or
  “where is our documentation on GitHub?”
---

# EXStreamTV — GitHub Wiki (sidebar, URL, push)

## Lesson

| ID | Topic |
| --- | --- |
| LL-037 | Wiki tab **hidden or disabled** in UI; **`EXStreamTV.wiki/`** ≠ hosted until **push** to `*.wiki.git` |

## Diagnosis (in order)

1. **Open** `https://github.com/<owner>/<repo>/wiki` (this project: [EXStreamTV Wiki](https://github.com/roto31/EXStreamTV/wiki)). If it loads with pages, the wiki exists; the issue is **navigation**, not deletion.
2. **Settings → General → Features → Wikis** — must be **on** for the tab to appear for users with access.
3. **UI** — **Wiki** may be under the repo tab **“…”** menu or omitted on small screens.
4. **Wrong fork** — Confirm **owner/repo** matches the canonical remote.

## If content is stale or empty

1. Regenerate: `python scripts/sync_docs_to_wiki.py --wiki-dir EXStreamTV.wiki`
2. Push hosted wiki: `scripts/push_wiki.sh` then `git push` from the wiki clone (see `docs/WIKI_UPLOAD.md`).

## Related

- `.cursor/skills/exstreamtv-documentation-parity/SKILL.md` — dual publish + `verify_wiki_confluence_docs.py --kroki`
- `.cursor/rules/exstreamtv-github-wiki.mdc` — RULE DOC-09
