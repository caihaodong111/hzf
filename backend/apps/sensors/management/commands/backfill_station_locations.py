import logging

from django.core.management.base import BaseCommand

from apps.sensors.models import SensorSnapshot, StationLocation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "从 sensor_data_latest 回填 station_locations（仅回填已有经纬度的数据，不调用外部地理编码）。"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="最多处理多少条（0=不限制）")

    def handle(self, *args, **options):
        limit = int(options.get("limit") or 0)

        qs = (
            SensorSnapshot.objects.exclude(station_id__isnull=True)
            .exclude(longitude__isnull=True)
            .exclude(latitude__isnull=True)
            .order_by("-updated_at")
        )
        if limit > 0:
            qs = qs[:limit]

        created = 0
        updated = 0

        for snap in qs.iterator(chunk_size=500):
            station_id = (snap.station_id or "").strip()
            if not station_id:
                continue

            obj, was_created = StationLocation.objects.get_or_create(
                station_id=station_id,
                defaults={
                    "station_name": snap.station_name,
                    "province": snap.province,
                    "city": snap.city,
                    "longitude": snap.longitude,
                    "latitude": snap.latitude,
                    "source": "snapshot",
                },
            )
            if was_created:
                created += 1
                continue

            if obj.longitude is None or obj.latitude is None:
                obj.station_name = obj.station_name or snap.station_name
                obj.province = obj.province or snap.province
                obj.city = obj.city or snap.city
                obj.longitude = snap.longitude
                obj.latitude = snap.latitude
                obj.source = obj.source or "snapshot"
                obj.save(update_fields=["station_name", "province", "city", "longitude", "latitude", "source", "updated_at"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"backfill done: created={created} updated={updated}"))

