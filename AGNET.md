# Digital Hub Agent Notes

## Purpose
- Django 4.2 backend for the Digital Hub platform.
- Combines REST APIs, a server-rendered dashboard, mobile content endpoints, notifications, videos, and an AI assistant branded as Admas AI.
- Main code lives in `core/`. Repo root mainly holds env/config/docs.

## Stack
- Python `>=3.10,<3.15`
- Django `4.2.6`
- Django REST Framework + SimpleJWT
- Channels + Daphne for WebSockets
- Celery for async jobs
- Gemini-based AI orchestration with Milvus retrieval
- Postgres in non-dev environments, SQLite in local/dev when `USE_SQLITE=True`

## Layout
- `core/project/`: Django project config, ASGI/WSGI, Celery, middleware.
- `core/AI/`: Admas AI chat, orchestration, Gemini client/service, Milvus retrieval, WebSocket consumer.
- `core/userManagement/`: custom user model, OTP login flow, password reset, OIDC integration, JWT refresh.
- `core/dashboard/`: server-rendered dashboard pages and account pages.
- `core/mobile/`: mobile app content APIs, time-series APIs, DPMES APIs, app version checks.
- `core/Videos/`: video list/comments/likes API.
- `core/Notification/`: notification models, API, Firebase push task integration.

## Entry Points
- Django management: `python core/manage.py <command>`
- Dev server: `poetry run python core/manage.py runserver`
- ASGI app: `core/project/asgi.py`
- URL root: `core/project/urls.py`
- AI HTTP routes: `/api/ai-chat/`
- AI WebSocket route: `/ws/chat/<room_name>/`

## Runtime Notes
- `.env` is loaded from the repo root, not from `core/`.
- `core/project/settings.py` validates Gemini, retrieval, and orchestration settings at startup.
- There is an explicit monkey patch for Django 4.2 template context copying on Python 3.14.
- `AUTH_USER_MODEL` is `userManagement.CustomUser`, with email as the login field.
- Default auth stack is session auth, optional OIDC auth, then JWT auth.
- `APPEND_SLASH=False`, so route strings matter.

## AI Architecture
- Current AI code is centered on:
- `core/AI/api.py`: REST endpoints for chat instances, history, health, and answers.
- `core/AI/consumers.py`: WebSocket streaming chat consumer.
- `core/AI/orchestration/service.py`: main router choosing text generation, time-series query, or dashboard generation.
- `core/AI/gemini/`: language detection, prompting, Gemini REST client, generation service.
- `core/AI/retrieval/`: Milvus retrieval, embeddings client, indicator/time-series enrichment.
- `core/AI/query_preprocessing.py`: preprocessing shared by classifier/orchestration.
- Chat persistence uses `ChatInstance` and `QuestionHistory`.
- Titles auto-update from the first real user question when the chat still has a generic title.

## AI Behavior
- Language is chosen from the user prompt script dominance:
- Amharic script => Amharic response.
- Latin script => English response.
- Main intents:
- `text_generation`
- `time_series_query`
- `dashboard_generation`
- Retrieval-first generation is the default for grounded answers.
- Dashboard generation calls an external dashboard creation API.
- Time-series enrichment may add charts and source metadata.

## Auth And User Flow
- Login is OTP-based:
- `POST /api/user/auth/login/` checks credentials and issues an OTP.
- `POST /api/user/auth/verify-otp/` validates OTP and returns JWT refresh/access tokens.
- Password reset is under `/api/user/reset-password/`.
- There is optional OIDC wiring through `mozilla-django-oidc`.
- `django-axes` is enabled for lockout/rate limiting.

## Other App Responsibilities
- `mobile`: app metadata, FAQ/settings/contact info, app version enforcement, time-series and DPMES APIs.
- `Videos`: videos, comments, likes, comment likes.
- `Notification`: categories + notifications, sends Firebase push via Celery on save when eligible.
- `dashboard`: HTML pages for dashboard, stats, SDG pages, profile/password pages, Admas AI page.

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
- OIDC:
- `OIDC_RP_CLIENT_ID`
- `OIDC_RP_CLIENT_SECRET`
- `OIDC_OP_*`
- AI:
- `GEMINI_API_KEY`
- `GEMINI_TEXT_MODEL`
- `GEMINI_TIMEOUT_SECONDS`
- `GEMINI_TEMPERATURE`
- `GEMINI_TOP_P`
- `GEMINI_MAX_OUTPUT_TOKENS`
- `GEMINI_HISTORY_TURNS`
- `GEMINI_STREAM_CHUNK_CHARS`
- `MAX_HISTORY_QUESTIONS`
- `MILVUS_URI`
- `MILVUS_COLLECTION_NAME`
- `MILVUS_RETRIEVAL_K`
- `MILVUS_RETRIEVAL_FETCH_K`
- `MILVUS_TIMEOUT_SECONDS`
- `EMBEDDING_API_BASE`
- `EMBEDDING_MODEL`
- `EMBEDDING_API_KEY`
- `TIME_SERIES_API_BASE`
- `TIME_SERIES_INDICATOR_LIMIT`
- `DASHBOARD_CREATE_API_URL`
- `DASHBOARD_TIMEOUT_SECONDS`

## Current Repo State
- The git worktree is already dirty.
- There is an active AI refactor in progress:
- old modules like `application/`, `endpoints/`, `infrastructure/`, `tools/`, `shared/`, `tasks.py`, `signals.py`, `mcp_tools.py`, and parsing-related files are being removed or superseded.
- new modules like `core/AI/api.py`, `core/AI/serializers.py`, `core/AI/responses.py`, `core/AI/gemini/`, `core/AI/orchestration/`, and `core/AI/retrieval/` are being added.
- Do not assume the old AI layout is authoritative.
- Do not revert unrelated in-flight AI changes unless explicitly asked.

## Safe Working Conventions
- Start by checking `git status --short` because this repo often has ongoing local edits.
- Read `core/project/settings.py`, `core/project/urls.py`, and the relevant app `urls.py` before changing behavior.
- For AI work, inspect `core/AI/api.py`, `core/AI/consumers.py`, and `core/AI/orchestration/service.py` first.
- For auth work, inspect `core/userManagement/views.py`, `core/userManagement/drf_authentication.py`, and `core/userManagement/auth_backends.py`.
- For mobile/data APIs, inspect `core/mobile/api/`.
- For dashboard UI changes, inspect `core/dashboard/views.py` plus templates/static assets.

## Tests
- Existing tests are concentrated in:
- `core/AI/tests.py`
- `core/userManagement/tests.py`
- Small placeholder test files also exist in other apps.
- Preferred verification:
- `poetry run python core/manage.py test AI userManagement`

## Common Commands
- Install deps: `poetry install`
- Run migrations: `poetry run python core/manage.py migrate`
- Run server: `poetry run python core/manage.py runserver`
- Run tests: `poetry run python core/manage.py test AI userManagement`

## First Read For Future Sessions
- `README.md`
- `core/project/settings.py`
- `core/project/urls.py`
- `core/AI/README.md`
- `core/AI/orchestration/service.py`
- `core/userManagement/views.py`

