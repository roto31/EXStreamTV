#!/usr/bin/env bash
# Push generated wiki content to https://github.com/roto31/EXStreamTV.wiki
# Run from project root. You will need to run 'git push' yourself (credentials).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WIKI_OUT="$PROJECT_ROOT/wiki_out"
WIKI_CLONE="${1:-$PROJECT_ROOT/EXStreamTV.wiki}"

if [[ ! -d "$WIKI_OUT" ]]; then
  echo "Generating wiki output..."
  python3 "$PROJECT_ROOT/scripts/sync_docs_to_wiki.py" --wiki-dir "$WIKI_OUT"
fi

if [[ ! -d "$WIKI_CLONE" ]]; then
  echo "Cloning wiki repo..."
  git clone https://github.com/roto31/EXStreamTV.wiki.git "$WIKI_CLONE"
  cd "$WIKI_CLONE"
else
  cd "$WIKI_CLONE"
  git fetch origin
  git checkout main 2>/dev/null || git checkout master 2>/dev/null || true
  git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || true
fi

echo "Copying wiki_out into wiki clone..."
for f in "$WIKI_OUT"/*.md; do
  [[ -f "$f" ]] && cp "$f" "$WIKI_CLONE/"
done
if [[ -d "$WIKI_OUT/screenshots" ]]; then
  rm -rf "$WIKI_CLONE/screenshots"
  cp -R "$WIKI_OUT/screenshots" "$WIKI_CLONE/"
fi

git add -A
if git diff --staged --quiet; then
  echo "No changes to commit."
else
  git commit -m "Populate wiki with full documentation (sync from docs/)"
  echo "Committed. Now run: cd $WIKI_CLONE && git push origin main"
fi

echo ""
echo "Next step: push the wiki (requires GitHub auth)"
echo "  cd $WIKI_CLONE"
echo "  git push origin main"
