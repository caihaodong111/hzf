"""
Data source preference helpers.
"""
from __future__ import annotations

from typing import List

from apps.dashboard.models import DataSourcePreference

VALID_MODES = {
    DataSourcePreference.MODE_AUTO,
    DataSourcePreference.MODE_MANUAL,
}


def get_data_source_mode() -> str:
    preference = DataSourcePreference.objects.order_by('-updated_at').first()
    if preference and preference.mode in VALID_MODES:
        return preference.mode
    return DataSourcePreference.MODE_AUTO


def set_data_source_mode(mode: str) -> DataSourcePreference:
    normalized = (mode or '').strip().lower()
    if normalized not in VALID_MODES:
        normalized = DataSourcePreference.MODE_AUTO
    preference, created = DataSourcePreference.objects.get_or_create(
        id=1,
        defaults={'mode': normalized},
    )
    if not created and preference.mode != normalized:
        preference.mode = normalized
        preference.save(update_fields=['mode', 'updated_at'])
    return preference


def get_data_source_priority() -> List[str]:
    mode = get_data_source_mode()
    if mode == DataSourcePreference.MODE_MANUAL:
        return ['huawei']
    return ['huawei', 'national']


def get_allowed_sources() -> List[str]:
    mode = get_data_source_mode()
    if mode == DataSourcePreference.MODE_MANUAL:
        return ['huawei', 'manual']
    return ['huawei', 'national']
