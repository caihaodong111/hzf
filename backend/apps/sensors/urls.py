"""
传感器应用URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import DeviceViewSet, SensorDataViewSet

router = DefaultRouter()
router.register(r'devices', DeviceViewSet, basename='device')
router.register(r'data', SensorDataViewSet, basename='sensordata')

urlpatterns = [
    path('', include(router.urls)),
]
