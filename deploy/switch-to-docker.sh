#!/usr/bin/env bash
# One-time switch of the production server from systemd (Daphne and Celery in
# .venv) to Docker, keeping the database, uploads and configuration.
#
#   bash switch-to-docker.sh prepare <branch>   backup, build, pre-flight checks.
#                                               The live site is not touched.
#   bash switch-to-docker.sh cutover            switch over (a few seconds of
#                                               downtime at the nginx reload).
#   bash switch-to-docker.sh rollback           back to systemd and the old code.
#
# Run a copy from outside the checkout (the cutover replaces the checkout):
#   cd /mnt/data/Digital_Hub && git fetch origin <branch> &&
#     git show FETCH_HEAD:deploy/switch-to-docker.sh > /tmp/switch-to-docker.sh &&
#     bash /tmp/switch-to-docker.sh prepare <branch>
#
# Everything is logged to $BACKUPS/switch.log; the screen shows a summary.
set -euo pipefail

ROOT="${ROOT:-/mnt/data/Digital_Hub}"
BACKUPS="${BACKUPS:-/mnt/data/backups/digital-hub}"
NGINX_CONF="${NGINX_CONF:-/etc/nginx/sites-available/data-hub.conf}"
SITE_HOST="${SITE_HOST:-data-hub.mopd.gov.et}"
WEB_PORT="${WEB_PORT:-8000}"
OLD_SERVICES=(daphne celery uwsgi)
OLD_DIRS=(core/AI core/Notification core/userManagement core/Videos)
APPS="'AI','Notification','userManagement','chat','mobile'"
COUNT_TABLES=(userManagement_customuser userManagement_ministry AI_chatinstance AI_questionhistory
              AI_catalogentity Notification_notification Notification_devicetoken chat_conversation
              chat_message mobile_app mobile_faq)
STATE="$BACKUPS/switch-state"
LOG="$BACKUPS/switch.log"
COMPOSE=(docker compose --file "$ROOT/deploy/compose.production.yaml")

say()  { printf '%s\n' "$*" | tee -a "$LOG"; }
step() { say ""; say "==> $*"; }
die()  { say "FAILED: $*"; say "(details: $LOG)"; exit 1; }
quiet() { "$@" >>"$LOG" 2>&1; }   # run, keeping the output in the log only

env_value() {   # a value from .env, without surrounding quotes
  grep -E "^$1=" "$ROOT/.env" | tail -1 | cut -d= -f2- | sed -e "s/^['\"]//" -e "s/['\"]\$//"
}

db() {          # psql against the production database
  PGPASSWORD="$(env_value DATABASE_PASSWORD)" psql --no-psqlrc --quiet --tuples-only --no-align \
    --host "$(env_value DATABASE_HOST)" --port "$(env_value DATABASE_PORT)" \
    --username "$(env_value DATABASE_USER)" --dbname "$(env_value DATABASE_NAME)" "$@"
}

row_counts() {  # "table=count" for the tables that hold the site's data
  local table
  for table in "${COUNT_TABLES[@]}"; do
    printf '%s=%s\n' "$table" "$(db --command "select count(*) from \"$table\"" 2>/dev/null || echo missing)"
  done
}

backup_database() {
  local file
  file="$BACKUPS/database-$(date +%Y%m%d-%H%M%S).dump"
  PGPASSWORD="$(env_value DATABASE_PASSWORD)" pg_dump --format custom \
    --host "$(env_value DATABASE_HOST)" --port "$(env_value DATABASE_PORT)" \
    --username "$(env_value DATABASE_USER)" --file "$file" "$(env_value DATABASE_NAME)" >>"$LOG" 2>&1 \
    || die "pg_dump failed"
  local tables
  tables="$(pg_restore --list "$file" | grep -c 'TABLE DATA')"
  [[ "$tables" -gt 20 ]] || die "the backup looks incomplete ($tables tables)"
  say "database backup: $file ($(du -h "$file" | cut -f1), $tables tables)"
  echo "$file" > "$BACKUPS/latest-database-backup"
}

state() { grep -E "^$1=" "$STATE" | tail -1 | cut -d= -f2-; }

in_image() {    # run a command in the new image, configured exactly as production will be
  IMAGE_TAG="$(state NEW_SHORT)" APP_UID="$(id -u)" WEB_PORT="$WEB_PORT" \
    "${COMPOSE[@]}" run --rm --no-deps -T web "$@"
}

settings_fingerprint='
import hashlib, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
from django.conf import settings
d = settings.DATABASES["default"]
h = lambda v: hashlib.sha256(str(v).encode()).hexdigest()[:16]
print("secret_key=" + h(settings.SECRET_KEY))
print("database=" + h("|".join(str(d.get(k)) for k in ("ENGINE", "NAME", "USER", "PASSWORD", "HOST", "PORT"))))
'

page_status() { # HTTP status of a path on the new container, asked the way nginx asks
  curl --silent --output /dev/null --write-out '%{http_code}' --max-time 15 \
    --header "Host: $SITE_HOST" --header 'X-Forwarded-Proto: https' "http://127.0.0.1:$WEB_PORT$1" || true
}

public_status() { # HTTP status of a path through this server's nginx, with the real host name and certificate
  local path="$1"; shift
  curl --silent --output /dev/null --write-out '%{http_code}' --max-time 20 \
    --resolve "$SITE_HOST:443:127.0.0.1" "$@" "https://$SITE_HOST$path" || true
}

ensure_docker_access() {
  docker info >/dev/null 2>&1 && return 0
  if ! getent group docker | grep -qw "$(id -un)"; then
    step "Adding $(id -un) to the docker group"
    sudo usermod --append --groups docker "$(id -un)"
  fi
  # This login session predates the group change; re-run under the new group.
  exec sg docker -c "$(printf '%q ' bash "$SCRIPT" "${ARGS[@]}")"
}

# --- prepare -----------------------------------------------------------------

prepare() {
  local branch="${1:?usage: prepare <branch>}"
  cd "$ROOT"
  [[ -f .env ]] || die "no $ROOT/.env"

  step "Fetching $branch"
  quiet git fetch origin "$branch" || die "git fetch failed"
  local sha short previous
  sha="$(git rev-parse FETCH_HEAD)"; short="$(git rev-parse --short FETCH_HEAD)"; previous="$(git rev-parse HEAD)"
  say "current code: $(git log --oneline -1 | cut -c1-70)"
  say "new code:     $(git log --oneline -1 "$sha" | cut -c1-70)"
  if [[ -f "$STATE" && "$(state STAGE)" == "switched" ]]; then
    die "this server has already been switched (see $STATE)"
  fi
  printf 'STAGE=preparing\nPREVIOUS=%s\nNEW=%s\nNEW_SHORT=%s\n' "$previous" "$sha" "$short" > "$STATE"

  step "Keeping the Firebase key outside git"
  mkdir -p secrets
  if [[ ! -f secrets/firebase-service-account.json ]]; then
    cp core/Notification/push_notification/admas-*.json secrets/firebase-service-account.json \
      || die "Firebase key not found in core/Notification/push_notification/"
  fi
  chmod 600 secrets/*.json
  say "secrets/firebase-service-account.json present"

  step "Backing up"
  backup_database
  cp -p .env "$BACKUPS/env-$(date +%Y%m%d-%H%M%S)"
  tar -czf "$BACKUPS/media-$(date +%Y%m%d-%H%M%S).tar.gz" -C core media 2>>"$LOG" || die "media backup failed"
  say "configuration and uploads backed up to $BACKUPS ($(du -sh core/media | cut -f1) of uploads)"
  row_counts > "$BACKUPS/row-counts-before"
  say "rows now: $(tr '\n' ' ' < "$BACKUPS/row-counts-before")"

  step "What the running site uses (to compare with the new image)"
  (cd core && "$ROOT/.venv/bin/python" -c "$settings_fingerprint") > "$BACKUPS/settings-before" 2>>"$LOG" \
    || die "could not read the current settings"
  say "recorded fingerprints of SECRET_KEY and the database settings (no values are stored)"

  step "Building the image from $short (the live checkout is not changed)"
  git archive --format=tar "$sha" \
    | docker build --build-arg APP_UID="$(id -u)" --tag "digital-hub:$short" --tag digital-hub:latest - >>"$LOG" 2>&1 \
    || die "docker build failed"
  say "built digital-hub:$short ($(docker image ls "digital-hub:$short" --format '{{.Size}}'))"

  step "Pre-flight: the new image against the live database (read-only)"
  mkdir -p deploy
  git show "$sha:deploy/compose.production.yaml" > deploy/compose.production.yaml
  in_image python manage.py check >>"$LOG" 2>&1 || die "Django checks failed in the new image"
  say "Django checks pass with production settings"
  in_image python -c "$settings_fingerprint" 2>>"$LOG" | grep -E '^(secret_key|database)=' > "$BACKUPS/settings-after" \
    || die "could not read settings in the new image"
  if ! diff "$BACKUPS/settings-before" "$BACKUPS/settings-after" >>"$LOG"; then
    die "the new image reads SECRET_KEY or the database settings differently from the running site"
  fi
  say "SECRET_KEY and database settings are identical in the new image (users stay signed in)"
  in_image python manage.py adopt_migrations 2>>"$LOG" | tee -a "$LOG" | grep -vE '^\{|^\[20' || true
  in_image python manage.py adopt_migrations >>"$LOG" 2>&1 || die "the database does not match the expected schema"

  sed -i 's/^STAGE=.*/STAGE=prepared/' "$STATE"
  step "READY. Nothing on the live site has changed. Next: bash $SCRIPT cutover"
}

# --- cutover -----------------------------------------------------------------

cutover() {
  cd "$ROOT"
  [[ -f "$STATE" && "$(state STAGE)" == "prepared" ]] || die "run 'prepare' first"
  local sha short
  sha="$(state NEW)"; short="$(state NEW_SHORT)"
  docker image inspect "digital-hub:$short" >/dev/null 2>&1 || die "image digital-hub:$short is missing; run prepare again"
  ss -ltn | grep -q ":$WEB_PORT " && die "port $WEB_PORT is already in use"

  step "Final backup"
  backup_database
  db --command "\\copy (select app, name, applied from django_migrations where app in ($APPS)) to '$BACKUPS/migration-history-before.csv' csv" \
    || die "could not save the migration history"
  tar -czf "$BACKUPS/old-migration-files.tar.gz" $(ls -d core/*/migrations 2>/dev/null) 2>>"$LOG" || true
  sudo cp -p "$NGINX_CONF" "$BACKUPS/nginx-data-hub.conf.before"
  say "saved the migration history, old migration files and the nginx site"

  step "Database: adopting the committed migrations, then migrating"
  in_image python manage.py adopt_migrations --apply >>"$LOG" 2>&1 || die "adopt_migrations failed (nothing else was changed)"
  in_image python manage.py migrate --noinput >>"$LOG" 2>&1 || die "migrate failed; the old site is still running"
  say "migrations applied: $(db --command "select count(*) from django_migrations where app in ($APPS)") recorded for the project apps"

  step "Stopping the old Celery worker (so it cannot take the new code's tasks)"
  sudo systemctl stop celery.service || true

  step "Replacing the code in $ROOT"
  quiet git reset --hard "$sha" || die "git reset failed"
  rm -rf "${OLD_DIRS[@]}" google-env
  quiet git clean --force -- core/chat/migrations core/mobile/migrations
  sudo chown -R "$(id -un)":www-data core/media secrets
  sudo chmod -R u+rwX,g+rwX core/media
  say "now at $(git log --oneline -1 | cut -c1-70)"

  step "Starting the containers"
  sudo systemctl enable docker.service >>"$LOG" 2>&1 || true   # so they come back after a reboot
  IMAGE_TAG="$short" APP_UID="$(id -u)" WEB_PORT="$WEB_PORT" "${COMPOSE[@]}" up --detach --remove-orphans >>"$LOG" 2>&1 \
    || die "docker compose up failed; the old site is still serving (run rollback to restore the old code)"
  local code=""
  for _ in $(seq 1 40); do
    code="$(page_status /admin/login/)"
    [[ "$code" == "200" ]] && break
    sleep 3
  done
  if [[ "$code" != "200" ]]; then
    "${COMPOSE[@]}" logs --tail 40 web >>"$LOG" 2>&1 || true
    die "the new web container answers '$code' on /admin/login/; nginx was not switched (run rollback)"
  fi
  say "new web container serves /admin/login/ (200) and static files ($(page_status /static/assets/css/style.css))"

  step "Switching nginx to the containers"
  sudo sed -i "s|server unix:///mnt/data/Digital_Hub/core/domains.sock;|server 127.0.0.1:$WEB_PORT;|" "$NGINX_CONF"
  # Static files now come from the image (WhiteNoise), so every deploy ships matching CSS/JS.
  sudo sed -i 's|alias /mnt/data/Digital_Hub/core/staticfiles/;|proxy_pass http://django; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme;|' "$NGINX_CONF"
  if ! grep -q "server 127.0.0.1:$WEB_PORT;" "$NGINX_CONF" || grep -q 'core/staticfiles' "$NGINX_CONF" \
      || ! sudo nginx -t >>"$LOG" 2>&1; then
    sudo cp -p "$BACKUPS/nginx-data-hub.conf.before" "$NGINX_CONF"
    die "the nginx change did not validate and was undone; the old site is still serving (run rollback)"
  fi
  sudo systemctl reload nginx
  say "nginx now proxies to 127.0.0.1:$WEB_PORT"

  step "Checking the public site"
  sleep 2
  local public removed
  public="$(public_status /admin/login/)"
  removed="$(public_status /api/user/auth/verify-otp/ --request POST)"
  say "https://$SITE_HOST/admin/login/ -> $public ; removed endpoint -> $removed (404 means the new code is serving)"
  if [[ "$public" != "200" || "$removed" != "404" ]]; then
    die "the public site is not answering from the new code; run: bash $SCRIPT rollback"
  fi

  step "Stopping the old services for good"
  sudo systemctl disable --now "${OLD_SERVICES[@]/%/.service}" >>"$LOG" 2>&1 || true
  rm -f core/domains.sock core/domains.sock.lock

  step "Data check"
  row_counts > "$BACKUPS/row-counts-after"
  if diff "$BACKUPS/row-counts-before" "$BACKUPS/row-counts-after" >>"$LOG"; then
    say "every table has the same number of rows as before the switch"
  else
    say "row counts changed (normal if people used the site in between):"
    diff "$BACKUPS/row-counts-before" "$BACKUPS/row-counts-after" | tee -a "$LOG" || true
  fi
  "${COMPOSE[@]}" ps --format '{{.Service}}: {{.Status}}' | tee -a "$LOG"

  sed -i 's/^STAGE=.*/STAGE=switched/' "$STATE"
  step "DONE. The site runs in Docker. Backups: $BACKUPS"
}

# --- rollback ----------------------------------------------------------------

rollback() {
  cd "$ROOT"
  [[ -f "$STATE" ]] || die "nothing to roll back"
  step "Restoring nginx"
  if [[ -f "$BACKUPS/nginx-data-hub.conf.before" ]]; then
    sudo cp -p "$BACKUPS/nginx-data-hub.conf.before" "$NGINX_CONF"
  fi
  step "Stopping the containers"
  [[ -f deploy/compose.production.yaml ]] && "${COMPOSE[@]}" down >>"$LOG" 2>&1 || true
  step "Restoring the old code and its migration files"
  quiet git reset --hard "$(state PREVIOUS)"
  [[ -f "$BACKUPS/old-migration-files.tar.gz" ]] && tar -xzf "$BACKUPS/old-migration-files.tar.gz"
  if [[ -f "$BACKUPS/migration-history-before.csv" ]]; then
    db --command "delete from django_migrations where app in ($APPS)" \
       --command "\\copy django_migrations (app, name, applied) from '$BACKUPS/migration-history-before.csv' csv" \
      || say "WARNING: could not restore the migration history"
  fi
  sudo chown -R www-data:www-data core/media
  step "Starting the old services"
  sudo systemctl enable --now "${OLD_SERVICES[@]/%/.service}" >>"$LOG" 2>&1 || true
  sudo nginx -t >>"$LOG" 2>&1 && sudo systemctl reload nginx
  sleep 3
  say "https://$SITE_HOST/admin/login/ -> $(public_status /admin/login/)"
  sed -i 's/^STAGE=.*/STAGE=rolled-back/' "$STATE"
  step "Rolled back to systemd. The database backups are in $BACKUPS"
}

# --- main --------------------------------------------------------------------

SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
ARGS=("$@")
case "$SCRIPT" in
  "$ROOT"/*) echo "Run a copy from outside $ROOT (see the header of this script)." >&2; exit 1 ;;
esac
if ! mkdir -p "$BACKUPS" 2>/dev/null; then
  sudo mkdir -p "$BACKUPS"
  sudo chown "$(id -un)" "$BACKUPS"
fi
chmod 700 "$BACKUPS"
ensure_docker_access
say ""
say "##### $(date '+%F %T') switch-to-docker $*"
case "${1:-}" in
  prepare)  shift; prepare "$@" ;;
  cutover)  cutover ;;
  rollback) rollback ;;
  *) echo "usage: $0 prepare <branch> | cutover | rollback" >&2; exit 2 ;;
esac
