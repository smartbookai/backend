import os

import rollbar

from sba_app.utils.env_utils import loan_env

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env = loan_env(BASE_DIR)

DJANGO_ENVIRONMENT = env("DJANGO_ENVIRONMENT", default="development")

IS_PRODUCTION = DJANGO_ENVIRONMENT == "production"

SECRET_KEY = env('SECRET_KEY')

DEBUG = env('DEBUG')

ALLOWED_HOSTS = env('ALLOWED_HOSTS', default='').split(',')

CORS_ORIGIN_WHITELIST = ["http://*"]

OPENAI_API_KEY = env("OPENAI_API_KEY")
# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "sba_app",
    "django_celery_beat",
    "django_celery_results",
    "import_export",
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]


MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "rollbar.contrib.django.middleware.RollbarNotifierMiddleware",
]

ROOT_URLCONF = "sba.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,  # Enable app directories template loading
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.static",
            ],
        },
    },
]

# Only use cached template loader in production
if IS_PRODUCTION:
    TEMPLATES[0]['OPTIONS']['loaders'] = [
        ('django.template.loaders.cached.Loader', [
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]),
    ]
    # Remove APP_DIRS when using explicit loaders
    TEMPLATES[0]['APP_DIRS'] = False

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.core.context_processors.csrf",
    "django.core.context_processors.request",
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    "django.contrib.messages.context_processors.messages",
)

WSGI_APPLICATION = "sba.wsgi.application"

# Database
DB_ENGINE = env('DB_ENGINE')

if DB_ENGINE == 'sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': f'django.db.backends.{DB_ENGINE}',
            'NAME': os.path.join(BASE_DIR, "db.sqlite3"),
        }
    }
elif DB_ENGINE == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': f'django.db.backends.{DB_ENGINE}',
            'NAME': env('DB_NAME'),
            'USER': env('DB_USER'),
            'PASSWORD': env('DB_PASS'),
            'HOST': env('DB_HOST'),
            'PORT': env('DB_PORT'),
            'OPTIONS': {
                'charset': 'utf8mb4',
            },
            "init_command": 'SET sql_mode="STRICT_TRANS_TABLES"',
        }
    }

# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('es', 'Spanish'),
]

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

if IS_PRODUCTION:
    STATIC_ROOT = os.path.join(BASE_DIR, "../static/")
    MEDIA_ROOT = os.path.join(BASE_DIR, "../media")
else:
    STATIC_ROOT = os.path.join(BASE_DIR, "sba_app/../static")
    MEDIA_ROOT = os.path.join(BASE_DIR, "sba_app/media")

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

STATIC_URL = "/static/"
MEDIA_URL = "/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ROLLBAR = {
    "access_token": env("ROLLBAR_ACCESS_TOKEN"),
    "environment": DJANGO_ENVIRONMENT,
    "code_version": "1.0",
    "root": BASE_DIR,
}
rollbar.init(**ROLLBAR)

HEALTH_CHECK = {
    "DISK_USAGE_MAX": 90,  # Percent
    "MEMORY_MIN": 100,    # in MB
}

# Celery settings
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = "django-db"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_IGNORE_RESULT = False
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_EXPIRES = 3 * 24 * 3600   # 3 days

SITE_URL = env("SITE_URL")

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'index'


