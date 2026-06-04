"""
WebSocket consumers for realtime data updates.
"""
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from .realtime_events import REALTIME_GROUP_NAME


class RealtimeUpdateConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(REALTIME_GROUP_NAME, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                'event': 'realtime.connected',
                'timestamp': timezone.now().isoformat(),
            }
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(REALTIME_GROUP_NAME, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get('event') == 'ping':
            await self.send_json(
                {
                    'event': 'pong',
                    'timestamp': timezone.now().isoformat(),
                }
            )

    async def realtime_message(self, event):
        await self.send_json(
            {
                'event': event.get('event', 'realtime.snapshot.updated'),
                'payload': event.get('payload') or {},
                'timestamp': event.get('timestamp') or timezone.now().isoformat(),
            }
        )
