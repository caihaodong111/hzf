"""
Django settings for aquaculture project.
"""
import os
import json
from pathlib import Path
from datetime import timedelta

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
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party apps
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    # 'drf_yasg',  # 暂时禁用以创建迁移
    # 'django_celery_beat',

    # Local apps
    'apps.sensors',
    'apps.alerts',
    'apps.dashboard',
    'apps.users',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'aquaculture.wsgi.application'

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
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

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
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
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


# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
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
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Create logs directory if it doesn't exist
(BASE_DIR / 'logs').mkdir(exist_ok=True)

# Open water data source configuration
_open_headers = {
    "User-Agent": os.environ.get("OPEN_WATER_DATA_UA", "Mozilla/5.0"),
}
_open_headers_env = os.environ.get("OPEN_WATER_DATA_HEADERS", "")
if _open_headers_env:
    try:
        _open_headers.update(json.loads(_open_headers_env))
    except json.JSONDecodeError:
        pass

OPEN_WATER_DATA = {
    "enabled": os.environ.get("OPEN_WATER_DATA_ENABLED", "false").lower() == "true",
    "source_type": os.environ.get("OPEN_WATER_DATA_SOURCE", "csv").lower(),
    "url": os.environ.get("OPEN_WATER_DATA_URL", ""),
    "timeout": int(os.environ.get("OPEN_WATER_DATA_TIMEOUT", "15")),
    "cache_minutes": int(os.environ.get("OPEN_WATER_DATA_CACHE_MINUTES", "30")),
    "json_path": os.environ.get("OPEN_WATER_DATA_JSON_PATH", ""),
    "time_formats": [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d%H%M%S",
    ],
    "field_map": {
        "device_id": os.environ.get("OPEN_WATER_DATA_FIELD_DEVICE_ID", "站点编号|断面编号|MN"),
        "device_name": os.environ.get("OPEN_WATER_DATA_FIELD_DEVICE_NAME", "断面名称|站点名称|监测断面"),
        "location": os.environ.get("OPEN_WATER_DATA_FIELD_LOCATION", "所在地|区域|省份|城市|河流"),
        "timestamp": os.environ.get("OPEN_WATER_DATA_FIELD_TIMESTAMP", "监测时间|采样时间|时间"),
        "temperature": os.environ.get("OPEN_WATER_DATA_FIELD_TEMPERATURE", "水温|温度"),
        "ph": os.environ.get("OPEN_WATER_DATA_FIELD_PH", "pH|PH"),
        "dissolved_oxygen": os.environ.get("OPEN_WATER_DATA_FIELD_DO", "溶解氧|DO"),
        # 修复：电导率和盐度是不同的物理量，不能混用
        "salinity": os.environ.get("OPEN_WATER_DATA_FIELD_SALINITY", "盐度"),
        "conductivity": os.environ.get("OPEN_WATER_DATA_FIELD_CONDUCTIVITY", "电导率|电导"),
    },
    "headers": _open_headers,
}

# National water data configuration (国家水质自动综合监管平台)
NATIONAL_WATER_DATA_ENABLED = os.environ.get("NATIONAL_WATER_DATA_ENABLED", "true").lower() == "true"
NATIONAL_WATER_DATA_CACHE_MINUTES = int(os.environ.get("NATIONAL_WATER_DATA_CACHE_MINUTES", "20"))
