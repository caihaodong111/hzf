"""
数据看板URL配置
"""
from django.urls import path
from .views import overview, ai_insight, data_source_settings

urlpatterns = [
    path('overview/', overview, name='dashboard-overview'),
    path('ai-insight/', ai_insight, name='dashboard-ai-insight'),
    path('settings/data-source/', data_source_settings, name='dashboard-data-source-settings'),
]
