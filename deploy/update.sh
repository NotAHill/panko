#!/bin/sh
# Update the hosted Panko: build the new image while the old one keeps serving, wait until no one's Panko is running
# a job (up to WAIT_MINUTES, 30 by default), then switch. FORCE=1 switches without waiting. A job that is cut off
# anyway comes back after the switch: free ones carry on by themselves, paid ones wait on the jobs page.
#   sh deploy/update.sh
set -e
cd "$(dirname "$0")/.."
C="docker compose -f deploy/compose.yml"
git pull -q
$C build -q
if [ -z "$FORCE" ] && [ -n "$($C ps -q panko)" ]; then
  $C exec -T panko panko host busy --wait "${WAIT_MINUTES:-30}" || {
    echo "jobs still running: not switched. Try again later, or FORCE=1 sh deploy/update.sh"; exit 1; }
fi
$C up -d
