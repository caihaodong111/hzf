"""
传感器应用配置
"""
from django.apps import AppConfig


class SensorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sensors'
    verbose_name = '传感器管理'
