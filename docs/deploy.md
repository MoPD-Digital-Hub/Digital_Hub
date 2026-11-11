# Running and deploying the Digital Hub with Docker

One image (`Dockerfile`) runs all three processes:

| Process | Command | Does |
|---|---|---|
| `web` | Daphne (ASGI) | Pages, REST API, WebSockets (AI chat, messaging), static files (WhiteNoise) |
| `worker` | Celery, queues `celery` and `ai_queue` | Emails, push notifications, queued AI answers |
| `beat` | Celery beat | Starts the periodic tasks; today: sending scheduled notifications, every minute. Exactly one may run. |

Configuration is environment variables only: `.env` in the repository root, documented in `.env.example`.
The image contains no secrets or uploaded media.

## Local development

```bash
cp .env.example .env          # set DEBUG=True and fill in the keys you have
docker compose up --build     # http://localhost:8000
```

`compose.yaml` runs PostgreSQL, Redis, web, worker and beat. `./core` is mounted, so code edits reload without a
rebuild. The `Makefile` wraps the usual commands (`make` lists them: `make up`, `make test`, `make logs`,
`make sync-catalog`, …); underneath they are:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py sync_ai_catalog     # needed once for the AI to answer data questions
docker compose exec web python manage.py test
docker compose logs -f web worker beat
docker compose down            # add -v to also delete the local database
```

## Production

The server keeps its PostgreSQL, Redis and nginx (with the TLS certificate). Only Daphne and Celery move into
containers, using the host network, so `DATABASE_HOST=127.0.0.1` and `REDIS_HOST=127.0.0.1` in the server's
`.env` keep working. Files:

| File | Purpose |
|---|---|
| `deploy/compose.production.yaml` | `web` (Daphne on `127.0.0.1:8000`), `worker` and `beat`, restart automatically |
| `deploy/deploy.sh` | Pull, build, migrate, restart, wait for health, keep the last 5 images |
| `deploy/nginx/data-hub.conf` | nginx site: TLS, `/media/` from disk, everything else to `127.0.0.1:8000` |
| `.github/workflows/ci.yml` | Lint and tests on every push and pull request |
| `.github/workflows/production.yml` | On push to `production`: run `ci.yml`; if it passes, SSH in, update the checkout, run `deploy.sh` |

Mounted from the server into the containers: `core/media/` (uploads) and `secrets/` (key files, read-only).
Migrations are committed and built into the image; `deploy.sh` applies them.

## Secrets

Key files are never committed or built into the image. They live in `secrets/` at the repository root
(git-ignored) and are mounted read-only:

| File | Used for |
|---|---|
| `secrets/firebase-service-account.json` | Push notifications (or set `FIREBASE_CREDENTIALS` to another path) |

Both service-account keys were committed in earlier history, so rotate them: create new keys in the
Firebase/Google Cloud console, put the new Firebase key in `secrets/`, then delete the old keys there.

## Migrations

Migrations are committed like code. After changing a model, run `make migrations`, review the new file and
commit it. Do not generate migrations on a server.

Databases created before this change have a migration history from files that were generated per machine.
`manage.py adopt_migrations` switches such a database to the committed files: it checks that every table and
column of the baseline schema (the first committed migrations) exists, then rewrites the history to that
baseline only; no table is changed. Migrations added since then are applied by the normal `migrate` that
follows. `deploy.sh` refuses to migrate until the adoption has been done.

### One-time switch from systemd to Docker

Run on the server as the user that owns `/mnt/data/Digital_Hub` (`mopd`). Do step 1 **before** the new code
reaches the server, because updating the checkout removes the key file from `core/`.

1. Keep the Firebase key outside git:
   ```bash
   cd /mnt/data/Digital_Hub && mkdir -p secrets && cp core/Notification/push_notification/admas-9e2c7-9bcdd20b9461.json secrets/firebase-service-account.json && chmod 600 secrets/*.json
   ```
   (If it is already gone: `git show d838978:core/Notification/push_notification/admas-9e2c7-9bcdd20b9461.json > secrets/firebase-service-account.json`.)
2. Back up the database:
   ```bash
   cd /mnt/data/Digital_Hub && set -a && . ./.env && set +a && PGPASSWORD="$DATABASE_PASSWORD" pg_dump -h "${DATABASE_HOST:-127.0.0.1}" -U "$DATABASE_USER" -Fc "$DATABASE_NAME" > ~/digital-hub-$(date +%F).dump && ls -lh ~/digital-hub-*.dump
   ```
3. Let the user run Docker, then log out and back in:
   ```bash
   sudo usermod -aG docker "$USER"
   ```
4. Update the checkout and build the image:
   ```bash
   cd /mnt/data/Digital_Hub && git fetch origin production && git reset --hard origin/production && docker compose -f deploy/compose.production.yaml build
   ```
5. Adopt the committed migrations (reports first; `--apply` only rewrites the history):
   ```bash
   docker compose -f deploy/compose.production.yaml run --rm --no-deps web python manage.py adopt_migrations
   ```
   ```bash
   docker compose -f deploy/compose.production.yaml run --rm --no-deps web python manage.py adopt_migrations --apply
   ```
6. Deploy. The site keeps running on the old systemd Daphne meanwhile:
   ```bash
   bash deploy/deploy.sh --no-pull
   ```
7. Point nginx at the container: in the site file, replace the `domains.sock` upstream with
   `server 127.0.0.1:8000;` (see `deploy/nginx/data-hub.conf`, keep your certificate lines), then:
   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```
8. Stop the old services so they don't start again on boot:
   ```bash
   sudo systemctl disable --now daphne.service celery.service uwsgi.service
   ```
9. Schedule the daily AI catalog refresh (`crontab -e`):
   ```
   15 2 * * * cd /mnt/data/Digital_Hub && docker compose -f deploy/compose.production.yaml run --rm --no-deps web python manage.py sync_ai_catalog >> /tmp/ai-catalog.log 2>&1
   ```
10. Remove the folders left from the old layout (only old generated files remain in them):
    ```bash
    cd /mnt/data/Digital_Hub/core && rm -rf AI Notification userManagement Videos ../google-env
    ```

To undo the switch: `docker compose -f deploy/compose.production.yaml down`, put the `domains.sock` upstream
back, `sudo systemctl enable --now daphne.service celery.service`, reload nginx.

### Everyday operations

On the server the same `Makefile` has `prod-` targets: `make prod-deploy`, `make prod-rollback`,
`make prod-logs`, `make prod-ps`, `make prod-shell`, `make prod-sync-catalog`. Underneath:

```bash
cd /mnt/data/Digital_Hub
bash deploy/deploy.sh                       # deploy origin/production (also what a push does)
bash deploy/deploy.sh --rollback            # back to the previous image, no migrations
docker compose -f deploy/compose.production.yaml ps
docker compose -f deploy/compose.production.yaml logs -f --tail 100 web
docker compose -f deploy/compose.production.yaml exec web python manage.py shell
```

After editing `.env`, run `docker compose -f deploy/compose.production.yaml up -d` to restart with the new
values (a plain `restart` does not reload `.env`).

## Dependencies

`pyproject.toml` lists what the code imports; `poetry.lock` pins everything, and the image installs exactly
that. Neither Python nor Poetry is needed on a developer machine. To change a dependency, edit
`pyproject.toml`, then regenerate the lock in a container that sees only those two files (mounting the whole
repository would let Poetry create a `.venv` in it), and rebuild with `docker compose up --build`:

```bash
docker run --rm -v "$PWD/pyproject.toml:/src/pyproject.toml" -v "$PWD/poetry.lock:/src/poetry.lock" -w /src \
  python:3.12-slim sh -c "pip install -q poetry==2.3.2 && poetry lock"
```
