# Digital Hub

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![Django Version](https://img.shields.io/badge/django-4.2.6-blue)

## 📖 Overview

**Digital Hub** is a Django-based project designed to provide a flexible and scalable foundation for building modern web applications. It leverages Django Rest Framework for API development and includes Admas AI, a data assistant that answers in English and Amharic from the live time-series and DPMES data.

## 🚀 Features

- 🔗 **API Development** with Django Rest Framework.
- 🔐 **JWT Authentication** using SimpleJWT.
- 🌐 **CORS Support** for cross-origin requests.
- 🧠 **Admas AI**: answers questions about indicators, ministries, policy areas and goals with tables and charts (see [docs/ai.md](docs/ai.md)).
- 📊 **Environment Management** using python-dotenv.

## 📂 Project Structure

```bash
Digital_Hub/
├── core/                  # Django project (manage.py)
│   ├── project/           # settings, urls, ASGI, Celery
│   ├── ai/  users/  dashboard/  mobile/  chat/  notifications/
│   ├── integrations/      # external APIs (DPMES)
│   ├── templates/  static/
├── deploy/                # production compose file, deploy script, nginx site
├── secrets/               # key files, git-ignored (docs/deploy.md)
├── docs/                  # ai.md, deploy.md, …
├── Dockerfile  compose.yaml  .env.example
└── pyproject.toml  poetry.lock
```

## ⚙️ Running it

The project runs in Docker; the only thing to install is
[Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine with the Compose plugin).

```bash
make env            # creates .env from .env.example: set DEBUG=True and fill in the keys you have
make up             # PostgreSQL, Redis, web and Celery worker on http://localhost:8000
make superuser      # an admin login
make sync-catalog   # once, so the AI can answer data questions
```

Code in `core/` is mounted into the container, so edits reload without a rebuild. Run `make` to list
every command; the common ones:

| Command | Does |
|---|---|
| `make logs` | Follow web and worker logs (`s=db` for another service) |
| `make test` | Run the tests (`app=AI` for one app) |
| `make check` | Django checks and missing-migration check |
| `make shell` / `make dbshell` | Django shell / psql |
| `make manage cmd="..."` | Any `manage.py` command |
| `make ask-ai q="..."` | Ask the AI one question and see its trace |
| `make stop` / `make down` | Stop / remove the containers (the database is kept) |

Every setting is listed in [.env.example](.env.example).

## AI Configuration

Admas AI uses the Ministry LLM gateway (OpenAI-compatible) for chat and embeddings. Set in `.env`
(see `.env.example`):

- `VLLM_API_BASE`, `VLLM_MODEL`, `VLLM_API_KEY` for the chat model
- `EMBEDDING_API_BASE`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY` for embeddings
- `DPMES2_API_BASE`, `DPMES2_API_KEY` for ministry and policy-area performance
- `TIME_SERIES_API_BASE` for indicator values
- `GEMINI_API_KEY` only for the chat's translate button and read-aloud

After the first deploy, and then daily, build the catalog of indicators and organizations:

```bash
python core/manage.py sync_ai_catalog
```

How answers are made, the client protocol and the other commands are in [docs/ai.md](docs/ai.md).

## API

Every JSON endpoint returns `{"result", "message", "request_id", "data"}` (plus `error` on failure),
while keeping every field the installed mobile app already reads. See [docs/api.md](docs/api.md).

## Deployment

Production runs the same image with Docker. Pushing to the `production` branch deploys it
(`.github/workflows/production.yml` → `deploy/deploy.sh`). Setup, the one-time switch from systemd, rollback
and everyday commands: [docs/deploy.md](docs/deploy.md).

## 📦 Dependencies

Listed in [pyproject.toml](pyproject.toml) and pinned in `poetry.lock`.

## 🧑‍💻 Authors

- **Mikiyas Degefu**  
  📧 [mikiyas.m.degefu@gmail.com](mailto:mikiyas.m.degefu@gmail.com)

- **Kaleab Hegie**  
  📧 [benjiyg400@gmail.com](mailto:benjiyg400@gmail.com)
