#!/usr/bin/env bash
# Nightly, encrypted backup of the hosted Panko's data with restic (run by cron on the server; see deploy/README.md).
# SQLite stores are copied with SQLite's own backup first (as <name>.db.bak beside the data's layout, under $SNAP),
# so a store that's being written is still whole.
# Settings in /etc/panko-backup.env: RESTIC_REPOSITORY, RESTIC_PASSWORD_FILE and the storage's keys.
set -euo pipefail

DATA=${PANKO_HOST_DATA:-/srv/panko}
SNAP=${PANKO_DB_SNAP:-/var/backups/panko-db}
# shellcheck disable=SC1091
source /etc/panko-backup.env

mkdir -p "$SNAP"
find "$SNAP" -name '*.db.bak' -type f -delete
cd "$DATA"
find . -name '*.db' -type f -not -path './run/*' | while read -r db; do
  mkdir -p "$SNAP/$(dirname "$db")"
  sqlite3 "$db" ".backup '$SNAP/$db.bak'"
done

restic backup "$DATA" "$SNAP" --exclude '*.db' --exclude '*.db-wal' --exclude '*.db-shm' \
  --exclude "$DATA/run" --exclude "$DATA/tmp" --tag panko --quiet
restic forget --tag panko --keep-daily 30 --prune --quiet
