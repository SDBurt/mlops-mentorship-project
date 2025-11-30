# Superset configuration for Lakehouse Analytics
# https://superset.apache.org/docs/configuration/configuring-superset/

import os
from datetime import timedelta

# ---------------------------------------------------------
# Flask App Configuration
# ---------------------------------------------------------

# Secret key for session signing
SECRET_KEY = os.environ.get("SECRET_KEY", "CHANGE_ME_TO_A_COMPLEX_RANDOM_SECRET")

# ---------------------------------------------------------
# Superset Metadata Database (PostgreSQL)
# ---------------------------------------------------------

DATABASE_HOST = os.environ.get("DATABASE_HOST", "superset-db")
DATABASE_PORT = os.environ.get("DATABASE_PORT", "5432")
DATABASE_USER = os.environ.get("DATABASE_USER", "superset")
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD", "superset")
DATABASE_DB = os.environ.get("DATABASE_DB", "superset")

SQLALCHEMY_DATABASE_URI = (
    f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@"
    f"{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_DB}"
)

# ---------------------------------------------------------
# Redis Cache Configuration (for async queries, caching)
# ---------------------------------------------------------

REDIS_HOST = os.environ.get("REDIS_HOST", "superset-redis")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 1,
}

DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_data_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 2,
}

FILTER_STATE_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_filter_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 3,
}

EXPLORE_FORM_DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_explore_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 4,
}

# ---------------------------------------------------------
# Celery Configuration (async tasks, alerts, reports)
# ---------------------------------------------------------

class CeleryConfig:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    imports = ("superset.sql_lab",)
    task_annotations = {
        "sql_lab.get_sql_results": {"rate_limit": "100/s"},
    }

CELERY_CONFIG = CeleryConfig

# ---------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------

FEATURE_FLAGS = {
    # Enable dashboard filters
    "DASHBOARD_CROSS_FILTERS": True,
    # Enable SQL Lab with Jinja templating
    "ENABLE_TEMPLATE_PROCESSING": True,
    # Dashboard embedding
    "EMBEDDABLE_CHARTS": True,
    "EMBEDDED_SUPERSET": True,
}

# ---------------------------------------------------------
# SQL Lab Configuration
# ---------------------------------------------------------

# Maximum number of rows returned from a SQL Lab query
SQL_MAX_ROW = 100000

# Default row limit for SQL Lab queries
DEFAULT_SQLLAB_LIMIT = 1000

# Enable SQL Lab async queries
SQLLAB_ASYNC_TIME_LIMIT_SEC = 60 * 60 * 2  # 2 hours

# Allow SQL Lab to use CTAS and CVAS
SQLLAB_CTAS_NO_LIMIT = True

# ---------------------------------------------------------
# Trino/Presto Specific Configuration
# ---------------------------------------------------------

# Increase query timeout for Trino (large Iceberg scans)
SUPERSET_WEBSERVER_TIMEOUT = 300

# ---------------------------------------------------------
# Security Configuration
# ---------------------------------------------------------

# Allow embedding in iframes
HTTP_HEADERS = {"X-Frame-Options": "ALLOWALL"}

# Public role for read-only dashboards
PUBLIC_ROLE_LIKE = "Gamma"

# ---------------------------------------------------------
# Application Server Configuration
# ---------------------------------------------------------

WEBSERVER_THREADS = 4
WEBSERVER_TIMEOUT = 300
WEBSERVER_ADDRESS = "0.0.0.0"
WEBSERVER_PORT = 8088

# ---------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------

LOG_FORMAT = "%(asctime)s:%(levelname)s:%(name)s:%(message)s"
LOG_LEVEL = "INFO"
