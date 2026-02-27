"""
Backfill province/city for historical sensor records using current inference rules.

Usage:
    python manage.py backfill_city_province
    python manage.py backfill_city_province --model sensor
    python manage.py backfill_city_province --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.sensors.models import ManualSensorData, SensorData
from core.city_resolver import infer_city_name, infer_province_name


def _normalize_province(value: str) -> str:
    return infer_province_name((value,), "") or (value or "").strip()


def _infer_for_record(record) -> tuple[str, str]:
    existing_province = _normalize_province(record.province)
    province_hint = existing_province or infer_province_name(
        (record.location, record.device_name),
        "",
    )
    city_candidate = infer_city_name(
        (record.device_name, record.location, record.province),
        province_hint or "",
        record.device_id or "",
    )
    province_candidate = infer_province_name(
        (record.location, record.device_name, city_candidate),
        city_candidate or "",
    )
    if not province_candidate and province_hint:
        province_candidate = province_hint
    return province_candidate, city_candidate


def _backfill_queryset(queryset, batch_size: int, dry_run: bool) -> tuple[int, int]:
    scanned = 0
    updated = 0
    pending = []

    for record in queryset.iterator(chunk_size=batch_size):
        scanned += 1
        province_candidate, city_candidate = _infer_for_record(record)
        existing_province = _normalize_province(record.province)
        existing_city = (record.city or "").strip()

        changed = False
        if province_candidate and province_candidate != existing_province:
            record.province = province_candidate
            changed = True
        if city_candidate and city_candidate != existing_city:
            record.city = city_candidate
            changed = True

        if changed:
            pending.append(record)
            updated += 1

        if len(pending) >= batch_size:
            if not dry_run:
                with transaction.atomic():
                    queryset.model.objects.bulk_update(pending, ["province", "city"])
            pending = []

    if pending and not dry_run:
        with transaction.atomic():
            queryset.model.objects.bulk_update(pending, ["province", "city"])

    return scanned, updated


class Command(BaseCommand):
    help = "Backfill province/city for sensor_data/manual_sensor_data using inference rules."

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            default="both",
            choices=("sensor", "manual", "both"),
            help="Choose which table to backfill.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            dest="batch_size",
            help="Batch size for bulk updates.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report counts without writing changes.",
        )

    def handle(self, *args, **options):
        model = options["model"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        results = []
        if model in ("sensor", "both"):
            scanned, updated = _backfill_queryset(
                SensorData.objects.all(), batch_size, dry_run
            )
            results.append(("sensor_data", scanned, updated))
        if model in ("manual", "both"):
            scanned, updated = _backfill_queryset(
                ManualSensorData.objects.all(), batch_size, dry_run
            )
            results.append(("manual_sensor_data", scanned, updated))

        for table_name, scanned, updated in results:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{table_name}: scanned={scanned} updated={updated} dry_run={dry_run}"
                )
            )
