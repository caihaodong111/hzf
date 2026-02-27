"""Resolve or infer city names for sensor records."""
from __future__ import annotations

import hashlib
from typing import Iterable, Optional, Set

from core.city_matcher import matches_city
from core.national_water_data import AREA_CODES, CITY_CODES

_CITY_NAMES = sorted(CITY_CODES.keys(), key=len, reverse=True)
_AREA_CODE_TO_NAME = {code: name for name, code in AREA_CODES.items() if code}
_CITY_CODE_TO_NAME = {code: name for name, code in CITY_CODES.items() if code}
_PROVINCE_NAMES = [name for name in AREA_CODES.keys() if name and name != "全国"]
_PROVINCE_SUFFIXES = ("省", "市", "自治区", "壮族自治区", "回族自治区", "维吾尔自治区", "特别行政区")
_PROVINCE_BY_PREFIX = {
    code[:2]: name
    for name, code in AREA_CODES.items()
    if code and name and name != "全国"
}

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


def _province_aliases(province: str) -> Set[str]:
    normalized = str(province or "").strip()
    if not normalized:
        return set()
    aliases = {normalized}
    for suffix in _PROVINCE_SUFFIXES:
        if normalized.endswith(suffix) and len(normalized) > len(suffix):
            aliases.add(normalized[: -len(suffix)])
    return aliases


def _normalize_province_name(province: str) -> str:
    normalized = str(province or "").strip()
    if not normalized:
        return ""
    for candidate in _PROVINCE_NAMES:
        aliases = _province_aliases(candidate)
        if normalized in aliases:
            return candidate
    return normalized


def infer_province_name(
    fields: Iterable[Optional[str]],
    city: str = ""
) -> str:
    """Infer province name from fields or city code mapping."""
    if city:
        city_code = CITY_CODES.get(city)
        if city_code:
            province_name = _PROVINCE_BY_PREFIX.get(city_code[:2])
            if province_name:
                return province_name

    for province in _PROVINCE_NAMES:
        aliases = _province_aliases(province)
        if not aliases:
            continue
        for field in fields:
            if not field:
                continue
            text = str(field).strip()
            for alias in aliases:
                if alias and (text == alias or text.startswith(alias) or alias in text):
                    return province
    return ""


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
    """Infer city name from known fields (no fallback assignment)."""
    province_name = _normalize_province_name(province)
    candidate_cities = _CITY_NAMES
    if province_name in _CITIES_BY_PROVINCE:
        candidate_cities = sorted(_CITIES_BY_PROVINCE[province_name], key=len, reverse=True)
    for city in candidate_cities:
        if matches_city(city, fields):
            return city
    return ""
