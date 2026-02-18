"""City matching helpers for filtering records."""
from __future__ import annotations

from typing import Iterable, Optional, Set


_CITY_SUFFIXES = ("自治州", "地区", "盟", "州", "市", "县", "区")


def _normalize_city(city: str) -> str:
    return str(city or "").strip()


def _strip_suffix(city: str) -> str:
    for suffix in _CITY_SUFFIXES:
        if city.endswith(suffix) and len(city) > len(suffix):
            return city[: -len(suffix)]
    return city


def city_aliases(city: str) -> Set[str]:
    """获取城市的所有别名（包括带和不带后缀的版本）"""
    normalized = _normalize_city(city)
    if not normalized:
        return set()
    aliases = {normalized}
    stripped = _strip_suffix(normalized)
    if stripped and stripped != normalized:
        aliases.add(stripped)
    return aliases


def matches_city(city: str, fields: Iterable[Optional[str]]) -> bool:
    """检查城市名称是否匹配任何字段。

    增强的匹配逻辑：
    1. 精确匹配：城市名称完全等于字段值
    2. 包含匹配：城市名称作为字段的一部分（带后缀变体）
    3. 字段以城市开头：字段以城市名称开头（考虑后缀）
    """
    aliases = city_aliases(city)
    if not aliases:
        return True

    for field in fields:
        if not field:
            continue
        text = str(field).strip()

        # 1. 精确匹配
        if text in aliases:
            return True

        # 2. 字段以城市名称开头（处理"北京市 - 某某流域"这种情况）
        for alias in aliases:
            if alias and text.startswith(alias):
                return True
            # 处理"海淀"匹配"海淀区"的情况
            if text.startswith(alias):
                return True

        # 3. 包含匹配（更宽松）
        for alias in aliases:
            if alias and alias in text:
                return True

    return False
