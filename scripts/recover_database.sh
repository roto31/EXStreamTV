#!/usr/bin/env bash
# Recover EXStreamTV database from corruption (e.g. "database disk image is malformed").
# Usage: ./scripts/recover_database.sh [backup_file] [target_db_path]
#   backup_file: optional; default = latest exstreamtv_backup_*.db.gz in backups/
#   target_db_path: optional; default = PROJECT_ROOT/exstreamtv.db
#   If the app shows "Database path: /some/path/exstreamtv.db", use that as target_db_path.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUPS_DIR="$PROJECT_ROOT/backups"
DB_PATH="${2:-$PROJECT_ROOT/exstreamtv.db}"
DB_PATH_WAL="${DB_PATH}-wal"
DB_PATH_SHM="${DB_PATH}-shm"

if [ -n "$1" ] && [ -f "$1" ]; then
  BACKUP="$1"
else
  BACKUP=$(ls -t "$BACKUPS_DIR"/exstreamtv_backup_*.db.gz 2>/dev/null | head -1)
  if [ -z "$BACKUP" ]; then
    echo "No backup found in $BACKUPS_DIR"
    echo "Usage: $0 [path_to_backup.db.gz] [target_db_path]"
    echo "  target_db_path = path shown in the app error (e.g. /full/path/exstreamtv.db)"
    exit 1
  fi
  echo "Using latest backup: $BACKUP"
fi

echo "Stopping any process using the database is recommended (e.g. stop EXStreamTV server)."
echo "Restore from: $BACKUP"
echo "Target DB:    $DB_PATH"
read -p "Proceed? [y/N] " -n 1 -r
echo
[[ ! $REPLY =~ ^[Yy]$ ]] && exit 0

# Move corrupted DB aside (keep WAL/SHM if present)
if [ -f "$DB_PATH" ]; then
  mv "$DB_PATH" "${DB_PATH}.corrupted.$(date +%Y%m%d_%H%M%S)"
fi
[ -f "$DB_PATH_WAL" ] && mv "$DB_PATH_WAL" "${DB_PATH_WAL}.old"
[ -f "$DB_PATH_SHM" ] && mv "$DB_PATH_SHM" "${DB_PATH_SHM}.old"

# Decompress backup to DB path
mkdir -p "$(dirname "$DB_PATH")"
if [[ "$BACKUP" == *.gz ]]; then
  gunzip -c "$BACKUP" > "$DB_PATH"
else
  cp "$BACKUP" "$DB_PATH"
fi

echo "Restored. Start EXStreamTV again. If problems persist, try SQLite recover:"
echo "  sqlite3 $DB_PATH \".recover\" | sqlite3 exstreamtv_recovered.db"
echo "  mv $DB_PATH ${DB_PATH}.bak && mv exstreamtv_recovered.db $DB_PATH"
