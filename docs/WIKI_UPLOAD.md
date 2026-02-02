# GitHub Wiki Upload Instructions

After pushing the main repo to https://github.com/roto31/EXStreamTV, populate the Wiki as follows.

## Option A: Use the generated wiki output

1. Generate wiki pages (already done if you ran the script):
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
