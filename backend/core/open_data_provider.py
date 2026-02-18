"""
Open water data provider.
Fetches public data from a configurable CSV or JSON API and normalizes fields.
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenWaterRecord:
    device_id: str
    device_name: str
    location: str
    timestamp: datetime
    temperature: Optional[float]
    salinity: Optional[float]
    dissolved_oxygen: Optional[float]
    ph: Optional[float]
    conductivity: Optional[float] = None  # 电导率 (μS/cm)


_cache: Dict[str, Any] = {"records": None, "fetched_at": None}


def _get_config() -> Dict[str, Any]:
    return getattr(settings, "OPEN_WATER_DATA", {})


def _is_enabled(config: Dict[str, Any]) -> bool:
    return bool(config.get("enabled")) and bool(config.get("url"))


def _cache_valid(config: Dict[str, Any]) -> bool:
    fetched_at = _cache.get("fetched_at")
    if not fetched_at:
        return False
    cache_minutes = int(config.get("cache_minutes", 30))
    return timezone.now() - fetched_at < timedelta(minutes=cache_minutes)


def _fetch_url(url: str, timeout: int, headers: Dict[str, str]) -> bytes:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _decode_bytes(payload: bytes) -> str:
    return payload.decode("utf-8-sig", errors="ignore")


def _coerce_key_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    return [str(value).strip()]


def _pick_value(row: Dict[str, Any], key_spec: Any) -> Any:
    keys = _coerce_key_list(key_spec)
    for key in keys:
        if key in row and row[key] not in ("", None):
            return row[key]
    return None


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _make_device_id(raw_id: str, device_name: str, location: str) -> str:
    if raw_id:
        return raw_id
    seed = device_name or location or "unknown"
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:10]
    return f"site_{digest}"


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text in ("", "--", "-", "—", "N/A", "NA"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_datetime(value: Any, time_formats: Iterable[str]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        try:
            timestamp = int(text)
            if len(text) >= 13:
                timestamp = timestamp / 1000
            return timezone.make_aware(datetime.fromtimestamp(timestamp))
        except (ValueError, OSError):
            pass
    for fmt in time_formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    except ValueError:
        return None


def _normalize_row(row: Dict[str, Any], config: Dict[str, Any]) -> Optional[OpenWaterRecord]:
    field_map = config.get("field_map", {})
    raw_id = _safe_str(_pick_value(row, field_map.get("device_id")))
    device_name = _safe_str(_pick_value(row, field_map.get("device_name"))) or raw_id
    location = _safe_str(_pick_value(row, field_map.get("location")))
    time_formats = config.get("time_formats", [])
    timestamp = _parse_datetime(_pick_value(row, field_map.get("timestamp")), time_formats)
    if not device_name:
        return None
    if not timestamp:
        timestamp = timezone.now()
    return OpenWaterRecord(
        device_id=_make_device_id(raw_id, device_name, location),
        device_name=device_name,
        location=location or "未知",
        timestamp=timestamp,
        temperature=_parse_float(_pick_value(row, field_map.get("temperature"))),
        salinity=_parse_float(_pick_value(row, field_map.get("salinity"))),
        dissolved_oxygen=_parse_float(_pick_value(row, field_map.get("dissolved_oxygen"))),
        ph=_parse_float(_pick_value(row, field_map.get("ph"))),
        conductivity=_parse_float(_pick_value(row, field_map.get("conductivity"))),
    )


def _load_csv(payload: bytes, config: Dict[str, Any]) -> List[OpenWaterRecord]:
    text = _decode_bytes(payload)
    reader = csv.DictReader(text.splitlines())
    records: List[OpenWaterRecord] = []
    for row in reader:
        record = _normalize_row(row, config)
        if record:
            records.append(record)
    return records


def _extract_json_list(data: Any, json_path: str) -> List[Dict[str, Any]]:
    if not json_path:
        return data if isinstance(data, list) else []
    cursor = data
    for key in json_path.split("."):
        if isinstance(cursor, dict):
            cursor = cursor.get(key)
        else:
            cursor = None
        if cursor is None:
            break
    return cursor if isinstance(cursor, list) else []


def _load_json(payload: bytes, config: Dict[str, Any]) -> List[OpenWaterRecord]:
    text = _decode_bytes(payload)
    data = json.loads(text)
    json_path = config.get("json_path", "")
    rows = _extract_json_list(data, json_path)
    records: List[OpenWaterRecord] = []
    for row in rows:
        if isinstance(row, dict):
            record = _normalize_row(row, config)
            if record:
                records.append(record)
    return records


def fetch_records() -> List[OpenWaterRecord]:
    config = _get_config()
    if not _is_enabled(config):
        return []
    if _cache_valid(config):
        return _cache["records"] or []
    url = config["url"]
    try:
        payload = _fetch_url(url, config.get("timeout", 15), config.get("headers", {}))
        if config.get("source_type") == "json":
            records = _load_json(payload, config)
        else:
            records = _load_csv(payload, config)
        _cache["records"] = records
        _cache["fetched_at"] = timezone.now()
        return records
    except Exception as exc:
        logger.warning("Open water data fetch failed: %s", exc)
        return []


def _format_time_label(ts: datetime, hours: int) -> str:
    if hours >= 24:
        return ts.strftime("%m-%d")
    return ts.strftime("%H:%M")


class OpenWaterDataService:
    @staticmethod
    def enabled() -> bool:
        return _is_enabled(_get_config())

    @staticmethod
    def get_devices() -> List[Dict[str, Any]]:
        records = fetch_records()
        devices: Dict[str, Dict[str, Any]] = {}
        for record in records:
            if record.device_id not in devices:
                devices[record.device_id] = {
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "device_type": "sensor",
                    "status": "online",
                    "location": record.location,
                }
        return list(devices.values())

    @staticmethod
    def get_realtime(count: int = 5) -> Dict[str, Any]:
        records = fetch_records()
        if not records:
            return {"timestamp": timezone.now().isoformat(), "sensors": []}
        latest_by_device: Dict[str, OpenWaterRecord] = {}
        for record in records:
            current = latest_by_device.get(record.device_id)
            if not current or record.timestamp > current.timestamp:
                latest_by_device[record.device_id] = record
        latest_records = sorted(latest_by_device.values(), key=lambda r: r.timestamp, reverse=True)
        sensors = []
        for record in latest_records[:count]:
            sensors.append(
                {
                    "device_id": record.device_id,
                    "location": record.location,
                    "temperature": record.temperature,
                    "salinity": record.salinity,
                    "dissolved_oxygen": record.dissolved_oxygen,
                    "ph": record.ph,
                    "timestamp": record.timestamp.isoformat(),
                }
            )
        return {"timestamp": timezone.now().isoformat(), "sensors": sensors}

    @staticmethod
    def get_history(device_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        records = fetch_records()
        if not records:
            return []
        now = timezone.now()
        threshold = now - timedelta(hours=hours)
        filtered = []
        for record in records:
            if record.device_id != device_id:
                continue
            if record.timestamp and record.timestamp < threshold:
                continue
            filtered.append(record)
        filtered.sort(key=lambda r: r.timestamp)
        return [
            {
                "time": _format_time_label(record.timestamp, hours),
                "timestamp": record.timestamp.isoformat(),
                "temperature": record.temperature,
                "salinity": record.salinity,
                "dissolved_oxygen": record.dissolved_oxygen,
                "ph": record.ph,
            }
            for record in filtered
        ]

    @staticmethod
    def get_alerts(count: int = 5) -> List[Dict[str, Any]]:
        records = fetch_records()
        alerts: List[Dict[str, Any]] = []
        for record in records:
            if record.temperature is not None and record.temperature > 30:
                alerts.append(
                    {
                        "device_id": record.device_id,
                        "type": "temperature",
                        "level": "warning",
                        "message": "水温偏高",
                        "value": record.temperature,
                        "timestamp": record.timestamp.isoformat(),
                    }
                )
            if record.dissolved_oxygen is not None and record.dissolved_oxygen < 5:
                alerts.append(
                    {
                        "device_id": record.device_id,
                        "type": "dissolved_oxygen",
                        "level": "warning",
                        "message": "溶解氧偏低",
                        "value": record.dissolved_oxygen,
                        "timestamp": record.timestamp.isoformat(),
                    }
                )
            if record.ph is not None and (record.ph < 6.5 or record.ph > 8.5):
                alerts.append(
                    {
                        "device_id": record.device_id,
                        "type": "ph",
                        "level": "warning",
                        "message": "pH异常",
                        "value": record.ph,
                        "timestamp": record.timestamp.isoformat(),
                    }
                )
            if len(alerts) >= count:
                break
        return alerts[:count]
