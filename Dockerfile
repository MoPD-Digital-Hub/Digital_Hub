# Digital Hub: one image for the web server (Daphne) and the Celery worker.
#
#   docker build -t digital-hub .
#
# Configuration comes from environment variables at run time (see .env.example);
# nothing secret is baked into the image.

# --- Dependencies ----------------------------------------------------------
FROM python:3.12-slim AS deps

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --root-user-action=ignore poetry==2.3.2 poetry-plugin-export==1.9.0

WORKDIR /build
COPY pyproject.toml poetry.lock ./
# Install exactly what poetry.lock pins, into a venv the runtime stage copies.
RUN poetry export --without-hashes --format requirements.txt --output requirements.txt \
 && python -m venv /venv \
 && /venv/bin/pip install --requirement requirements.txt

# --- Runtime ---------------------------------------------------------------
FROM python:3.12-slim

# Match the server user that owns the media and migrations folders mounted into
# the container (deploy/deploy.sh passes `id -u`), so uploads stay writable.
ARG APP_UID=1000

ENV PATH=/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=project.settings

RUN useradd --uid "$APP_UID" --create-home --shell /usr/sbin/nologin app

COPY --from=deps /venv /venv
WORKDIR /app/core
COPY --chown=app:app core/ ./

# Static files are collected into the image and served by WhiteNoise. DEBUG=True
# here only lets settings load without production secrets; it is not kept.
RUN DEBUG=True SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput \
 && mkdir -p media \
 && chown -R app:app staticfiles media

USER app
EXPOSE 8000

# A TCP check: an HTTP one would trip ALLOWED_HOSTS and the HTTPS redirect.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, socket; socket.create_connection(('127.0.0.1', int(os.getenv('WEB_PORT', '8000'))), 3)"

CMD ["sh", "-c", "exec daphne --bind 0.0.0.0 --port ${WEB_PORT:-8000} --proxy-headers project.asgi:application"]
