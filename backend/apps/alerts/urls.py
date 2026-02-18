"""
告警应用URL配置 - 重定向到sensors app的alerts路由
保留此文件以兼容现有API路径
"""
from django.urls import path, include

# 直接重定向到sensors app的alerts路由
urlpatterns = [
    path('', include('apps.sensors.urls')),
]
