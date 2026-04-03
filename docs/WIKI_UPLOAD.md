# GitHub Wiki Upload Instructions

The Wiki at https://github.com/roto31/EXStreamTV/wiki currently has only a placeholder page. To populate it with all documentation (26+ pages, Mermaid diagrams, screenshots):

## Quick way (script does clone + copy + commit)

From the **EXStreamTV project root**:

```bash
chmod +x scripts/push_wiki.sh
./scripts/push_wiki.sh
```

Then push (you must do this yourself so Git can use your credentials):

```bash
cd EXStreamTV.wiki
git push origin main
```

After the push, the wiki Home will be [Home](https://github.com/roto31/EXStreamTV/wiki/Home) and the sidebar will list all pages.

## Option A: Manual steps

1. Generate wiki pages (if needed):
   ```bash
   python scripts/sync_docs_to_wiki.py --wiki-dir wiki_out
   ```

2. Clone the Wiki repo:
   ```bash
   git clone https://github.com/roto31/EXStreamTV.wiki.git
   cd EXStreamTV.wiki
   ```

3. Copy contents of `wiki_out/` into the wiki clone (all `.md` files and `screenshots/` folder).

4. Commit and push:
   ```bash
   git add .
   git commit -m "Populate wiki with full documentation"
   git push origin main
   ```

## Option B: Manual

Create each Wiki page on GitHub (Wiki tab → New Page), paste from the corresponding file under `docs/` (see plan Phase 3.1 table). Preserve all ` ```mermaid ` blocks.

## Post-upload verification (Phase 4)

- [ ] README on GitHub shows project name EXStreamTV, version 2.6.0, link to repo (roto31/EXStreamTV).
- [ ] CHANGELOG compare links open correctly (roto31/EXStreamTV).
- [ ] Wiki Home lists all major docs; each linked page loads and internal links work.
- [ ] Wiki pages with Mermaid (Home, AI-Setup, Advanced-Scheduling, Streaming-Stability, System-Design, Tunarr-DizqueTV-Integration, Integration-Plan, Platform-Comparison): diagrams render.
- [ ] Clone and run: `git clone https://github.com/roto31/EXStreamTV.git && cd EXStreamTV && ./start.sh` (after install) to confirm docs match reality.

## Wiki tab missing from the GitHub repo sidebar

The live wiki may still exist. GitHub often puts **Wiki** in the **“…” overflow** on the repo tab bar, or hides it when the viewport is narrow. The tab also **disappears entirely** if **Settings → General → Features → Wikis** is turned off.

| Symptom | What to do |
| --- | --- |
| No **Wiki** next to Issues / Pull requests | Open the direct URL: `https://github.com/<owner>/<repo>/wiki` (e.g. [EXStreamTV wiki](https://github.com/roto31/EXStreamTV/wiki)). Check **Settings → Wikis** is enabled. Add a **Wiki** link in the repo **About** description and in **README** (this repo does). |
| Wiki URL 404 / empty | Enable Wikis in settings, create **Home**, then push from `EXStreamTV.wiki/` per this doc. |
| Only `EXStreamTV.wiki/` folder in clone | That folder is **not** the hosted wiki until you push to `https://github.com/<owner>/<repo>.wiki.git`. |

Lesson: **LL-037** in `docs/LESSONS_LEARNED.md`. Rule: **RULE DOC-09** in `.cursor/rules/exstreamtv-github-wiki.mdc`.

**Last Revised:** 2026-04-03
