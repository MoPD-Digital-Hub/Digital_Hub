import os
import warnings
import logging
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
from decouple import Csv, config
from AI.runtime.config import validate_ai_config
# import logging
# import logging.handlers


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = os.path.join(BASE_DIR.parent, 'logs')


load_dotenv(os.path.join(BASE_DIR.parent, '.env'))

# Python 3.14 emits this warning from langchain_core internals; suppress in app logs.
warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.",
    category=UserWarning,
)

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
    'rest_framework_simplejwt',
    'ckeditor',
    'userManagement',
    'corsheaders',
    'Videos',
    'AI',
    'mobile',
    'Notification',
    'dashboard',
    'axes',
    'drf_user_activity_tracker',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'project.middleware.request_id_middleware.RequestIDMiddleware',
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
        'userManagement.drf_authentication.OptionalOIDCAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    )
  
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

    "TOKEN_OBTAIN_SERIALIZER":  "userManagement.serializers.MyTokenObtainPairSerializer",
    "TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSerializer",
    "TOKEN_VERIFY_SERIALIZER": "rest_framework_simplejwt.serializers.TokenVerifySerializer",
    "TOKEN_BLACKLIST_SERIALIZER": "rest_framework_simplejwt.serializers.TokenBlacklistSerializer",
    "SLIDING_TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainSlidingSerializer",
    "SLIDING_TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSlidingSerializer",
}

AUTHENTICATION_BACKENDS = [
    'userManagement.auth_backends.CustomOIDCAuthenticationBackend',
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Keycloak Configuration
OIDC_RP_CLIENT_ID = config('OIDC_RP_CLIENT_ID', default='')
OIDC_RP_CLIENT_SECRET = config('OIDC_RP_CLIENT_SECRET', default='')
OIDC_OP_AUTHORIZATION_ENDPOINT = config('OIDC_OP_AUTHORIZATION_ENDPOINT', default='')
OIDC_OP_TOKEN_ENDPOINT = config('OIDC_OP_TOKEN_ENDPOINT', default='')
OIDC_OP_USER_ENDPOINT = config('OIDC_OP_USER_ENDPOINT', default='')
OIDC_OP_JWKS_ENDPOINT = config('OIDC_OP_JWKS_ENDPOINT', default='')
OIDC_OP_LOGOUT_ENDPOINT = config('OIDC_OP_LOGOUT_ENDPOINT', default='')
OIDC_POST_LOGOUT_REDIRECT_URI = config('OIDC_POST_LOGOUT_REDIRECT_URI', default='')
OIDC_RP_SIGN_ALGO = config('OIDC_RP_SIGN_ALGO', default='RS256')
OIDC_STORE_ID_TOKEN = config('OIDC_STORE_ID_TOKEN', default=True, cast=bool)
OIDC_CALLBACK_CLASS = config(
    'OIDC_CALLBACK_CLASS',
    default='userManagement.oidc_views.CustomOIDCAuthenticationCallbackView'
)
OIDC_DRF_AUTH_BACKEND = "userManagement.auth_backends.CustomOIDCAuthenticationBackend"

# Optional: Automatically create a Django user if they don't exist
OIDC_CREATE_USER = config('OIDC_CREATE_USER', default=False, cast=bool)

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
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
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
        "AI": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

AI_USE_ASYNC_QUEUE = config("AI_USE_ASYNC_QUEUE", default=False, cast=bool)
AI_WS_MAX_CONCURRENCY = config("AI_WS_MAX_CONCURRENCY", default=20, cast=int)
AI_MAX_RETRIEVAL_DOCS = config("AI_MAX_RETRIEVAL_DOCS", default=4, cast=int)
AI_TTS_CACHE_TIMEOUT = config("AI_TTS_CACHE_TIMEOUT", default=3600, cast=int)
AI_TRANSLATION_CACHE_TIMEOUT = config("AI_TRANSLATION_CACHE_TIMEOUT", default=3600, cast=int)

# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,

#     'formatters': {
#         'uwsgi_style': {
#             'format': '[{asctime}] {levelname} {name}: {message}',
#             'style': '{',
#         },
#     },

#     'handlers': {
#         'daphne_file': {
#             'level': 'DEBUG',
#             'class': 'logging.FileHandler',
#             'filename': '/mnt/data/Digital_Hub/core/daphne.log',
#             'formatter': 'uwsgi_style',
#         },
#     },

#     'loggers': {
#         # Django core
#         'django': {
#             'handlers': ['daphne_file'],
#             'level': 'DEBUG',
#             'propagate': True,
#         },

#         # Django requests
#         'django.request': {
#             'handlers': ['daphne_file'],
#             'level': 'DEBUG',
#             'propagate': False,
#         },

#         # Channels
#         'channels': {
#             'handlers': ['daphne_file'],
#             'level': 'DEBUG',
#             'propagate': True,
#         },

#         # Daphne server
#         'daphne': {
#             'handlers': ['daphne_file'],
#             'level': 'DEBUG',
#             'propagate': True,
#         },

#         # Your project apps
#         'project': {   # 🔴 replace with your real project name
#             'handlers': ['daphne_file'],
#             'level': 'DEBUG',
#             'propagate': True,
#         },
#     },
# }


# Email settings
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = os.getenv('EMAIL')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL = os.getenv('EMAIL')


ASGI_APPLICATION = "project.asgi.application"

REDIS_HOST = config('REDIS_HOST', default='127.0.0.1')
REDIS_PORT = config('REDIS_PORT', default=6379, cast=int)
USE_REDIS_CHANNELS = config('USE_REDIS_CHANNELS', default=not DEBUG, cast=bool)
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default=f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default=f"redis://{REDIS_HOST}:{REDIS_PORT}/1")

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
