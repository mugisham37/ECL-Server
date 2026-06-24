#!/usr/bin/env bash
# Stop stale API, Celery, and honcho processes from previous dev runs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${BLUE}[stop]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }

cd "$ROOT"
stopped=0

KEEP_API=0
if [[ "${1:-}" == "--celery-only" ]]; then
  KEEP_API=1
fi

# Honcho orchestrator from a previous `make dev-all`
if pgrep -f "honcho start -f Procfile" >/dev/null 2>&1; then
  log "Stopping honcho..."
  pkill -TERM -f "honcho start -f Procfile" 2>/dev/null || true
  sleep 1
  stopped=1
fi

# API on port 8000 (skip when restarting Celery via `make dev`)
if [[ $KEEP_API -eq 0 ]]; then
  pids=$(lsof -ti:8000 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    log "Stopping process(es) on port 8000..."
    # shellcheck disable=SC2086
    kill -TERM $pids 2>/dev/null || true
    sleep 1
    pids=$(lsof -ti:8000 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      warn "Force-killing remaining process(es) on port 8000..."
      # shellcheck disable=SC2086
      kill -9 $pids 2>/dev/null || true
    fi
    stopped=1
  fi
fi

# Celery workers for this project
if pgrep -f "celery -A app.tasks.celery_app" >/dev/null 2>&1; then
  log "Stopping Celery workers..."
  pkill -TERM -f "celery -A app.tasks.celery_app" 2>/dev/null || true
  sleep 2
  if pgrep -f "celery -A app.tasks.celery_app" >/dev/null 2>&1; then
    warn "Force-killing remaining Celery processes..."
    pkill -9 -f "celery -A app.tasks.celery_app" 2>/dev/null || true
  fi
  stopped=1
fi

# Stale beat schedule lock files (root cwd and run/)
for base in celerybeat-schedule run/celerybeat-schedule; do
  rm -f "${base}" "${base}.db" "${base}.dat" "${base}.dir" "${base}.bak" 2>/dev/null || true
done

if [[ $stopped -eq 0 ]]; then
  log "No stale dev processes found."
else
  log "Cleanup complete."
fi
