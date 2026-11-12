import os
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config
from dotenv import load_dotenv

from ai.config import validate_ai_config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv(os.path.join(BASE_DIR.parent, '.env'))


# Django 4.2.x + Python 3.14 compatibility:
# BaseContext.__copy__ in Django 4.2 uses copy(super()), which fails on 3.14.
from django.template.context import BaseContext  # noqa: E402


def _patched_base_context_copy(self):
    duplicate = self.__class__.__new__(self.__class__)
    duplicate.__dict__ = self.__dict__.copy()
    duplicate.dicts = self.dicts[:]
    return duplicate

BaseContext.__copy__ = _patched_base_context_copy
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='unsafe-development-secret-key')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)
APPEND_SLASH=False

validate_ai_config(DEBUG)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())

CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())
CORS_ALLOW_CREDENTIALS = config('CORS_ALLOW_CREDENTIALS', default=True, cast=bool)

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://data-hub.mopd.gov.et',
    cast=Csv()
)

if not DEBUG:
    if SECRET_KEY == 'unsafe-development-secret-key':
        raise ValueError("SECRET_KEY must be set in production")
    if not ALLOWED_HOSTS:
        raise ValueError("ALLOWED_HOSTS must be set in production")

# Application definition

INSTALLED_APPS = [
    "daphne",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'rest_framework_simplejwt',
    'ckeditor',
    'users',
    'corsheaders',
    'ai',
    'mobile',
    'notifications',
    'chat',
    'dashboard',
    'preferences',
    'axes',
    'drf_user_activity_tracker',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Serves collected static files from the app itself (in Docker there is no shared disk with nginx).
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'project.middleware.request_id_middleware.RequestIDMiddleware',
    'project.middleware.api_envelope_middleware.ApiEnvelopeMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'axes.middleware.AxesMiddleware',
    'project.middleware.activity_tracker_middleware.ActivityTrackerMiddleware',
    'project.middleware.not_found_redirect_middleware.NotFoundRedirectMiddleware',
]


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'project.responses.exception_handler',
  
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Digital Hub API',
    'DESCRIPTION': 'OpenAPI documentation for the mobile time-series API surface.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'PREPROCESSING_HOOKS': [
        'project.schema.mobile_only_schema_endpoints',
    ],
    'SORT_OPERATIONS': 'project.schema.mobile_schema_sort_key',
    'TAGS': [
        {'name': 'Mobile Authentication', 'description': 'Authentication endpoints used by the mobile application.'},
        {'name': 'Time Series API', 'description': 'Time-series endpoints used by the mobile experience.'},
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=90),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,

    "ALGORITHM": "HS256",
    "VERIFYING_KEY": "",
    "AUDIENCE": None,
    "ISSUER": None,
    "JSON_ENCODER": None,
    "JWK_URL": None,
    "LEEWAY": 0,

    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",

    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",

    "JTI_CLAIM": "jti",

    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),

    "TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSerializer",
    "TOKEN_VERIFY_SERIALIZER": "rest_framework_simplejwt.serializers.TokenVerifySerializer",
    "TOKEN_BLACKLIST_SERIALIZER": "rest_framework_simplejwt.serializers.TokenBlacklistSerializer",
    "SLIDING_TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainSlidingSerializer",
    "SLIDING_TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSlidingSerializer",
}

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AXES_ENABLED = True
AXES_FAILURE_LIMIT = 7
AXES_COOLOFF_TIME = timedelta(hours=1)
AXES_LOG_LOCKOUT = True
AXES_RESET_ON_SUCCESS = True
AXES_FAILURES_PER_USERNAME_AND_IP_ADDRESS = True
AXES_USE_IPWARE = True
AXES_LOCK_OUT_AT_FAILURE = True


ROOT_URLCONF = 'project.urls'

# Keep dev startup logs clean. CKEditor 4 warning is known and tracked.
SILENCED_SYSTEM_CHECKS = ['ckeditor.W001']

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'project.wsgi.application'

AUTH_USER_MODEL = 'userManagement.CustomUser'
LOGIN_URL = '/dashboard/login/'
LOGIN_REDIRECT_URL = '/dashboard/'

DRF_ACTIVITY_TRACKER_DATABASE = True
DRF_ACTIVITY_TRACKER_SIGNAL = True
DRF_ACTIVITY_TRACKER_EXCLUDE_KEYS = ['password', 'token', 'access', 'refresh']
DRF_ACTIVITY_TRACKER_QUEUE_MAX_SIZE = 50
DRF_ACTIVITY_TRACKER_INTERVAL = 30


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases


testing_database = {
        'ENGINE': 'project.sqlite_immediate',
        'NAME': BASE_DIR / 'db.sqlite3',
        # SQLite allows one writer at a time; wait for the lock instead of
        # raising "database is locked" when concurrent requests write.
        'OPTIONS': {
            'timeout': 20,
        },
    }

server_database = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.getenv('DATABASE_NAME'),
    'USER': os.getenv('DATABASE_USER'),
    'PASSWORD': os.getenv('DATABASE_PASSWORD'),
    'HOST': os.getenv('DATABASE_HOST', '127.0.0.1'),
    'PORT': os.getenv('DATABASE_PORT', '5432'),
    'CONN_MAX_AGE': 300,
    'CONN_HEALTH_CHECKS': True,
}

USE_SQLITE = config('USE_SQLITE', default=DEBUG, cast=bool)

DATABASES = {
    'default': testing_database if USE_SQLITE else server_database
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'mobile.validators.StrongPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_DIR = os.path.join(BASE_DIR, "static")
STATICFILES_DIRS = [STATIC_DIR] if os.path.isdir(STATIC_DIR) else []

MEDIA_ROOT=os.path.join(BASE_DIR,"media/")
MEDIA_URL='/media/'

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Compressed copies for WhiteNoise. Not the manifest variant: templates bust
# caches with ?v= already, and a manifest fails collectstatic on any CSS url()
# that points at a missing file.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=not DEBUG, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=not DEBUG, cast=bool)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000 if not DEBUG else 0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS',
    default=not DEBUG,
    cast=bool,
)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=not DEBUG, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = config('SECURE_CONTENT_TYPE_NOSNIFF', default=True, cast=bool)
SECURE_REFERRER_POLICY = config('SECURE_REFERRER_POLICY', default='same-origin')
X_FRAME_OPTIONS = config('X_FRAME_OPTIONS', default='DENY')

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
        "json": {
            "()": "project.logging_utils.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain" if DEBUG else "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "ai": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

AI_USE_ASYNC_QUEUE = config("AI_USE_ASYNC_QUEUE", default=False, cast=bool)
AI_WS_MAX_CONCURRENCY = config("AI_WS_MAX_CONCURRENCY", default=20, cast=int)
# Amharic answers may only use Ethiopic, Latin and punctuation (ai/engine/amharic.py).
AI_AMHARIC_CONSTRAINED = config("AI_AMHARIC_CONSTRAINED", default=True, cast=bool)

# Admas AI's web search for general questions, through the self-hosted SearXNG
# (core/integrations/websearch). Off when SEARXNG_URL is empty.
SEARXNG_URL = config("SEARXNG_URL", default="")
WEB_SEARCH_ENABLED = config("WEB_SEARCH_ENABLED", default=True, cast=bool)
# Web-searched answers per user per day; 0 means no limit.
WEB_SEARCH_DAILY_LIMIT = config("WEB_SEARCH_DAILY_LIMIT", default=50, cast=int)

# Documents Admas AI makes on request (core/ai/documents): kept this many days,
# at most this many per user per day (0 = no limit).
AI_DOCUMENT_DAYS = config("AI_DOCUMENT_DAYS", default=7, cast=int)
AI_DOCUMENTS_DAILY_LIMIT = config("AI_DOCUMENTS_DAILY_LIMIT", default=10, cast=int)
# The site's public address, for links sent to the mobile app (empty: links are relative).
SITE_URL = config("SITE_URL", default="").rstrip("/")
AI_TTS_CACHE_TIMEOUT = config("AI_TTS_CACHE_TIMEOUT", default=3600, cast=int)
AI_TRANSLATION_CACHE_TIMEOUT = config("AI_TRANSLATION_CACHE_TIMEOUT", default=3600, cast=int)

# Email settings
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
)

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = os.getenv("EMAIL")
SERVER_EMAIL = os.getenv("EMAIL")


ASGI_APPLICATION = "project.asgi.application"

# DPMES2 organization-performance API (key issued to the Digital Hub)
DPMES2_API_BASE = config('DPMES2_API_BASE', default='https://dpmes.mopd.gov.et')
DPMES2_API_KEY = config('DPMES2_API_KEY', default='')

REDIS_HOST = config('REDIS_HOST', default='127.0.0.1')
REDIS_PORT = config('REDIS_PORT', default=6379, cast=int)
USE_REDIS_CHANNELS = config('USE_REDIS_CHANNELS', default=not DEBUG, cast=bool)
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default=f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default=f"redis://{REDIS_HOST}:{REDIS_PORT}/1")
# Run by the `beat` service (celery beat); exactly one beat process may run.
CELERY_BEAT_SCHEDULE = {
    "send-due-notifications": {
        "task": "notifications.tasks.send_due_notifications",
        "schedule": 60.0,
    },
    "delete-expired-ai-documents": {
        "task": "ai.tasks.delete_expired_documents",
        "schedule": 3600.0,
    },
}

if USE_REDIS_CHANNELS:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [(REDIS_HOST, REDIS_PORT)],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
