from unittest.mock import patch

from celery import Celery
from django.conf import settings
from django.test import SimpleTestCase

from apps.sensors.tasks import sync_national_realtime_data
from aquaculture import celery_app


class CeleryConfigTests(SimpleTestCase):
    def test_celery_app_is_exposed(self):
        self.assertIsInstance(celery_app, Celery)
        self.assertEqual(celery_app.main, "aquaculture")

    def test_hourly_beat_schedule_points_to_sync_task(self):
        schedule = settings.CELERY_BEAT_SCHEDULE["sync-national-water-data-hourly"]

        self.assertEqual(
            schedule["task"],
            "apps.sensors.tasks.sync_national_realtime_data",
        )


class SensorTaskTests(SimpleTestCase):
    @patch("apps.sensors.tasks.broadcast_realtime_event")
    @patch("apps.sensors.tasks.sync_realtime_data")
    def test_sync_national_realtime_data_uses_expected_options(
        self,
        mock_sync_realtime_data,
        mock_broadcast_realtime_event,
    ):
        mock_sync_realtime_data.return_value = {
            "source": "national",
            "created": 3,
            "updated": 5,
        }

        result = sync_national_realtime_data()

        mock_sync_realtime_data.assert_called_once_with(
            source="national",
            count=0,
            manual=False,
            with_city=True,
            force_refresh=True,
        )
        mock_broadcast_realtime_event.assert_called_once_with(
            {
                "reason": "celery_beat",
                "source": "national",
                "created": 3,
                "updated": 5,
            }
        )
        self.assertEqual(result, mock_sync_realtime_data.return_value)
