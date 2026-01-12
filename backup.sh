#!/bin/bash
# Backup script for sgos-phone
# Run from HOST (not inside container) - uses docker exec for pg_dump
# Called by Toucan's backup orchestrator
set -e

APP_DIR="${APP_DIR:-/srv/apps/sgos-phone}"
BACKUP_DIR="$APP_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR/voicemails"

# Database dump (run pg_dump inside the db container for version match)
echo "Backing up database..."
docker exec sgos-phone-db-1 pg_dump -U phone phone > "$BACKUP_DIR/db_$TIMESTAMP.sql"
echo "Database saved: db_$TIMESTAMP.sql"

# Voicemails (copy only new files)
echo "Backing up voicemails..."
COPIED=0
for f in "$APP_DIR/data/voicemails/"*.mp3; do
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
ls -la "$BACKUP_DIR"
