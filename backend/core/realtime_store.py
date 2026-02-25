"""
Store realtime data from external sources into database tables.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from django.db.models import Max

from apps.sensors.models import ManualSensorData, SensorData
from core.data_source_preference import get_data_source_priority
from core.data_transformer import DataTransformer
from core.national_water_data import NationalWaterDataService
from core.open_data_provider import OpenWaterDataService
from core.city_resolver import infer_city_name


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    if isinstance(value, str) and value:
        normalized = value.replace("Z", "+00:00")
        parsed = parse_datetime(normalized)
        if parsed:
            return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    return timezone.now()


def _fetch_realtime(source: str, count: int) -> List[Dict[str, Any]]:
    if source == "national":
        result = NationalWaterDataService.get_realtime(count=count, force_refresh=True)
        return result.get("sensors", [])
    if source == "open":
        result = OpenWaterDataService.get_realtime(count=count)
        return result.get("sensors", [])
    return []


def _pick_source(preferred: Optional[str], count: int) -> Tuple[str, List[Dict[str, Any]]]:
    if preferred:
        sensors = _fetch_realtime(preferred, count)
        return preferred, sensors
    for source in get_data_source_priority():
        sensors = _fetch_realtime(source, count)
        if sensors:
            return source, sensors
    return "none", []


def sync_realtime_data(
    source: Optional[str] = None,
    count: int = 1000,
    manual: bool = False,
) -> Dict[str, Any]:
    """Fetch realtime data and store into auto/manual history tables."""
    normalized_source = (source or "").strip().lower() or None
    if normalized_source == "all":
        results: List[Dict[str, Any]] = []
        total_created = 0
        total_updated = 0
        for item in ("national", "open"):
            created = 0
            updated = 0
            result = sync_realtime_data(source=item, count=count)
            created = result.get("created", 0)
            updated = result.get("updated", 0)
            total_created += created
            total_updated += updated
            results.append(result)
        return {
            "source": "all",
            "created": total_created,
            "updated": total_updated,
            "results": results,
        }

    selected_source, sensors = _pick_source(normalized_source, count)
    if not sensors:
        return {"source": selected_source, "created": 0, "updated": 0}

    created = 0
    updated = 0
    store_source = "manual" if manual else selected_source
    target_model = ManualSensorData if manual else SensorData
    transformed_sensors: List[Dict[str, Any]] = []

    for sensor in sensors:
        transformed = DataTransformer.transform_realtime_data(sensor, selected_source)
        if not transformed.get("device_id"):
            continue
        city_name = infer_city_name(
            (transformed.get("device_name"), transformed.get("location")),
            transformed.get("province") or "",
            transformed.get("device_id") or "",
        )
        recorded_at = _parse_timestamp(transformed.get("timestamp"))
        transformed["recorded_at"] = recorded_at
        transformed["city"] = transformed.get("city") or city_name
        transformed_sensors.append(transformed)

    device_ids = [sensor.get("device_id") for sensor in transformed_sensors if sensor.get("device_id")]
    latest_by_device = {}
    if device_ids:
        latest_qs = target_model.objects.filter(device_id__in=device_ids)
        if not manual:
            latest_qs = latest_qs.filter(data_source=store_source)
        latest_by_device = {
            row["device_id"]: row["last_time"]
            for row in latest_qs.values("device_id").annotate(last_time=Max("recorded_at"))
        }

    to_create = []
    for sensor in transformed_sensors:
        device_id = sensor.get("device_id")
        ts = sensor.get("recorded_at")
        if not device_id or not ts:
            continue
        last_time = latest_by_device.get(device_id)
        if last_time and ts <= last_time:
            continue
        payload = {
            "device_id": device_id,
            "device_name": sensor.get("device_name") or "",
            "location": sensor.get("location") or "",
            "province": sensor.get("province") or "",
            "city": sensor.get("city") or "",
            "river_basin": sensor.get("river_basin") or "",
            "temperature": sensor.get("temperature"),
            "ph": sensor.get("ph"),
            "dissolved_oxygen": sensor.get("dissolved_oxygen"),
            "conductivity": sensor.get("conductivity"),
            "turbidity": sensor.get("turbidity"),
            "salinity": sensor.get("salinity"),
            "water_quality": sensor.get("water_quality"),
            "permanganate": sensor.get("permanganate"),
            "ammonia_nitrogen": sensor.get("ammonia_nitrogen"),
            "total_phosphorus": sensor.get("total_phosphorus"),
            "total_nitrogen": sensor.get("total_nitrogen"),
            "chlorophyll_a": sensor.get("chlorophyll_a"),
            "algae_density": sensor.get("algae_density"),
            "recorded_at": ts,
        }
        if not manual:
            payload["data_source"] = store_source
        to_create.append(target_model(**payload))

    if to_create:
        target_model.objects.bulk_create(to_create, batch_size=200)
        created = len(to_create)

    return {"source": selected_source, "created": created, "updated": updated}
