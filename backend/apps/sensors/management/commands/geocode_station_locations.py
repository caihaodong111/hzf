import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db import transaction

from apps.sensors.models import SensorSnapshot, StationLocation
from core.amap_geocoding import get_amap_service

logger = logging.getLogger(__name__)


def _clean(value) -> str:
    return str(value or "").strip()


class Command(BaseCommand):
    help = "从 sensor_data_latest 的省/市/位置/断面名出发，调用高德地理编码补齐 station_locations，并可选回写 sensor_data_latest。"
    # 该命令不依赖 URLConf / 外部数据源，跳过 system checks 可避免不必要的模块导入（例如华为 SDK）。
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=300, help="最多处理多少个站点（0=全量；默认 300）")
        parser.add_argument("--batch-size", type=int, default=300, help="每批处理站点数（默认 300）")
        parser.add_argument(
            "--update-snapshot",
            action="store_true",
            help="把命中的经纬度回写到 sensor_data_latest（仅填充空值，不覆盖已有坐标）",
        )
        parser.add_argument(
            "--prefer-location",
            action="store_true",
            help="优先使用 location 字段作为高德查询关键词（否则默认用 station_name）",
        )

    def handle(self, *args, **options):
        amap_key = _clean(
            getattr(settings, "AMAP_WEB_SERVICE_KEY", "")
            or getattr(settings, "AMAP_API_KEY", "")
        )
        if not amap_key:
            raise CommandError(
                "未配置高德 Web 服务 Key，无法调用高德地理编码。请先设置环境变量 AMAP_WEB_SERVICE_KEY（或兼容 AMAP_API_KEY）。"
            )

        limit = int(options.get("limit") or 0)
        batch_size = int(options.get("batch_size") or 0)
        if batch_size <= 0:
            raise CommandError("--batch-size 必须为正整数。")
        update_snapshot = bool(options.get("update_snapshot"))
        prefer_location = bool(options.get("prefer_location"))

        amap_service = get_amap_service()
        self.stdout.write(
            f"start geocode_station_locations: limit={limit or 'ALL'} batch_size={batch_size} "
            f"update_snapshot={update_snapshot} prefer_location={prefer_location}"
        )

        def _process_batch(candidates: list) -> tuple[int, int, int, int, int]:
            """
            Returns: (attempted, ok, created, updated, snapshot_updated)
            """
            if not candidates:
                return (0, 0, 0, 0, 0)

            station_ids = [_clean(item.get("key")) for item in candidates if _clean(item.get("key"))]

            # 1) 先用 station_locations 已有坐标回填（可选）并跳过 API 调用
            existing_coords = {
                row.station_id: (float(row.longitude), float(row.latitude))
                for row in (
                    StationLocation.objects.filter(station_id__in=station_ids)
                    .exclude(longitude__isnull=True)
                    .exclude(latitude__isnull=True)
                )
                if row.station_id
            }

            remaining = [item for item in candidates if _clean(item.get("key")) not in existing_coords]

            # 2) 调用高德地理编码补齐剩余部分
            geocoded_coords = {}
            if remaining:
                geocoded_coords = amap_service.batch_geocode_sections(remaining, province=None, city=None) or {}

            coords_map = {**existing_coords, **geocoded_coords}
            if not coords_map:
                return (len(candidates), 0, 0, 0, 0)

            created = 0
            updated = 0
            snapshot_updated = 0

            meta_by_id = {_clean(item.get("key")): item for item in candidates if _clean(item.get("key"))}

            with transaction.atomic():
                existing_rows = StationLocation.objects.filter(station_id__in=list(coords_map.keys()))
                existing_map = {row.station_id: row for row in existing_rows if row.station_id}

                to_create = []
                to_update = []

                for station_id, (lon, lat) in coords_map.items():
                    station_id = _clean(station_id)
                    if not station_id:
                        continue
                    meta = meta_by_id.get(station_id) or {}
                    row = existing_map.get(station_id)

                    payload = {
                        "station_id": station_id,
                        "station_name": meta.get("station_name") or meta.get("name") or "",
                        "province": meta.get("province") or "",
                        "city": meta.get("city") or "",
                        "longitude": lon,
                        "latitude": lat,
                        "source": "amap" if station_id in geocoded_coords else (row.source if row else "amap"),
                    }

                    if row:
                        if row.longitude is None or row.latitude is None:
                            for k, v in payload.items():
                                setattr(row, k, v)
                            to_update.append(row)
                    else:
                        to_create.append(StationLocation(**payload))

                if to_create:
                    StationLocation.objects.bulk_create(to_create, batch_size=200)
                    created = len(to_create)
                if to_update:
                    StationLocation.objects.bulk_update(
                        to_update,
                        ["station_name", "province", "city", "longitude", "latitude", "source"],
                        batch_size=200,
                    )
                    updated = len(to_update)

                if update_snapshot:
                    for station_id, (lon, lat) in coords_map.items():
                        snapshot_updated += SensorSnapshot.objects.filter(station_id=station_id).filter(
                            models.Q(longitude__isnull=True) | models.Q(latitude__isnull=True)
                        ).update(longitude=lon, latitude=lat)

            return (len(candidates), len(coords_map), created, updated, snapshot_updated)

        qs = SensorSnapshot.objects.exclude(station_id__isnull=True).order_by("-updated_at")
        processed = 0
        attempted_total = 0
        ok_total = 0
        created_total = 0
        updated_total = 0
        snapshot_updated_total = 0
        candidates: list = []

        def _append_candidate(snap: SensorSnapshot) -> None:
            station_id = _clean(snap.station_id)
            if not station_id:
                return
            name = _clean(snap.location) if prefer_location else ""
            if not name:
                name = _clean(snap.station_name) or _clean(snap.location)
            if not name:
                return
            query = _clean(snap.location) if prefer_location else ""
            if not query:
                query = _clean(snap.location) or _clean(snap.station_name)
            if query and len(query) <= 4 and all(token not in query for token in ("桥", "闸", "坝", "水库", "河", "湖", "港", "渠")):
                ctx = " ".join(part for part in (_clean(snap.city), _clean(snap.province), _clean(snap.river_basin)) if part).strip()
                if ctx:
                    query = f"{query} {ctx}"
            candidates.append(
                {
                    "key": station_id,
                    "name": name,
                    "query": query,
                    "province": _clean(snap.province),
                    "city": _clean(snap.city),
                    "river_basin": _clean(snap.river_basin),
                    "station_name": _clean(snap.station_name),
                    "location": _clean(snap.location),
                }
            )

        for snap in qs.iterator(chunk_size=2000):
            if limit > 0 and processed >= limit:
                break
            processed += 1
            _append_candidate(snap)
            if len(candidates) >= batch_size:
                attempted, ok, created, updated, snap_updated = _process_batch(candidates)
                attempted_total += attempted
                ok_total += ok
                created_total += created
                updated_total += updated
                snapshot_updated_total += snap_updated
                self.stdout.write(
                    f"batch done: processed={processed} attempted={attempted_total} ok={ok_total} "
                    f"created={created_total} updated={updated_total} snapshot_updated={snapshot_updated_total}"
                )
                candidates = []

        if candidates:
            attempted, ok, created, updated, snap_updated = _process_batch(candidates)
            attempted_total += attempted
            ok_total += ok
            created_total += created
            updated_total += updated
            snapshot_updated_total += snap_updated

        if attempted_total == 0:
            self.stdout.write(self.style.WARNING("没有需要地理编码的站点（可能都已缓存或缺少名称字段）。"))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"geocode done: processed={processed} attempted={attempted_total} ok={ok_total} "
                f"station_locations created={created_total} updated={updated_total} "
                f"snapshot_updated={snapshot_updated_total}"
            )
        )
