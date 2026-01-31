"""
告警应用URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AlertViewSet

router = DefaultRouter()
router.register('', AlertViewSet, basename='alert')

urlpatterns = [
    path('', include(router.urls)),
]
