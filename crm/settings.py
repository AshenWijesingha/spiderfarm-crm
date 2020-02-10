import os
from celery.schedules import crontab

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'mwx@&97%!$fx_*zgj(2ygi^(s=oh5j(cqb$=+-mkd9scbt!0v0'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# ZONE FRAGMENT DIRECTORY
ZONE_FRAGMENT_DIR = '/home/spiderfarmer/SFCRM/media/uploads/zone_files'

# MAX SPIDERJOB DOMAINS
IMPORT_MAX = 10000

# Application definition

REST_FRAMEWORK = {

    'DATETIME_FORMAT': "%m/%d/%Y %H:%M:%S",
}

LOGIN_REDIRECT_URL = '/'

LOGIN_URL = '/login/'

INSTALLED_APPS = [
    'django.contrib.auth',
    'filebrowser',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'simple_pagination',
    'django_celery_beat',
    'compressor',
    'common',
    'accounts',
    'cases',
    'contacts',
    'emails',
    'leads',
    'opportunity',
    'planner',
    'spiderfarm',
    'sorl.thumbnail',
    'phonenumber_field',
    'storages',
    'marketing',
    'tasks',
    'invoices',
    'events',
    'teams',
    'rest_framework',
    'rest_framework.authtoken',
    'import_export',
    'taggit',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'crm.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, "templates"), ],
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

WSGI_APPLICATION = 'crm.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'sfdb_dev',
        'USER': 'spiderfarmer',
        'PASSWORD': '$p!d3rf4rm3rDBPWD',
        'HOST': 'sfdb01-arctangent.cluster-c9lvpkiabmis.us-west-2.rds.amazonaws.com',
        'PORT': '3306'
    }
}

STATICFILES_DIRS = [os.path.join(BASE_DIR, "assets"), ]

# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Los_Angeles'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Django FileBrowser settings
FILEBROWSER_DIRECTORY = ''
DIRECTORY = ''

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = '/static/'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# EMAIL_HOST = 'localhost'
# EMAIL_PORT = 25
# AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend', )


EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_HOST_USER = os.getenv('SG_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('SG_PWD', '')
EMAIL_PORT = 587
EMAIL_USE_TLS = True

AUTH_USER_MODEL = 'common.User'

STORAGE_TYPE = os.getenv('STORAGE_TYPE', 'normal')

if STORAGE_TYPE == 'normal':
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    MEDIA_URL = '/media/'

    STATIC_URL = '/static/'
    STATIC_ROOT = '/home/spiderfarmer/SFCRM/assets'
    STATICFILES_DIRS = (BASE_DIR + '/static',)
    COMPRESS_ROOT = BASE_DIR + '/static/'

elif STORAGE_TYPE == 's3-storage':

    AWS_STORAGE_BUCKET_NAME = AWS_BUCKET_NAME = os.getenv('AWSBUCKETNAME', '')
    AM_ACCESS_KEY = AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
    AM_PASS_KEY = AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    S3_DOMAIN = AWS_S3_CUSTOM_DOMAIN = str(AWS_BUCKET_NAME) + '.s3.amazonaws.com'

    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }

    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    DEFAULT_S3_PATH = "media"
    STATICFILES_STORAGE = 'storages.backends.s3boto.S3BotoStorage'
    STATIC_S3_PATH = "static"
    COMPRESS_STORAGE = 'storages.backends.s3boto.S3BotoStorage'

    COMPRESS_CSS_FILTERS = [
        'compressor.filters.css_default.CssAbsoluteFilter', 'compressor.filters.cssmin.CSSMinFilter']
    COMPRESS_JS_FILTERS = ['compressor.filters.jsmin.JSMinFilter']
    COMPRESS_REBUILD_TIMEOUT = 5400

    MEDIA_ROOT = '/%s/' % DEFAULT_S3_PATH
    MEDIA_URL = '//%s/%s/' % (S3_DOMAIN, DEFAULT_S3_PATH)
    STATIC_ROOT = "/%s/" % STATIC_S3_PATH
    STATIC_URL = 'https://%s/' % (S3_DOMAIN)
    ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'

    CORS_ORIGIN_ALLOW_ALL = True

    AWS_IS_GZIPPED = True
    AWS_ENABLED = True
    AWS_S3_SECURE_URLS = True

COMPRESS_ROOT = BASE_DIR + '/static/'

COMPRESS_ENABLED = True

COMPRESS_OFFLINE_CONTEXT = {
    'STATIC_URL': 'STATIC_URL',
}

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter', 'compressor.filters.cssmin.CSSMinFilter']
COMPRESS_REBUILD_TIMEOUT = 5400

COMPRESS_OUTPUT_DIR = 'CACHE'
COMPRESS_URL = STATIC_URL

COMPRESS_PRECOMPILERS = (
    ('text/less', 'lessc {infile} {outfile}'),
    ('text/x-sass', 'sass {infile} {outfile}'),
    ('text/x-scss', 'sass {infile} {outfile}'),
)

COMPRESS_OFFLINE_CONTEXT = {
    'STATIC_URL': 'STATIC_URL',
}

DEFAULT_FROM_EMAIL = 'no-reply@django-crm.micropyramid.com'

# celery Tasks
CELERY_BROKER_URL = 'amqp://localhost:5672/'
CELERY_RESULT_BACKEND = 'amqp://localhost:5672/'
CELERY_TIMEZONE='America/Los_Angeles'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

'''
CELERY_BEAT_SCHEDULE = {
    "runs-scheduled-checks-for-missing-host-data-after-ssl-imports-every-21-mins": {
        "task": "spiderfarm.tasks.host_data_cleanup",
        "schedule": crontab(minute='*/21')
    },
    "runs-scheduled-ghost-crawls-after-cleaned-up-host-imports-every-20-mins": {
        "task": "spiderfarm.tasks.ghost_crawl_import",
        "schedule": crontab(minute='*/34')
    },
    "runs-scheduled-daily-ssl-updates-for-leads": {
        "task": "spiderfarm.tasks.ssl_daily_update",
        "schedule": crontab(hour='1')
    }
}
 
CELERY_BEAT_SCHEDULE = {
    "runs-scheduled-ghost-crawls-after-cleaned-up-host-imports-every-25-mins": {
        "task": "spiderfarm.tasks.ghost_crawl_import",
        "schedule": crontab(minute='*/25')
    }
}
'''

MAIL_SENDER = 'AMAZON'
INACTIVE_MAIL_SENDER = 'MANDRILL'

AM_ACCESS_KEY = os.getenv('AM_ACCESS_KEY', '')
AM_PASS_KEY = os.getenv('AM_PASS_KEY', '')
AWS_REGION = os.getenv('AWS_REGION', '')

MGUN_API_URL = os.getenv('MGUN_API_URL', '')
MGUN_API_KEY = os.getenv('MGUN_API_KEY', '')

SG_USER = os.getenv('SG_USER', '')
SG_PWD = os.getenv('SG_PWD', '')

MANDRILL_API_KEY = os.getenv('MANDRILL_API_KEY', '')

ADMIN_EMAIL = "admin@micropyr.com"

URL_FOR_LINKS = "http://djangocrm.com"

try:
    from .dev_settings import *
except ImportError:
    pass


GP_CLIENT_ID = os.getenv('GP_CLIENT_ID', False)
GP_CLIENT_SECRET = os.getenv('GP_CLIENT_SECRET', False)
ENABLE_GOOGLE_LOGIN = os.getenv('ENABLE_GOOGLE_LOGIN', False)

MARKETING_REPLY_EMAIL = 'djangocrm@micropyramid.com'

PASSWORD_RESET_TIMEOUT_DAYS = 3

SENTRY_ENABLED = os.getenv('SENTRY_ENABLED', False)

if SENTRY_ENABLED and not DEBUG:
    if os.getenv('SENTRYDSN') is not None:
        RAVEN_CONFIG = {
            'dsn': os.getenv('SENTRYDSN', ''),
        }
        INSTALLED_APPS = INSTALLED_APPS + [
            'raven.contrib.django.raven_compat',
        ]
        MIDDLEWARE = [
            'raven.contrib.django.raven_compat.middleware.Sentry404CatchMiddleware',
            'raven.contrib.django.raven_compat.middleware.SentryResponseErrorIdMiddleware',
         ] + MIDDLEWARE
        LOGGING = {
            'version': 1,
            'disable_existing_loggers': True,
            'root': {
                'level': 'WARNING',
                'handlers': ['sentry'],
            },
            'formatters': {
                'verbose': {
                    'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
                },
            },
            'handlers': {
                'sentry': {
                    'level': 'ERROR',
                    'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
                },
                'console': {
                    'level': 'DEBUG',
                    'class': 'logging.StreamHandler',
                    'formatter': 'verbose'
                }
            },
            'loggers': {
                'django.db.backends': {
                    'level': 'ERROR',
                    'handlers': ['console'],
                    'propagate': False,
                },
                'raven': {
                    'level': 'DEBUG',
                    'handlers': ['console'],
                    'propagate': False,
                },
                'sentry.errors': {
                    'level': 'DEBUG',
                    'handlers': ['console'],
                    'propagate': False,
                },
            },
        }
