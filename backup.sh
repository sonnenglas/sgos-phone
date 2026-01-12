#!/bin/bash
# Backup script for sgos-phone
# Backs up: PostgreSQL database + voicemail MP3 files
set -e

BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR/voicemails"

# Database dump
echo "Backing up database..."
pg_dump "$DATABASE_URL" > "$BACKUP_DIR/db_$TIMESTAMP.sql"
echo "Database saved: db_$TIMESTAMP.sql"

# Voicemails (copy only new files)
echo "Backing up voicemails..."
COPIED=0
for f in /app/data/voicemails/*.mp3; do
    [ -e "$f" ] || continue
    BASENAME=$(basename "$f")
    if [ ! -f "$BACKUP_DIR/voicemails/$BASENAME" ]; then
        cp "$f" "$BACKUP_DIR/voicemails/"
        COPIED=$((COPIED + 1))
    fi
done
echo "Copied $COPIED new voicemail(s)"

# Cleanup old database dumps (keep 7 days)
find "$BACKUP_DIR" -maxdepth 1 -name "db_*.sql" -mtime +7 -delete

echo "Backup complete: $BACKUP_DIR"
