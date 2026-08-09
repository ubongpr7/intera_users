
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

LOCAL_SERVER = os.getenv('LOCAL_SERVER', 'False')=='True'

BASE_DIR = Path(__file__).resolve().parent.parent


def _split_csv_env(var_name: str, default: list[str]) -> list[str]:
    value = os.getenv(var_name, "").strip()
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.getenv('SECRET_KEY')

if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set.")

DEBUG = os.getenv('DEBUG', 'False') == 'True'
DATABASE_CONN_MAX_AGE = int(os.getenv("DATABASE_CONN_MAX_AGE", "600"))
DATABASE_CONN_HEALTH_CHECKS = os.getenv("DATABASE_CONN_HEALTH_CHECKS", "True") == "True"
DATABASE_DISABLE_SERVER_SIDE_CURSORS = os.getenv("DATABASE_DISABLE_SERVER_SIDE_CURSORS", "True") == "True"
DATABASE_CONNECT_TIMEOUT = int(os.getenv("DATABASE_CONNECT_TIMEOUT", "10"))

# Logging
# Django's default logging config won't show `logger.info(...)` from our modules unless you
# define `LOGGING`. This ensures Kafka consumers/producers log to stdout (Docker logs).
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DJANGO_LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", LOG_LEVEL).upper()
KAFKA_LOG_LEVEL = os.getenv("KAFKA_LOG_LEVEL", LOG_LEVEL).upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": DJANGO_LOG_LEVEL,
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": DJANGO_LOG_LEVEL,
            "propagate": False,
        },
        "subapps.kafka": {
            "handlers": ["console"],
            "level": KAFKA_LOG_LEVEL,
            "propagate": False,
        },
    },
}

_default_allowed_hosts = [
    'localhost',
    '127.0.0.1',
    '10.0.2.2',
    'accounts.interaims.com',
    'dev.accounts.interaims.com',
    'host.docker.internal'
    
]
ALLOWED_HOSTS = _split_csv_env("ALLOWED_HOSTS", _default_allowed_hosts)
# ALLOWED_HOSTS = ['*']

# Application definition
DJ_DEFAULT_INSTALLED_APPS=[
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
THIRD_PARTY_APPS=[
    'django_extensions',
     "rest_framework",
    "rest_framework.authtoken",
    'corsheaders',
    'cities_light',
    'whitenoise.runserver_nostatic',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'oauth2_provider',
    'drf_yasg',
    'djoser',
    'social_django',
]

CORE_APPS = [
    'mainapps.accounts',
    'mainapps.common',
    'mainapps.kafka_reliability',
    'mainapps.profile',
    'mainapps.permit',
]

INSTALLED_APPS=DJ_DEFAULT_INSTALLED_APPS+THIRD_PARTY_APPS+CORE_APPS


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
   
]


ROOT_URLCONF = 'core.urls'
AUTH_USER_MODEL = 'accounts.User' 
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR/"templates"],
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

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=DATABASE_CONN_MAX_AGE,
        conn_health_checks=DATABASE_CONN_HEALTH_CHECKS,
    )
}

DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = DATABASE_DISABLE_SERVER_SIDE_CURSORS
if DATABASE_CONNECT_TIMEOUT > 0:
    DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = DATABASE_CONNECT_TIMEOUT

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  

STATICFILES_DIRS=[os.path.join(BASE_DIR,'static')]

MEDIA_URL = '/media/'
MEDIAFILES_DIRS=[os.path.join(BASE_DIR,'media')]
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django_smtp_ssl.SSLEmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "True") == "True"
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "False") == "True"
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD =os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_SUPPORT_EMAIL = os.getenv("EMAIL_SUPPORT_EMAIL", "support@interaims.com").strip()
EMAIL_NOREPLY_ADDRESS = os.getenv("EMAIL_NOREPLY_ADDRESS", "noreply@interaims.com").strip()
EMAIL_ACCOUNTS_ADDRESS = os.getenv("EMAIL_ACCOUNTS_ADDRESS", "intera-accounts@interaims.com").strip()
EMAIL_AGENT_ADDRESS = os.getenv("EMAIL_AGENT_ADDRESS", "intera-agent@interaims.com").strip()
EMAIL_SYSTEM_FROM_EMAIL = os.getenv("EMAIL_SYSTEM_FROM_EMAIL", f"Intera IMS <{EMAIL_NOREPLY_ADDRESS}>").strip()
EMAIL_ACCOUNTS_FROM_EMAIL = os.getenv("EMAIL_ACCOUNTS_FROM_EMAIL", f"Intera Accounts <{EMAIL_ACCOUNTS_ADDRESS}>").strip()
EMAIL_AGENT_FROM_EMAIL = os.getenv("EMAIL_AGENT_FROM_EMAIL", f"Intera Agent <{EMAIL_AGENT_ADDRESS}>").strip()
EMAIL_DEFAULT_REPLY_TO = os.getenv("EMAIL_DEFAULT_REPLY_TO", EMAIL_SUPPORT_EMAIL).strip()
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    EMAIL_SYSTEM_FROM_EMAIL,
).strip()
EMAIL_BRAND_LOGO_URL = os.getenv("EMAIL_BRAND_LOGO_URL", "").strip()
EMAIL_BRAND_LOGO_LIGHT_URL = os.getenv("EMAIL_BRAND_LOGO_LIGHT_URL", "").strip()
EMAIL_BRAND_LOGO_DARK_URL = os.getenv("EMAIL_BRAND_LOGO_DARK_URL", "").strip()
EMAIL_BRAND_STATIC_LOGO_PATH = "images/logos/INTERA-EMAIL-LOGO-DARK.png"
EMAIL_SHARED_STATIC_BUCKET = os.getenv("EMAIL_SHARED_STATIC_BUCKET", os.getenv("AWS_STORAGE_BUCKET_NAME", "")).strip()
EMAIL_SHARED_STATIC_LOCATION = os.getenv(
    "EMAIL_SHARED_STATIC_LOCATION",
    os.getenv("AWS_STATIC_LOCATION", "assessment/static"),
).strip("/")
COMPANY_INVITATION_EXPIRY_DAYS = int(os.getenv("COMPANY_INVITATION_EXPIRY_DAYS", "2"))
SITE_URL = os.getenv("SITE_URL", "").strip().rstrip("/")
FRONTEND_SITE_URL = os.getenv("FRONTEND_SITE_URL", SITE_URL).strip().rstrip("/")
COMPANY_INVITATION_ACCEPT_URL_TEMPLATE = os.getenv("COMPANY_INVITATION_ACCEPT_URL_TEMPLATE", "").strip()
_frontend_site = urlparse(FRONTEND_SITE_URL) if FRONTEND_SITE_URL else None
EMAIL_FRONTEND_PROTOCOL = (_frontend_site.scheme if _frontend_site and _frontend_site.scheme else "").strip() or None
EMAIL_FRONTEND_DOMAIN = (_frontend_site.netloc if _frontend_site and _frontend_site.netloc else "").strip() or None

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
    






AUTHENTICATION_BACKENDS = [
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.facebook.FacebookOAuth2',
    "djoser.auth_backends.LoginFieldBackend",

    'django.contrib.auth.backends.ModelBackend',
]


def _read_key_from_env(value_var: str) -> str | None:
    """Read a PEM key from a raw environment variable."""
    key_value = os.getenv(value_var)
    if key_value:
        return key_value.replace("\\n", "\n")
    return None


JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "RS256")
JWT_SIGNING_KEY = _read_key_from_env("JWT_PRIVATE_KEY")
JWT_VERIFYING_KEY = _read_key_from_env("JWT_PUBLIC_KEY")

if JWT_ALGORITHM.upper().startswith(("RS", "ES")):
    if not JWT_SIGNING_KEY:
        raise ImproperlyConfigured(
            "JWT_PRIVATE_KEY must be set when using RS/ES algorithms."
        )
    if not JWT_VERIFYING_KEY:
        raise ImproperlyConfigured(
            "JWT_PUBLIC_KEY must be set when using RS/ES algorithms."
        )

# DJOSER CONFIGURATION
DJOSER = {
    'PASSWORD_RESET_CONFIRM_URL': 'accounts/password_reset/{uid}/{token}',
    'USERNAME_RESET_CONFIRM_URL': 'username/reset/confirm/{uid}/{token}',
    'ACTIVATION_URL': 'activate/{uid}/{token}',
    'SEND_ACTIVATION_EMAIL': True,
    'USER_CREATE_PASSWORD_RETYPE': True,
    'PASSWORD_RESET_CONFIRM_RETYPE': True,
    'LOGOUT_ON_PASSWORD_CHANGE': True,
    'EMAIL_FRONTEND_DOMAIN': EMAIL_FRONTEND_DOMAIN,
    'EMAIL_FRONTEND_PROTOCOL': EMAIL_FRONTEND_PROTOCOL,
    'EMAIL_FRONTEND_SITE_NAME': 'Intera IMS',
    'EMAIL': {
        'activation': 'mainapps.accounts.emails.InteraActivationEmail',
        'password_reset': 'mainapps.accounts.emails.InteraPasswordResetEmail',
    },
    'TOKEN_MODEL': 'rest_framework.authtoken.models.Token',  

    'SOCIAL_AUTH_ALLOWED_REDIRECT_URIS': os.getenv('SOCIAL_AUTH_ALLOWED_REDIRECT_URIS', '').split(','),
    'PERMISSIONS': {
        'user_create': ['rest_framework.permissions.AllowAny'],
    },
}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=2),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=6),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': JWT_ALGORITHM,
    'SIGNING_KEY': JWT_SIGNING_KEY if JWT_SIGNING_KEY else SECRET_KEY,
    'VERIFYING_KEY': JWT_VERIFYING_KEY,
    # Treat empty strings as unset so we don't enforce/emit `aud`/`iss` with "".
    'AUDIENCE': os.getenv("JWT_AUDIENCE") or None,
    'ISSUER': os.getenv("JWT_ISSUER") or None,
    'JWK_URL': os.getenv("JWT_JWK_URL") or None,
    'LEEWAY': 0,
    "TOKEN_OBTAIN_SERIALIZER": "mainapps.accounts.serializers.MyTokenObtainPairSerializer",
    "TOKEN_REFRESH_SERIALIZER": "mainapps.accounts.serializers.TokenRefreshSerializer",

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

AUTH_COOKIE='accessToken'
AUTH_REFRESH_COOKIE='refreshToken'
AUTH_COOKIE_ACCESS_MAX_AGE=60*10
AUTH_COOKIE_REFRESH_MAX_AGE=60*60*24
AUTH_COOKIE_SECURE=os.getenv('AUTH_COOKIE_SECURE', 'True')=='True'
AUTH_COOKIE_HTTP_ONLY=True
AUTH_COOKIE_PATH='/'
AUTH_COOKIE_SAMESITE=os.getenv('AUTH_COOKIE_SAMESITE', 'Lax')
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'mainapps.accounts.authentication.AccountJWTAuthentication',
        # 'rest_framework_simplejwt.authentication.JWTStatelessUserAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.getenv('ANON_RATE_LIMIT', '20/minute'),
        'user': os.getenv('USER_RATE_LIMIT', '120/minute'),
    },
}

CORS_ALLOW_ALL_ORIGINS=os.getenv('CORS_ALLOW_ALL_ORIGINS', 'False')=='True'
CORS_ORIGIN_ALLOW_ALL=CORS_ALLOW_ALL_ORIGINS

CORS_ALLOW_CREDENTIALS=os.getenv('CORS_ALLOW_CREDENTIALS', 'True')=='True'
CORS_ALLOW_METHODS = (
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'X-profile-id',  
    'x-device-id',
]

_default_cors_allowed_origins = [
    "http://localhost:3000",
    "http://localhost:8001",
    "http://127.0.0.1:3000",
    'http://3.212.68.52:3000',
    "https://intera-inventory.vercel.app",
    "http://3.84.22.207:3000",
    'https://intera-inventory.vercel.app',
    'https://dev.product.interaims.com',
    'https://dev.inventory.interaims.com',
    'https://dev.pos.interaims.com',
    'https://accounts.interaims.com',
    'https://dev.accounts.interaims.com',
    'https://www.interaims.com',
    'https://interaims.com',
    'https://dev.interaims.com',
    'http://10.0.2.2:3000',
    'http://10.0.2.2:8080',

]
CORS_ALLOWED_ORIGINS = _split_csv_env("CORS_ALLOWED_ORIGINS", _default_cors_allowed_origins)

_default_csrf_trusted_origins = sorted(set(CORS_ALLOWED_ORIGINS + [
    "https://accounts.interaims.com",
    "https://dev.accounts.interaims.com",
    "http://10.0.2.2:3000",
    "http://10.0.2.2:8080",
]))
CSRF_TRUSTED_ORIGINS = _split_csv_env("CSRF_TRUSTED_ORIGINS", _default_csrf_trusted_origins)


SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False')=='True'

SECURE_PROXY_SSL_HEADER = (
    ('HTTP_X_FORWARDED_PROTO', 'https')
    if os.getenv('SECURE_PROXY_SSL_HEADER_ENABLED', 'False') == 'True'
    else None
)
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True')=='True'

CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'True')=='True'
FILE_UPLOAD_TIMEOUT = 3600
DATA_UPLOAD_MAX_MEMORY_SIZE = 2147483648  # 2GB
FILE_UPLOAD_MAX_MEMORY_SIZE = 2147483648  # 2GB

"""
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis:6379/",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}
"""

# S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME')
AWS_STATIC_LOCATION = os.getenv('AWS_STATIC_LOCATION', 'assessment/static')
AWS_S3_CUSTOM_DOMAIN = "%s.s3.amazonaws.com" % AWS_STORAGE_BUCKET_NAME
AWS_S3_CONNECT_TIMEOUT = 10  
AWS_S3_TIMEOUT = 60 
AWS_S3_FILE_OVERWRITE = True


if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME:

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {"location": AWS_STATIC_LOCATION},
        },
    }
    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_STATIC_LOCATION}/"

if not EMAIL_BRAND_LOGO_URL and EMAIL_SHARED_STATIC_BUCKET:
    EMAIL_BRAND_LOGO_URL = (
        f"https://{EMAIL_SHARED_STATIC_BUCKET}.s3.amazonaws.com/"
        f"{EMAIL_SHARED_STATIC_LOCATION}/{EMAIL_BRAND_STATIC_LOGO_PATH}"
    )
elif not EMAIL_BRAND_LOGO_URL:
    EMAIL_BRAND_LOGO_URL = f"{STATIC_URL.rstrip('/')}/{EMAIL_BRAND_STATIC_LOGO_PATH}"


CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
USE_L10N = True
USE_THOUSAND_SEPARATOR = True

# INTER SERVICE COMMUNICATION
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')

