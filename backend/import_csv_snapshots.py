"""
Import historical water quality CSVs into SensorDataSnapshot.

Default source files: ../pc/*.csv
"""
import argparse
import csv
import hashlib
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import django


def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aquaculture.settings")
    django.setup()


def parse_decimal(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "--":
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_snapshot_time(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    # Support formats like "02-18 14:00" and "2025-02-18 14:00".
    formats = ["%Y-%m-%d %H:%M", "%m-%d %H:%M"]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%m-%d %H:%M":
                dt = dt.replace(year=datetime.now().year)
            return dt
        except ValueError:
            continue
    return None


def make_device_id(province, river_basin, device_name):
    raw = f"{province}|{river_basin}|{device_name}"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]
    return f"csv_{digest}"


def import_csv_file(path, batch_size=500):
    from django.utils import timezone
    from apps.sensors.models import SensorDataSnapshot

    created = 0
    buffer = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            province = (row.get("省份") or "").strip()
            river_basin = (row.get("流域") or "").strip()
            device_name = (row.get("断面名称") or "").strip()
            snapshot_time = parse_snapshot_time(row.get("监测时间"))
            if not snapshot_time:
                continue

            if timezone.is_naive(snapshot_time):
                snapshot_time = timezone.make_aware(
                    snapshot_time, timezone.get_current_timezone()
                )

            device_id = make_device_id(province, river_basin, device_name)
            location = f"{province} - {river_basin}" if province or river_basin else ""

            payload = SensorDataSnapshot(
                device_id=device_id,
                device_name=device_name or None,
                location=location or None,
                province=province or None,
                city=None,
                river_basin=river_basin or None,
                water_quality=(row.get("水质类别") or "").strip() or None,
                temperature=parse_decimal(row.get("水温")),
                ph=parse_decimal(row.get("pH")),
                dissolved_oxygen=parse_decimal(row.get("溶解氧")),
                conductivity=parse_decimal(row.get("电导率")),
                turbidity=parse_decimal(row.get("浊度")),
                permanganate=parse_decimal(row.get("高锰酸盐指数")),
                ammonia_nitrogen=parse_decimal(row.get("氨氮")),
                total_phosphorus=parse_decimal(row.get("总磷")),
                total_nitrogen=parse_decimal(row.get("总氮")),
                chlorophyll_a=parse_decimal(row.get("叶绿素α"))
                or parse_decimal(row.get("叶绿素a")),
                algae_density=parse_decimal(row.get("藻密度")),
                data_source="csv_cache",
                snapshot_time=snapshot_time,
            )
            buffer.append(payload)

            if len(buffer) >= batch_size:
                SensorDataSnapshot.objects.bulk_create(
                    buffer, batch_size=batch_size, ignore_conflicts=True
                )
                created += len(buffer)
                buffer = []

    if buffer:
        SensorDataSnapshot.objects.bulk_create(
            buffer, batch_size=batch_size, ignore_conflicts=True
        )
        created += len(buffer)

    return created


def main():
    parser = argparse.ArgumentParser(description="Import CSV snapshots.")
    parser.add_argument(
        "files",
        nargs="*",
        help="CSV files to import. If omitted, imports ../pc/*.csv",
    )
    args = parser.parse_args()

    setup_django()

    if args.files:
        files = [Path(f) for f in args.files]
    else:
        files = sorted(Path(__file__).resolve().parent.parent.joinpath("pc").glob("*.csv"))

    total = 0
    for path in files:
        if not path.exists():
            continue
        created = import_csv_file(path)
        total += created
        print(f"{path}: imported {created} rows")

    print(f"Total imported rows: {total}")


if __name__ == "__main__":
    main()
