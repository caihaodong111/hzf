"""
Django settings for aquaculture project.
"""
import os
import json
from pathlib import Path
from datetime import timedelta
from celery.schedules import crontab

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# 修复Django 6.x的mysqlclient版本检查问题 - 必须在导入django.db.backends之前执行
import sys
import pymysql

# 先安装pymysql作为MySQLdb
pymysql.install_as_MySQLdb()

# 然后设置版本号，使Django版本检查通过
pymysql.version_info = (2, 2, 1)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Security settings
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-this-in-production')
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party apps
    'channels',
    'rest_framework',
    'corsheaders',
    'django_filters',
    # 'drf_yasg',  # 暂时禁用以创建迁移

    # Local apps
    'apps.sensors',
    'apps.alerts',
    'apps.dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'aquaculture.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'aquaculture.wsgi.application'
ASGI_APPLICATION = 'aquaculture.asgi.application'

CHANNEL_LAYER_BACKEND = os.environ.get('CHANNEL_LAYER_BACKEND', 'memory').strip().lower()
if CHANNEL_LAYER_BACKEND == 'redis':
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [os.environ.get('CHANNEL_REDIS_URL', os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'))],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'hzf'),
        'HOST': os.environ.get('DB_HOST', '47.93.141.103'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'USER': os.environ.get('DB_USER', 'hzf'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'hzf123123'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# Cache (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = []

# Internationalization
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
}

# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:3000",
]
CORS_ALLOW_CREDENTIALS = True

# CSRF settings
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
CSRF_COOKIE_SAMESITE = 'Lax'


# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.dashboard': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.sensors': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.alerts': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Create logs directory if it doesn't exist
(BASE_DIR / 'logs').mkdir(exist_ok=True)

# National water data configuration (国家水质自动综合监管平台)
NATIONAL_WATER_DATA_ENABLED = os.environ.get("NATIONAL_WATER_DATA_ENABLED", "true").lower() == "true"
NATIONAL_WATER_DATA_CACHE_MINUTES = int(os.environ.get("NATIONAL_WATER_DATA_CACHE_MINUTES", "20"))
NATIONAL_WATER_CITY_SLEEP_MS = int(os.environ.get("NATIONAL_WATER_CITY_SLEEP_MS", "50"))
NATIONAL_WATER_CITY_TIMEOUT_S = int(os.environ.get("NATIONAL_WATER_CITY_TIMEOUT_S", "30"))
NATIONAL_WATER_CITY_WORKERS = int(os.environ.get("NATIONAL_WATER_CITY_WORKERS", "8"))

# Huawei water data configuration (华为云API市场 - 地表水监测数据)
HUAWEI_WATER_DATA = {
    "enabled": os.environ.get("HUAWEI_WATER_DATA_ENABLED", "false").lower() == "true",
    "url": os.environ.get("HUAWEI_WATER_DATA_URL", "https://nawaterstation.apistore.huaweicloud.com/api/surface_water/data"),
    "app_key": os.environ.get("HUAWEI_WATER_DATA_APP_KEY", ""),
    "app_secret": os.environ.get("HUAWEI_WATER_DATA_APP_SECRET", ""),
    "timeout": int(os.environ.get("HUAWEI_WATER_DATA_TIMEOUT", "15")),
    "cache_minutes": int(os.environ.get("HUAWEI_WATER_DATA_CACHE_MINUTES", "10")),
    "json_path": os.environ.get("HUAWEI_WATER_DATA_JSON_PATH", "data"),
    "default_params": json.loads(os.environ.get("HUAWEI_WATER_DATA_DEFAULT_PARAMS", '{"version":"v1"}')),
    "stanames": json.loads(os.environ.get("HUAWEI_WATER_DATA_STANAMES", '[]')) if os.environ.get("HUAWEI_WATER_DATA_STANAMES") else [],
}

# AMap (高德地图) - 地理编码与前端地图
# 后端 Web 服务 Key（用于 restapi.amap.com 的地理编码/逆地理编码等）
AMAP_WEB_SERVICE_KEY = os.environ.get("AMAP_WEB_SERVICE_KEY", "")
# 兼容旧变量名：AMAP_API_KEY（同样用于后端 Web 服务 Key）
AMAP_API_KEY = os.environ.get("AMAP_API_KEY", "")
AMAP_GEOCODE_ENABLED = os.environ.get("AMAP_GEOCODE_ENABLED", "true").lower() == "true"
# with_city=True 数据量大，默认关闭；如需在按城市抓取时也进行地理编码可开启
AMAP_GEOCODE_ENABLED_WITH_CITY = os.environ.get("AMAP_GEOCODE_ENABLED_WITH_CITY", "false").lower() == "true"
AMAP_GEOCODE_MAX_SECTIONS = int(os.environ.get("AMAP_GEOCODE_MAX_SECTIONS", "300"))

# Celery (Redis broker + hourly beat schedule)
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"))
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = False
CELERY_TASK_IGNORE_RESULT = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "sync-national-water-data-hourly": {
        "task": "apps.sensors.tasks.sync_national_realtime_data",
        "schedule": crontab(minute=0),
    },
}
