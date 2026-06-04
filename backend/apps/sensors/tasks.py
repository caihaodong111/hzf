"""
Celery tasks for sensor data synchronization.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from celery import shared_task

from core.realtime_store import sync_realtime_data
from .realtime_events import broadcast_realtime_event

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def sync_national_realtime_data() -> Dict[str, Any]:
    """Hourly sync for national water data snapshots."""
    logger.info("Celery periodic sync started: source=national")

    result = sync_realtime_data(
        source="national",
        count=0,
        manual=False,
        with_city=True,
        force_refresh=True,
    )

    logger.info(
        "Celery periodic sync finished: source=%s created=%s updated=%s",
        result.get("source"),
        result.get("created", 0),
        result.get("updated", 0),
    )
    broadcast_realtime_event(
        {
            "reason": "celery_beat",
            "source": result.get("source"),
            "created": result.get("created", 0),
            "updated": result.get("updated", 0),
        }
    )
    return result
