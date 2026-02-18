"""Resolve or infer city names for sensor records."""
from __future__ import annotations

import hashlib
from typing import Iterable, Optional

from core.city_matcher import matches_city
from core.national_water_data import AREA_CODES, CITY_CODES

_CITY_NAMES = sorted(CITY_CODES.keys(), key=len, reverse=True)
_AREA_CODE_TO_NAME = {code: name for name, code in AREA_CODES.items() if code}
_CITY_CODE_TO_NAME = {code: name for name, code in CITY_CODES.items() if code}

_PROVINCE_PREFIX = {
    province: code[:2]
    for province, code in AREA_CODES.items()
    if code
}
_CITIES_BY_PROVINCE = {
    province: [city for city, code in CITY_CODES.items() if code.startswith(prefix)]
    for province, prefix in _PROVINCE_PREFIX.items()
}


def resolve_area_name(area_id: str) -> str:
    if not area_id:
        return ""
    return _CITY_CODE_TO_NAME.get(area_id) or _AREA_CODE_TO_NAME.get(area_id, "")


def _stable_index(seed: str, size: int) -> int:
    if size <= 0:
        return 0
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % size


def infer_city_name(
    fields: Iterable[Optional[str]],
    province: str = "",
    device_id: str = ""
) -> str:
    """Infer city name from known fields or assign a stable fallback by province."""
    for city in _CITY_NAMES:
        if matches_city(city, fields):
            return city

    if province:
        cities = _CITIES_BY_PROVINCE.get(province, [])
        if cities:
            seed = device_id or province
            return cities[_stable_index(seed, len(cities))]

    return ""
