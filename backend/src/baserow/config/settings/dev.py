from .base import *  # noqa: F403, F401
import snoop

SECRET_KEY = os.getenv("SECRET_KEY", "dev_hardcoded_secret_key")  # noqa: F405

DEBUG = True
WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES = 4
WEBHOOKS_MAX_RETRIES_PER_CALL = 4

INSTALLED_APPS += ["django_extensions", "silk"]  # noqa: F405

MIDDLEWARE += [  # noqa: F405
    "silk.middleware.SilkyMiddleware",
]

SILKY_ANALYZE_QUERIES = True

snoop.install()

CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_USE_TLS = False
EMAIL_HOST = "mailhog"
EMAIL_PORT = 1025

BASEROW_IMPORT_TOLERATED_TYPE_ERROR_THRESHOLD = 5  # Allow 5% to be more adventurous
BASEROW_MAX_FILE_IMPORT_ERROR_COUNT = 10  # To trigger this exception easily

try:
    from .local import *  # noqa: F403, F401
except ImportError:
    pass
