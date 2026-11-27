#!/bin/sh
# Update the hosted Panko: build the new image while the old one keeps serving, wait until no one's Panko is running
# a job (up to WAIT_MINUTES, 30 by default), then switch, and wait until the new one answers. FORCE=1 switches
# without waiting. A job that is cut off anyway comes back after the switch: free ones carry on by themselves, paid
# ones wait on the jobs page.
#   sh deploy/update.sh
#
# The update runs on its own on the server, so a dropped SSH connection can't stop it halfway (once it left the new
# container made but not started). This shell only follows its log: if the connection drops, the update carries on,
# and `tail -f deploy/update.log` shows it. One update at a time.
set -e
cd "$(dirname "$0")/.."
LOG=deploy/update.log
LOCK=deploy/.update.lock
STATUS=deploy/update.status

if [ -z "$PANKO_UPDATE_RUN" ]; then
  if ! flock -n "$LOCK" true; then
    echo "an update is already running: tail -f $LOG"; exit 1
  fi
  # run a copy: `git pull` may change this file while it's being read
  copy=$(mktemp /tmp/panko-update.XXXXXX)
  cp deploy/update.sh "$copy"
  rm -f "$STATUS"
  PANKO_UPDATE_RUN=1 PANKO_UPDATE_DIR="$(pwd)" nohup setsid sh "$copy" >"$LOG" 2>&1 </dev/null &
  pid=$!
  tail -n +1 -f --pid="$pid" "$LOG"
  exit "$(cat "$STATUS" 2>/dev/null || echo 1)"
fi

# ---- the update itself, detached from the terminal
cd "$PANKO_UPDATE_DIR"
exec 9>"$LOCK"
flock -n 9 || { echo "an update is already running"; echo 1 >"$STATUS"; exit 1; }
trap 'echo $? >"$STATUS"; rm -f "$0"' EXIT      # $0: the copy this runs from
C="docker compose -f deploy/compose.yml"
echo "update: $(date -u '+%Y-%m-%d %H:%M:%S') UTC"
git pull -q
echo "code: $(git log --oneline -1)"
$C build -q
if [ -z "$FORCE" ] && [ -n "$($C ps -q panko)" ]; then
  $C exec -T panko panko host busy --wait "${WAIT_MINUTES:-30}" || {
    echo "jobs still running: not switched. Try again later, or FORCE=1 sh deploy/update.sh"; exit 1; }
fi
$C up -d
# the new container must actually start and answer; start it again once if it didn't
health() { docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
  "$($C ps -aq panko)" 2>/dev/null || echo missing; }
tries=0
while :; do
  h=$(health)
  case "$h" in
    healthy) echo "switched: the new Panko answers"; exit 0 ;;
    created|exited|dead|missing)
      if [ "$tries" -ge 1 ]; then echo "the new container didn't start ($h): see $C logs panko"; exit 1; fi
      echo "the new container is $h: starting it again"; $C up -d; tries=1 ;;
  esac
  waited=$((${waited:-0} + 5))
  if [ "$waited" -ge 180 ]; then echo "the new Panko didn't answer within 3 minutes ($h): see $C logs panko"; exit 1; fi
  sleep 5
done
