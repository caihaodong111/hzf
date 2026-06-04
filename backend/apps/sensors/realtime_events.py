"""
Realtime event broadcasting helpers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

logger = logging.getLogger(__name__)

REALTIME_GROUP_NAME = 'realtime_updates'
REALTIME_EVENT_NAME = 'realtime.snapshot.updated'


def broadcast_realtime_event(payload: Dict[str, Any] | None = None) -> bool:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return False

    try:
        async_to_sync(channel_layer.group_send)(
            REALTIME_GROUP_NAME,
            {
                'type': 'realtime.message',
                'event': REALTIME_EVENT_NAME,
                'payload': payload or {},
                'timestamp': timezone.now().isoformat(),
            },
        )
        return True
    except Exception:
        logger.warning('Failed to broadcast realtime event', exc_info=True)
        return False
