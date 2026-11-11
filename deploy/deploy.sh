#!/usr/bin/env bash
# Deploy the Digital Hub on this server with Docker. See docs/deploy.md.
#
#   deploy/deploy.sh               pull origin/production, build, migrate, restart
#   deploy/deploy.sh --no-pull     deploy the code already checked out
#   deploy/deploy.sh --rollback    restart the previous image (no build, no migrations)
#
# Run from anywhere as the user that owns the checkout (in the docker group).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose --file "$ROOT/deploy/compose.production.yaml")
BRANCH="${DEPLOY_BRANCH:-production}"
KEEP_IMAGES=5

# The public host name, used to check the site the way nginx reaches it.
SITE_HOST="${SITE_HOST:-data-hub.mopd.gov.et}"

export APP_UID="$(id -u)"
# WEB_PORT may be set in .env; nginx's upstream must use the same port.
export WEB_PORT="${WEB_PORT:-$(sed -n 's/^WEB_PORT=//p' "$ROOT/.env" 2>/dev/null | tail -1)}"
export WEB_PORT="${WEB_PORT:-8000}"

log() { printf '\n==> %s\n' "$*"; }

wait_healthy() {
  local container status
  container="$("${COMPOSE[@]}" ps --quiet web)"
  for _ in $(seq 1 30); do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || echo missing)"
    if [[ "$status" == "healthy" ]]; then
      break
    fi
    sleep 3
  done
  # Request a real page as nginx does (Host + X-Forwarded-Proto), which also
  # catches a bad SECRET_KEY/ALLOWED_HOSTS or an HTTPS redirect loop.
  local code
  code="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 \
    --header "Host: $SITE_HOST" --header 'X-Forwarded-Proto: https' \
    "http://127.0.0.1:$WEB_PORT/admin/login/" || true)"
  if [[ "$status" == "healthy" && "$code" == "200" ]]; then
    log "web is up on 127.0.0.1:$WEB_PORT (https://$SITE_HOST/admin/login/ -> 200)"
    return 0
  fi
  echo "web is not serving (container: $status, /admin/login/: ${code:-no answer}). Recent logs:" >&2
  "${COMPOSE[@]}" logs --tail 60 web >&2
  return 1
}

warn_about_systemd() {
  local unit
  for unit in daphne celery uwsgi; do
    if systemctl is-active --quiet "$unit.service" 2>/dev/null; then
      echo "WARNING: $unit.service is still running outside Docker. Stop it once nginx points at" \
           "127.0.0.1:$WEB_PORT: sudo systemctl disable --now $unit.service" >&2
    fi
  done
}

cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing $ROOT/.env (copy .env.example and fill it in)." >&2
  exit 1
fi
if [[ ! -f secrets/firebase-service-account.json ]] && ! grep -q '^FIREBASE_CREDENTIALS=' .env; then
  echo "WARNING: no secrets/firebase-service-account.json: push notifications will not be sent." >&2
fi

if [[ "${1:-}" == "--rollback" ]]; then
  previous="$(docker image ls digital-hub --format '{{.Tag}}' | grep -v '^latest$' | sed -n 2p)"
  if [[ -z "$previous" ]]; then
    echo "No previous image to roll back to." >&2
    exit 1
  fi
  log "Rolling back to digital-hub:$previous"
  IMAGE_TAG="$previous" "${COMPOSE[@]}" up --detach --no-build --remove-orphans
  wait_healthy
  exit 0
fi

if [[ "${1:-}" != "--no-pull" ]]; then
  log "Updating code to origin/$BRANCH"
  git fetch origin "$BRANCH"
  git reset --hard "origin/$BRANCH"
fi

export IMAGE_TAG="$(git rev-parse --short HEAD)"
mkdir -p core/media

log "Building digital-hub:$IMAGE_TAG"
"${COMPOSE[@]}" build web
docker tag "digital-hub:$IMAGE_TAG" digital-hub:latest

log "Migrating the database"
# Migrations are committed and built into the image. A database whose history
# came from the old per-server migration files must be adopted once first.
if ! "${COMPOSE[@]}" run --rm --no-deps web python manage.py adopt_migrations --check; then
  echo "Back up the database, then run once:" >&2
  echo "  docker compose -f deploy/compose.production.yaml run --rm --no-deps web python manage.py adopt_migrations --apply" >&2
  echo "and deploy again (docs/deploy.md, 'One-time switch')." >&2
  exit 1
fi
"${COMPOSE[@]}" run --rm --no-deps web python manage.py migrate --noinput

log "Starting web, worker and beat"
"${COMPOSE[@]}" up --detach --no-build --remove-orphans
wait_healthy

log "Removing old images (keeping the last $KEEP_IMAGES)"
docker image ls digital-hub --format '{{.Tag}}' | grep -v '^latest$' | tail -n +$((KEEP_IMAGES + 1)) \
  | xargs -r -I{} docker image rm "digital-hub:{}" >/dev/null || true
docker image prune --force >/dev/null

warn_about_systemd
log "Deployed $IMAGE_TAG"
