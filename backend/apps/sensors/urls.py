"""
传感器应用URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import SensorDataViewSet, AlertViewSet, device_ingest_gateway

router = DefaultRouter()
router.register(r'data', SensorDataViewSet, basename='sensordata')
router.register(r'alerts', AlertViewSet, basename='alert')

urlpatterns = [
    path('device-ingest/', device_ingest_gateway, name='device-ingest'),
    path('', include(router.urls)),
]
