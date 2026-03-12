"""
Store realtime data from external sources into database tables.
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

from apps.sensors.models import SensorData, SensorSnapshot
from core.data_source_preference import get_data_source_priority
from core.data_transformer import DataTransformer
from core.national_water_data import NationalWaterDataService
from core.huawei_water_data import HuaweiWaterDataService
from core.city_resolver import infer_city_name, infer_province_name
from core.amap_geocoding import get_amap_service


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    if isinstance(value, str) and value:
        normalized = value.replace("Z", "+00:00")
        parsed = parse_datetime(normalized)
        if parsed:
            return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    return timezone.now()


def _normalize_signature_value(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return value
    return value


def _build_signature(data: Dict[str, Any], fields: Iterable[str]) -> Tuple[Any, ...]:
    return tuple(_normalize_signature_value(data.get(field)) for field in fields)


def _fetch_realtime(source: str, count: int, force_refresh: bool) -> List[Dict[str, Any]]:
    if source == "national":
        result = NationalWaterDataService.get_realtime(count=count, force_refresh=force_refresh)
        return result.get("sensors", [])
    if source == "huawei":
        # 华为数据源强制刷新缓存，确保获取最新数据
        result = HuaweiWaterDataService.get_realtime(count=count, force_refresh=force_refresh)
        return result.get("sensors", [])
    return []

def _fetch_realtime_with_city(
    source: str,
    count: int,
    with_city: bool,
    force_refresh: bool,
    fetch_kwargs: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if source == "national":
        if not with_city:
            logger.info("national 数据源强制启用 with_city=True（已移除非城市抓取路径）")
            with_city = True
        fetch_kwargs = fetch_kwargs or {}
        result = NationalWaterDataService.get_realtime(
            count=count,
            force_refresh=force_refresh,
            with_city=with_city,
            **fetch_kwargs,
        )
        return result.get("sensors", [])
    return _fetch_realtime(source, count, force_refresh)


def _pick_source(preferred: Optional[str], count: int, force_refresh: bool) -> Tuple[str, List[Dict[str, Any]]]:
    if preferred:
        sensors = _fetch_realtime(preferred, count, force_refresh)
        return preferred, sensors
    for source in get_data_source_priority():
        sensors = _fetch_realtime(source, count, force_refresh)
        if sensors:
            return source, sensors
    return "none", []

def _pick_source_with_city(
    preferred: Optional[str],
    count: int,
    with_city: bool,
    force_refresh: bool,
    fetch_kwargs: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    if preferred:
        sensors = _fetch_realtime_with_city(preferred, count, with_city, force_refresh, fetch_kwargs)
        return preferred, sensors
    for source in get_data_source_priority():
        sensors = _fetch_realtime_with_city(source, count, with_city, force_refresh, fetch_kwargs)
        if sensors:
            return source, sensors
    return "none", []


def sync_realtime_data(
    source: Optional[str] = None,
    count: int = 1000,
    manual: bool = False,
    with_city: bool = False,
    force_refresh: bool = True,
    max_cities: int = 0,
    sleep_ms: Optional[int] = None,
    timeout_s: Optional[int] = None,
    workers: Optional[int] = None,
) -> Dict[str, Any]:
    """Fetch realtime data and store into auto/manual history tables."""
    normalized_source = (source or "").strip().lower() or None
    if normalized_source == "all":
        results: List[Dict[str, Any]] = []
        total_created = 0
        total_updated = 0
        for item in ("national", "huawei"):
            created = 0
            updated = 0
            result = sync_realtime_data(
                source=item,
                count=count,
                manual=manual,
                with_city=with_city,
                force_refresh=force_refresh,
                max_cities=max_cities,
                sleep_ms=sleep_ms,
                timeout_s=timeout_s,
                workers=workers,
            )
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

    fetch_kwargs: Dict[str, Any] = {}
    if max_cities and max_cities > 0:
        fetch_kwargs["max_cities"] = int(max_cities)
    if sleep_ms is not None:
        fetch_kwargs["sleep_ms"] = int(sleep_ms)
    if timeout_s is not None:
        fetch_kwargs["timeout_s"] = int(timeout_s)
    if workers is not None:
        fetch_kwargs["workers"] = int(workers)

    selected_source, sensors = _pick_source_with_city(
        normalized_source,
        count,
        with_city,
        force_refresh=force_refresh,
        fetch_kwargs=fetch_kwargs or None,
    )
    if not sensors:
        logger.warning(f"数据源 {selected_source} 未获取到传感器数据")
        return {"source": selected_source, "created": 0, "updated": 0}

    logger.info(f"从数据源 {selected_source} 获取到 {len(sensors)} 条传感器数据")

    created = 0
    updated = 0
    store_source = "manual" if manual else selected_source
    target_model = SensorData
    transformed_sensors: List[Dict[str, Any]] = []

    for sensor in sensors:
        transformed = DataTransformer.transform_realtime_data(sensor, selected_source)
        if not transformed.get("station_id"):
            continue
        province_name = transformed.get("province") or infer_province_name(
            (
                transformed.get("location"),
                transformed.get("station_name"),
                transformed.get("city"),
            ),
            transformed.get("city") or "",
        )
        city_name = transformed.get("city") or infer_city_name(
            (
                transformed.get("station_name"),
                transformed.get("location"),
                province_name,
            ),
            province_name or "",
            transformed.get("station_id") or "",
        )
        recorded_at = _parse_timestamp(transformed.get("timestamp"))
        transformed["recorded_at"] = recorded_at
        transformed["province"] = province_name
        transformed["city"] = city_name
        transformed_sensors.append(transformed)

    missing_city_transformed = sum(
        1 for s in transformed_sensors if not (s.get("city") or "").strip()
    )
    logger.info(
        "转换完成: sensors=%s missing_city=%s with_city=%s",
        len(transformed_sensors),
        missing_city_transformed,
        with_city,
    )

    station_ids = [sensor.get("station_id") for sensor in transformed_sensors if sensor.get("station_id")]
    to_create = []
    skipped = 0
    signature_fields = [
        "station_id",
        "recorded_at",
    ]

    existing_signatures = set()
    if station_ids:
        recorded_ats = {
            sensor.get("recorded_at")
            for sensor in transformed_sensors
            if sensor.get("recorded_at")
        }
        if recorded_ats:
            existing_qs = target_model.objects.filter(
                station_id__in=station_ids,
                recorded_at__in=recorded_ats,
            )
            for row in existing_qs.values(*signature_fields):
                existing_signatures.add(_build_signature(row, signature_fields))

    section_coords: Dict[str, Tuple[float, float]] = {}
    # with_city 场景数据量很大，默认不做高德地理编码（否则会非常慢）；需要时可在 settings 中开启。
    if with_city and not bool(getattr(settings, "AMAP_GEOCODE_ENABLED_WITH_CITY", False)):
        logger.info("with_city=True: 跳过高德地理编码（可通过 AMAP_GEOCODE_ENABLED_WITH_CITY 开启）")
    else:
        geocode_enabled = bool(getattr(settings, "AMAP_GEOCODE_ENABLED", True))
        if geocode_enabled:
            max_sections = int(getattr(settings, "AMAP_GEOCODE_MAX_SECTIONS", 300))
            candidates = [
                {
                    "key": s.get("station_id"),
                    "name": s.get("station_name"),
                    "province": s.get("province"),
                    "city": s.get("city"),
                }
                for s in transformed_sensors
                if s.get("station_id") and s.get("station_name")
            ]
            if max_sections > 0:
                candidates = candidates[:max_sections]
            logger.info(
                "开始获取断面经纬度坐标: sections=%s (total=%s)",
                len(candidates),
                len(transformed_sensors),
            )
            amap_service = get_amap_service()
            section_coords = amap_service.batch_geocode_sections(
                candidates,
                province=None,
                city=None,
            )
            logger.info("成功获取断面经纬度坐标: %s/%s", len(section_coords), len(candidates))
        else:
            logger.info("高德地理编码已禁用（AMAP_GEOCODE_ENABLED=False）")

    for sensor in transformed_sensors:
        station_id = sensor.get("station_id")
        ts = sensor.get("recorded_at")
        if not station_id or not ts:
            continue
        # 获取经纬度坐标
        station_name = sensor.get("station_name")
        longitude, latitude = section_coords.get(station_id, (None, None))
        sensor["longitude"] = longitude
        sensor["latitude"] = latitude

        payload = {
            "station_id": station_id,
            "station_name": station_name or "",
            "location": sensor.get("location") or "",
            "province": sensor.get("province") or "",
            "city": sensor.get("city") or "",
            "river_basin": sensor.get("river_basin") or "",
            "longitude": longitude,
            "latitude": latitude,
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
        payload["data_source"] = store_source
        signature = _build_signature(payload, signature_fields)
        if signature in existing_signatures:
            skipped += 1
            continue
        to_create.append(target_model(**payload))

    if to_create:
        target_model.objects.bulk_create(to_create, batch_size=200)
        created = len(to_create)
        logger.info(f"数据源 {selected_source}: 新入库 {created} 条，跳过 {skipped} 条（重复记录）")
    else:
        logger.info(f"数据源 {selected_source}: 没有新数据入库，跳过 {skipped} 条（全部重复）")

    _sync_snapshot(transformed_sensors, store_source)

    return {"source": selected_source, "created": created, "updated": updated}


def _sync_snapshot(transformed_sensors: List[Dict[str, Any]], store_source: str) -> None:
    latest_by_station: Dict[str, Dict[str, Any]] = {}
    for sensor in transformed_sensors:
        station_id = sensor.get("station_id")
        ts = sensor.get("recorded_at")
        if not station_id or not ts:
            continue
        current = latest_by_station.get(station_id)
        if not current or ts > current.get("recorded_at"):
            latest_by_station[station_id] = sensor

    if not latest_by_station:
        return

    station_ids = list(latest_by_station.keys())
    existing_qs = SensorSnapshot.objects.filter(
        station_id__in=station_ids,
    )
    existing_map = {
        row.station_id: row
        for row in existing_qs
    }

    to_create = []
    to_update = []

    for station_id, sensor in latest_by_station.items():
        record = existing_map.get(station_id)
        payload = {
            "station_id": station_id,
            "station_name": sensor.get("station_name") or "",
            "location": sensor.get("location") or "",
            "province": sensor.get("province") or "",
            "city": sensor.get("city") or "",
            "river_basin": sensor.get("river_basin") or "",
            "longitude": sensor.get("longitude"),
            "latitude": sensor.get("latitude"),
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
            "recorded_at": sensor.get("recorded_at"),
            "data_source": store_source,
        }

        if record:
            if record.recorded_at and payload["recorded_at"] and payload["recorded_at"] < record.recorded_at:
                continue
            if record.recorded_at and payload["recorded_at"] and payload["recorded_at"] == record.recorded_at:
                needs_fill = (
                    (not record.city and payload.get("city"))
                    or (not record.province and payload.get("province"))
                    or (not record.location and payload.get("location"))
                    or (not record.river_basin and payload.get("river_basin"))
                )
                if not needs_fill:
                    continue
            for key, value in payload.items():
                setattr(record, key, value)
            to_update.append(record)
        else:
            to_create.append(SensorSnapshot(**payload))

    if to_create:
        SensorSnapshot.objects.bulk_create(to_create, batch_size=200)
    if to_update:
        SensorSnapshot.objects.bulk_update(
            to_update,
            [
                "station_name",
                "location",
                "province",
                "city",
                "river_basin",
                "longitude",
                "latitude",
                "temperature",
                "ph",
                "dissolved_oxygen",
                "conductivity",
                "turbidity",
                "salinity",
                "water_quality",
                "permanganate",
                "ammonia_nitrogen",
                "total_phosphorus",
                "total_nitrogen",
                "chlorophyll_a",
                "algae_density",
                "recorded_at",
                "data_source",
            ],
            batch_size=200,
        )
