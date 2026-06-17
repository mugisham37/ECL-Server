#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[dev]${NC}  $*"; }
ok()   { echo -e "${GREEN}[ok]${NC}   $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
die()  { echo -e "${RED}[err]${NC}  $*" >&2; exit 1; }

cd "$ROOT"

# ── 1. Docker ──────────────────────────────────────────────────────────────
log "Checking Docker daemon..."
docker info &>/dev/null || die "Docker is not running. Start Docker Desktop (or the daemon) and try again."
ok "Docker is running."

# ── 2. Infrastructure ──────────────────────────────────────────────────────
log "Starting infrastructure services (Redis + MinIO)..."
docker compose -f docker/docker-compose.yml up -d

# ── 3. Wait for Redis ──────────────────────────────────────────────────────
log "Waiting for Redis on :6380..."
for i in $(seq 1 30); do
  if docker compose -f docker/docker-compose.yml exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
    ok "Redis is ready."
    break
  fi
  [ "$i" -eq 30 ] && die "Redis did not become healthy after 30s. Check: docker compose -f docker/docker-compose.yml logs redis"
  sleep 1
done

# ── 4. Wait for MinIO ──────────────────────────────────────────────────────
log "Waiting for MinIO on :9000..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:9000/minio/health/live &>/dev/null; then
    ok "MinIO is ready."
    break
  fi
  if [ "$i" -eq 30 ]; then
    warn "MinIO health check timed out — continuing anyway."
    break
  fi
  sleep 1
done

# ── 5. Migrations ──────────────────────────────────────────────────────────
log "Applying database migrations..."
if .venv/bin/alembic upgrade head 2>&1; then
  ok "Database is up to date."
else
  warn "Migration step had issues — database may already be current or there's a connection problem."
fi

# ── 6. Launch ──────────────────────────────────────────────────────────────
echo ""
log "All systems go. Starting API + Celery worker..."
echo ""
exec .venv/bin/honcho start -f Procfile.dev
