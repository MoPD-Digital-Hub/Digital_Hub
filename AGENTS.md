# Digital Hub Agent Notes

## Purpose
- Django 4.2 backend for the Digital Hub platform.
- Combines REST APIs, a server-rendered dashboard, mobile content endpoints, notifications, chat, and an AI assistant branded as Admas AI.
- Main code lives in `core/`. Repo root mainly holds env/config/docs.

## Stack
- Python `>=3.10,<3.15`
- Django `4.2.6`
- Django REST Framework + SimpleJWT
- Channels + Daphne for WebSockets
- Celery for async jobs (worker) and periodic ones (beat, `CELERY_BEAT_SCHEDULE` in settings)
- Admas AI on the Ministry LLM gateway (OpenAI-compatible chat + embeddings); Gemini only for translate and read-aloud
- Postgres in non-dev environments, SQLite in local/dev when `USE_SQLITE=True`

## Layout
- `core/project/`: Django project config, ASGI/WSGI, Celery, middleware.
- `core/ai/` (app label `AI`): Admas AI: the answer pipeline (`engine/`), chat WebSockets, REST endpoints, translate and TTS.
- `core/users/` (app label `userManagement`): custom user model, email + password sign-in, password reset, JWT refresh.
- `core/dashboard/`: server-rendered dashboard pages and account pages.
- `core/mobile/`: mobile app content (apps, settings, FAQ, contact) and app version checks.
- `core/notifications/` (app label `Notification`): notification models, API, Firebase push tasks.
- `core/chat/`: user-to-user messaging (REST + WebSockets).
- `core/integrations/`: one package per external service, each with `client.py` (the calls), `views.py` + `urls.py` (the `/api/mobile/` endpoints that serve its data).
- `core/integrations/dpmes/`: DPMES client, response mapping (`compat.py`), and the scorecard endpoints the website uses.
- `core/integrations/time_series/`: time-series service client (address from `TIME_SERIES_API_BASE`), the pass-through endpoints for the app and website, and their OpenAPI docs.
- Every app: REST views in `api/views.py`, serializers in `api/serializers.py`, Celery tasks in `tasks.py`, routes in `urls.py`.
- API responses: build them with `project.responses.success()` / `failure()` (docs/api.md). Every `/api/` JSON response is completed to the standard shape by middleware; it must stay backward compatible with the installed mobile app (add fields, never rename, retype or remove).
- App labels keep the old names so tables, migrations and admin URLs are unchanged; import by package name (`ai`, `users`, `notifications`).
- Migrations are committed. After a model change: `make migrations`, review, commit. Never generate migrations on a server. `users/management/commands/adopt_migrations.py` lists the baseline migrations old databases are switched to; never add later migrations to that list.
- Key files live in `secrets/` (git-ignored), never in the repository.

## Entry Points
- Django management: `docker compose exec web python manage.py <command>`
- Dev server: `docker compose up --build` (http://localhost:8000)
- ASGI app: `core/project/asgi.py`
- URL root: `core/project/urls.py`
- AI HTTP routes: `/api/ai-chat/`
- AI WebSocket routes: `/ws/chat/<room_name>/` (app), `/ws/chat-web/<room_name>/` (web)

## Runtime Notes
- `.env` is loaded from the repo root, not from `core/`.
- `core/project/settings.py` validates the LLM gateway URLs at startup (`ai/config.py`).
- There is an explicit monkey patch for Django 4.2 template context copying on Python 3.14.
- `AUTH_USER_MODEL` is `userManagement.CustomUser`, with email as the login field.
- Auth: session auth (website, admin), then JWT (mobile app). No SSO/OIDC.
- `APPEND_SLASH=False`, so route strings matter.

## AI Architecture
- Full description: `docs/ai.md`.
- `core/ai/engine/pipeline.py`: plan (one model call, JSON schema) → resolve names against the entity catalog → fetch with typed tools (time-series and DPMES APIs) → compose (streamed) → render tables/charts in code → check numbers.
- `core/ai/engine/compat.py`: the message format the mobile app and web chat expect on `/ws/chat/` and `/api/ai-chat/answer/`.
- `core/ai/consumers.py`: chat and TTS WebSocket consumers. `core/ai/api/views.py`: REST endpoints.
- Chat persistence uses `ChatInstance` and `QuestionHistory`; every answer also writes an `AnswerTrace`.
- The catalog (`CatalogEntity`) is built by `manage.py sync_ai_catalog` (run in the web container); there is no vector database.
- Language follows the question's script: Amharic script gets an Amharic answer, otherwise English.

## Auth And User Flow
- Sign-in is email + password: `POST /api/user/auth/password-login/` returns the user and JWT refresh/access tokens. There is no sign-in OTP.
- `POST /api/auth/token/refresh/` renews the access token.
- Password reset is under `/api/user/reset-password/`: POST emails a random 6-digit code valid for 20 minutes; PUT sets the new password with it. Five wrong codes cancel the code.
- `django-axes` is enabled for lockout/rate limiting.

## Other App Responsibilities
- `mobile`: app metadata, FAQ/settings/contact info, app version enforcement.
- `integrations/time_series`: indicator data passed through from the time-series service; also used by the AI (catalog sync, indicator values).
- `notifications`: categories + notifications. A notification is pushed to all devices once (`sent_at` records it): on save when it is active and due, otherwise by the `beat` service, which runs `send_due_notifications` every minute for scheduled ones (`send_at`). Later edits do not push again.
- `integrations/dpmes`: DPMES scorecards for the website (the browser cannot call DPMES directly: it needs the API key and sends no CORS headers).
- `dashboard`: HTML pages for dashboard, stats, SDG pages, profile/password pages, Admas AI page, and the app's public privacy policy.

## Important Environment Variables
- Core:
- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `USE_SQLITE`
- Database:
- `DATABASE_NAME`
- `DATABASE_USER`
- `DATABASE_PASSWORD`
- `DATABASE_HOST`
- `DATABASE_PORT`
- Channels / async:
- `REDIS_HOST`
- `REDIS_PORT`
- AI:
- `VLLM_API_BASE`, `VLLM_MODEL`, `VLLM_API_KEY`
- `EMBEDDING_API_BASE`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY`
- `DPMES2_API_BASE`, `DPMES2_API_KEY`
- `TIME_SERIES_API_BASE`
- `GEMINI_API_KEY` (translate and read-aloud only)

## Safe Working Conventions
- Start by checking `git status --short` because this repo often has ongoing local edits.
- Read `core/project/settings.py`, `core/project/urls.py`, and the relevant app `urls.py` before changing behavior.
- For AI work, read `docs/ai.md`, then `core/ai/engine/pipeline.py` and `core/ai/consumers.py`.
- For auth work, inspect `core/users/api/views.py` (sign-in, password reset, token refresh) and `core/users/models.py`.
- For mobile/data APIs, inspect `core/mobile/api/` and `core/integrations/`.
- For dashboard UI changes, inspect `core/dashboard/views.py` plus templates/static assets.

## Tests
- Every package has a `tests.py`: `ai`, `users`, `chat`, `notifications`, `mobile`, `dashboard`, `project` (API response shape), `integrations/dpmes`, `integrations/time_series`.
- Tests never call the real services: patch the LLM gateway, DPMES, time-series and Firebase. Saving a `Notification` queues a push to every device, so tests that create one must patch `notifications.models.send_to_all` (see `notifications/tests.py`).
- Before finishing a change: `make ci` (lint + Django checks + missing-migration check + tests). GitHub runs the same on every push (`.github/workflows/ci.yml`), and a push to `production` deploys only if it passes.
- Lint rules are in `ruff.toml`; `make lint fix=1` applies the safe fixes.

## Common Commands
- Everything goes through `make` (run `make` to list targets): `make up`, `make test`, `make logs`, `make prod-deploy`; see `docs/deploy.md`
- Lint, checks and tests together: `make ci`
- Deploy: push to `production`, or on the server `bash deploy/deploy.sh`

## First Read For Future Sessions
- `README.md`
- `core/project/settings.py`
- `core/project/urls.py`
- `core/ai/README.md`
- `docs/ai.md`
- `core/users/api/views.py`

