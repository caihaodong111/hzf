"""
数据看板URL配置
"""
from django.urls import path
from .views import overview

urlpatterns = [
    path('overview/', overview, name='dashboard-overview'),
]
