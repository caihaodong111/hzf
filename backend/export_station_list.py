"""
Export station list to CSV for manual address mapping.

Usage:
  python export_station_list.py --output /path/to/station_list.csv
  python export_station_list.py --source snapshot
  python export_station_list.py --source history
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import django


def _setup_django() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, base_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aquaculture.settings")
    django.setup()


def _export_snapshot(output_path: str) -> int:
    from apps.sensors.models import SensorSnapshot

    qs = SensorSnapshot.objects.exclude(station_id__isnull=True).order_by("station_id")
    rows = qs.values(
        "station_id",
        "station_name",
        "province",
        "city",
        "river_basin",
        "location",
    )
    count = 0
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["station_id", "station_name", "province", "city", "river_basin", "location"])
        for row in rows:
            writer.writerow(
                [
                    row.get("station_id") or "",
                    row.get("station_name") or "",
                    row.get("province") or "",
                    row.get("city") or "",
                    row.get("river_basin") or "",
                    row.get("location") or "",
                ]
            )
            count += 1
    return count


def _export_history(output_path: str) -> int:
    from apps.sensors.models import SensorData

    rows = (
        SensorData.objects.exclude(station_id__isnull=True)
        .values("station_id", "station_name", "province", "city", "river_basin", "location")
        .distinct()
        .order_by("station_id")
    )
    count = 0
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["station_id", "station_name", "province", "city", "river_basin", "location"])
        for row in rows:
            writer.writerow(
                [
                    row.get("station_id") or "",
                    row.get("station_name") or "",
                    row.get("province") or "",
                    row.get("city") or "",
                    row.get("river_basin") or "",
                    row.get("location") or "",
                ]
            )
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Export station list to CSV.")
    parser.add_argument(
        "--output",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "station_list.csv")),
        help="CSV output path.",
    )
    parser.add_argument(
        "--source",
        choices=("snapshot", "history"),
        default="snapshot",
        help="Export source: snapshot (latest) or history (all distinct).",
    )
    args = parser.parse_args()

    _setup_django()

    if args.source == "history":
        count = _export_history(args.output)
    else:
        count = _export_snapshot(args.output)

    print(f"exported {count} rows to {args.output}")


if __name__ == "__main__":
    main()
