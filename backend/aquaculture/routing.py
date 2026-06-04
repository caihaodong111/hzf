"""
WebSocket routing.
"""
from django.urls import path

from apps.sensors.consumers import RealtimeUpdateConsumer

websocket_urlpatterns = [
    path('ws/realtime/', RealtimeUpdateConsumer.as_asgi()),
]
