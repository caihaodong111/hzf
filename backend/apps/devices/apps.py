"""
设备管理应用配置
"""
from django.apps import AppConfig


class DevicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.devices'
    verbose_name = '设备管理'
