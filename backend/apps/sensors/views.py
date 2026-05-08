"""
传感器数据视图 - 统一多数据源接口
使用数据转换层确保输出格式一致
"""
import hashlib
import logging

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Min, Max
from django.db.models.functions import Coalesce

from .models import SensorData, SensorSnapshot, StationLocation, Alert
from .serializers import (
    SensorDataSerializer, RealtimeDataSerializer,
    HistoricalDataSerializer, AlertSerializer, DashboardSummarySerializer
)
from core.national_water_data import NationalWaterDataService
from core.huawei_water_data import HuaweiWaterDataService
from core.data_transformer import DataTransformer
from core.data_source_preference import get_allowed_sources, get_data_source_priority, get_data_source_mode
from core.realtime_store import sync_realtime_data
from core.city_matcher import matches_city
from core.city_resolver import infer_city_name, resolve_area_name
from core.national_water_data import AREA_CODES

logger = logging.getLogger(__name__)


def _compute_data_version(sensors):
    hasher = hashlib.md5()
    ordered = sorted(
        sensors,
        key=lambda item: (
            item.get("station_id") or "",
            str(item.get("timestamp") or "")
        ),
    )
    for sensor in ordered:
        timestamp = sensor.get("timestamp")
        if not isinstance(timestamp, str):
            timestamp = str(timestamp or "")
        parts = [
            sensor.get("station_id") or "",
            timestamp or "",
            sensor.get("water_quality") or "",
            str(sensor.get("temperature") or ""),
            str(sensor.get("ph") or ""),
            str(sensor.get("dissolved_oxygen") or ""),
        ]
        hasher.update("|".join(parts).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


class SensorDataViewSet(viewsets.ReadOnlyModelViewSet):
    """传感器数据视图集 - 使用数据库模型"""
    queryset = SensorData.objects.all()
    serializer_class = SensorDataSerializer

    @action(detail=False, methods=['get'])
    def area_options(self, request):
        """返回省/市级联筛选选项（仅基于数据库快照，不触发外部抓取）。"""
        allowed_sources = get_allowed_sources()
        snapshot_qs = SensorSnapshot.objects.exclude(station_id__isnull=True)
        if allowed_sources:
            snapshot_qs = snapshot_qs.filter(data_source__in=allowed_sources)

        province_to_cities = {}
        for province, city in snapshot_qs.values_list("province", "city").distinct():
            province_name = str(province or "").strip()
            city_name = str(city or "").strip()
            if not province_name:
                continue
            bucket = province_to_cities.setdefault(province_name, set())
            if city_name:
                bucket.add(city_name)

        province_name_to_code = {
            str(name).strip(): str(code).strip()
            for name, code in AREA_CODES.items()
            if name and code and name != "全国"
        }

        def province_sort_key(name: str):
            code = province_name_to_code.get(name) or "999999"
            return (0 if code != "999999" else 1, code, name)

        options = [{"code": "", "name": "全国", "children": []}]
        for province_name in sorted(province_to_cities.keys(), key=province_sort_key):
            options.append(
                {
                    "code": province_name_to_code.get(province_name, ""),
                    "name": province_name,
                    "children": sorted(province_to_cities.get(province_name) or []),
                }
            )

        return Response(
            {
                "code": 200,
                "message": "success",
                "data": {
                    "options": options,
                },
            }
        )

    def get_queryset(self):
        queryset = super().get_queryset()
        station_id = self.request.query_params.get('station_id') or self.request.query_params.get('device_id')

        if station_id:
            queryset = queryset.filter(station_id=station_id)

        # 默认返回最近24小时的数据
        hours = int(self.request.query_params.get('hours', 24))
        time_threshold = timezone.now() - timedelta(hours=hours)
        queryset = queryset.filter(recorded_at__gte=time_threshold)

        return queryset.order_by('-recorded_at')

    @action(detail=False, methods=['get'])
    def realtime(self, request):
        """获取实时数据 - 只使用真实数据源"""
        count = int(request.query_params.get('count', 100))
        area_id = request.query_params.get('area_id', '')
        river_id = request.query_params.get('river_id', '')
        search_name = request.query_params.get('search_name', '')
        city_name = request.query_params.get('city_name', '')  # 添加城市参数
        force_refresh = str(request.query_params.get('force_refresh', '')).lower() in ('1', 'true', 'yes')
        last_version = request.query_params.get('last_version', '')
        manual_mode = get_data_source_mode() == 'manual'
        allowed_sources = get_allowed_sources()
        base_queryset = SensorSnapshot.objects.all()
        if allowed_sources:
            base_queryset = base_queryset.filter(data_source__in=allowed_sources)
        if search_name:
            base_queryset = base_queryset.filter(station_name__icontains=search_name)

        area_name = resolve_area_name(area_id)
        if area_name:
            if area_id.endswith("0000"):
                base_queryset = base_queryset.filter(province__icontains=area_name)
            else:
                base_queryset = base_queryset.filter(
                    Q(city__icontains=area_name) |
                    Q(location__icontains=area_name) |
                    Q(station_name__icontains=area_name) |
                    Q(province__icontains=area_name)
                )

        if river_id:
            base_queryset = base_queryset.filter(river_basin__icontains=river_id)

        if city_name:
            base_queryset = base_queryset.filter(
                Q(city__icontains=city_name) |
                Q(location__icontains=city_name) |
                Q(station_name__icontains=city_name) |
                Q(province__icontains=city_name)
            )

        sensors = []
        latest_time = None
        missing_coord_station_ids = set()
        snapshot_queryset = base_queryset.exclude(station_id__isnull=True).order_by('-recorded_at')
        for record in snapshot_queryset:
            if not latest_time or record.recorded_at > latest_time:
                latest_time = record.recorded_at
            transformed = DataTransformer.transform_realtime_data({
                'station_id': record.station_id,
                'station_name': record.station_name,
                'location': record.location,
                'province': record.province,
                'city': record.city,
                'river_basin': record.river_basin,
                'water_quality': record.water_quality,
                'temperature': record.temperature,
                'ph': record.ph,
                'dissolved_oxygen': record.dissolved_oxygen,
                'conductivity': record.conductivity,
                'turbidity': record.turbidity,
                'salinity': record.salinity,
                'permanganate': record.permanganate,
                'ammonia_nitrogen': record.ammonia_nitrogen,
                'total_phosphorus': record.total_phosphorus,
                'total_nitrogen': record.total_nitrogen,
                'chlorophyll_a': record.chlorophyll_a,
                'algae_density': record.algae_density,
                'longitude': float(record.longitude) if record.longitude else None,
                'latitude': float(record.latitude) if record.latitude else None,
                'recorded_at': record.recorded_at,
            }, 'database')
            if transformed.get("longitude") is None or transformed.get("latitude") is None:
                station_id = transformed.get("station_id")
                if station_id:
                    missing_coord_station_ids.add(station_id)
            if not transformed.get("city"):
                transformed["city"] = infer_city_name(
                    (transformed.get("station_name"), transformed.get("location")),
                    transformed.get("province") or "",
                    transformed.get("station_id") or ""
                )
            transformed["data_source"] = record.data_source or ("manual" if manual_mode else "auto")
            transformed["_recorded_at"] = record.recorded_at
            sensors.append(transformed)

        if missing_coord_station_ids:
            cached_coords = {
                row.station_id: (float(row.longitude), float(row.latitude))
                for row in (
                    StationLocation.objects.filter(station_id__in=list(missing_coord_station_ids))
                    .exclude(longitude__isnull=True)
                    .exclude(latitude__isnull=True)
                )
                if row.station_id
            }
            if cached_coords:
                for sensor in sensors:
                    if sensor.get("longitude") is not None and sensor.get("latitude") is not None:
                        continue
                    station_id = sensor.get("station_id")
                    coords = cached_coords.get(station_id)
                    if coords:
                        sensor["longitude"], sensor["latitude"] = coords

        if city_name:
            sensors = [
                sensor for sensor in sensors
                if matches_city(
                    city_name,
                    (
                        sensor.get("location"),
                        sensor.get("station_name"),
                        sensor.get("city"),
                        sensor.get("province"),
                    )
                )
            ]

        total = len(sensors)
        sensors = sensors[:count]
        if sensors:
            latest_time = max(
                (sensor.get("_recorded_at") for sensor in sensors if sensor.get("_recorded_at")),
                default=latest_time
            )
        for sensor in sensors:
            if "_recorded_at" in sensor:
                sensor.pop("_recorded_at")

        data_version = _compute_data_version(sensors)
        changed = not last_version or last_version != data_version
        response_sensors = sensors if changed else []

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'sensors': response_sensors,
                'total': total,
                'timestamp': (latest_time or timezone.now()).isoformat(),
                'data_version': data_version,
                'changed': changed
            }
        })

    @action(detail=False, methods=['post'])
    def sync_realtime(self, request):
        """手动触发实时数据入库"""
        payload = request.data or {}
        source = (payload.get('source') or '').strip().lower() or None
        raw_count = payload.get('count', 1000)
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            count = 1000
        manual = payload.get('manual', True)
        with_city = payload.get('with_city', False)
        force_refresh = payload.get('force_refresh', True)
        max_cities = payload.get('max_cities', 0)
        sleep_ms = payload.get('sleep_ms')
        timeout_s = payload.get('timeout_s')
        workers = payload.get('workers')
        if isinstance(manual, str):
            manual = manual.strip().lower() in ('1', 'true', 'yes')
        if isinstance(with_city, str):
            with_city = with_city.strip().lower() in ('1', 'true', 'yes')
        if isinstance(force_refresh, str):
            force_refresh = force_refresh.strip().lower() in ('1', 'true', 'yes')
        try:
            max_cities = int(max_cities or 0)
        except (TypeError, ValueError):
            max_cities = 0
        try:
            sleep_ms = None if sleep_ms is None or sleep_ms == "" else int(sleep_ms)
        except (TypeError, ValueError):
            sleep_ms = None
        try:
            timeout_s = None if timeout_s is None or timeout_s == "" else int(timeout_s)
        except (TypeError, ValueError):
            timeout_s = None
        try:
            workers = None if workers is None or workers == "" else int(workers)
        except (TypeError, ValueError):
            workers = None
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or '-'
        logger.info(
            "sync_realtime triggered: source=%s count=%s manual=%s with_city=%s force_refresh=%s max_cities=%s sleep_ms=%s timeout_s=%s workers=%s ip=%s",
            source,
            count,
            bool(manual),
            bool(with_city),
            bool(force_refresh),
            max_cities,
            sleep_ms,
            timeout_s,
            workers,
            client_ip,
        )
        result = sync_realtime_data(
            source=source,
            count=count,
            manual=bool(manual),
            with_city=bool(with_city),
            force_refresh=bool(force_refresh),
            max_cities=max_cities,
            sleep_ms=sleep_ms,
            timeout_s=timeout_s,
            workers=workers,
        )
        logger.info(
            "sync_realtime finished: source=%s created=%s updated=%s",
            result.get("source"),
            result.get("created"),
            result.get("updated"),
        )
        return Response({
            'code': 200,
            'message': 'success',
            'data': result
        })

    @action(detail=False, methods=['get'])
    def history(self, request):
        """获取历史数据 - 从数据库历史表中读取"""
        station_id = request.query_params.get('station_id') or request.query_params.get('device_id')
        hours = int(request.query_params.get('hours', 24))
        limit = int(request.query_params.get('limit', 0))  # 0表示不限制，返回所有数据

        time_threshold = timezone.now() - timedelta(hours=hours)

        manual_mode = get_data_source_mode() == 'manual'
        allowed_sources = get_allowed_sources()
        sensor_qs = SensorData.objects.filter(recorded_at__gte=time_threshold).order_by('recorded_at')
        if allowed_sources:
            sensor_qs = sensor_qs.filter(data_source__in=allowed_sources)
        if station_id:
            sensor_qs = sensor_qs.filter(station_id=station_id)
        else:
            first_record = sensor_qs.first()
            if first_record:
                station_id = first_record.station_id
                sensor_qs = sensor_qs.filter(station_id=station_id)

        # 应用限制
        if limit > 0:
            sensor_qs = sensor_qs[:limit]

        history_data = []
        for record in sensor_qs:
            if hours <= 24:
                time_label = record.recorded_at.strftime('%H:%M')
            else:
                time_label = record.recorded_at.strftime('%m-%d')

            history_data.append({
                'time': time_label,
                'timestamp': record.recorded_at.isoformat(),
                'temperature': float(record.temperature) if record.temperature is not None else None,
                'ph': float(record.ph) if record.ph is not None else None,
                'dissolved_oxygen': float(record.dissolved_oxygen) if record.dissolved_oxygen is not None else None,
                'conductivity': float(record.conductivity) if record.conductivity is not None else None,
                'turbidity': float(record.turbidity) if record.turbidity is not None else None,
                'permanganate_index': float(record.permanganate) if record.permanganate is not None else None,
                'ammonia_nitrogen': float(record.ammonia_nitrogen) if record.ammonia_nitrogen is not None else None,
                'total_phosphorus': float(record.total_phosphorus) if record.total_phosphorus is not None else None,
                'total_nitrogen': float(record.total_nitrogen) if record.total_nitrogen is not None else None,
                'chlorophyll_a': float(record.chlorophyll_a) if record.chlorophyll_a is not None else None,
                'algae_density': float(record.algae_density) if record.algae_density is not None else None,
            })

        if manual_mode and history_data:
            data_source = 'manual'
        else:
            data_source = 'auto' if history_data else 'none'

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'station_id': station_id,
                'data_source': data_source,
                'data': history_data,
                'count': len(history_data)
            }
        })

    @action(detail=False, methods=['get'])
    def all_history(self, request):
        """获取站点所有历史数据 - 不受时间限制"""
        station_id = request.query_params.get('station_id') or request.query_params.get('device_id')

        if not station_id:
            return Response({
                'code': 400,
                'message': '需要提供station_id参数'
            }, status=400)

        manual_mode = get_data_source_mode() == 'manual'
        allowed_sources = get_allowed_sources()

        # 获取该站点的所有历史数据，按时间升序排列
        sensor_qs = SensorData.objects.filter(station_id=station_id).order_by('recorded_at')

        if allowed_sources:
            sensor_qs = sensor_qs.filter(data_source__in=allowed_sources)

        # 统计信息
        total_count = sensor_qs.count()
        if total_count == 0:
            return Response({
                'code': 200,
                'message': 'success',
                'data': {
                    'station_id': station_id,
                    'data_source': 'none',
                    'data': [],
                    'count': 0,
                    'time_range': None
                }
            })

        # 获取时间范围
        time_range = sensor_qs.aggregate(
            min_time=Min('recorded_at'),
            max_time=Max('recorded_at')
        )

        history_data = []
        for record in sensor_qs:
            # 根据时间跨度决定时间标签格式
            time_span = (time_range['max_time'] - time_range['min_time']).total_seconds()
            if time_span <= 86400:  # 24小时内
                time_label = record.recorded_at.strftime('%H:%M')
            elif time_span <= 604800:  # 7天内
                time_label = record.recorded_at.strftime('%m-%d %H:%M')
            else:
                time_label = record.recorded_at.strftime('%m-%d')

            history_data.append({
                'time': time_label,
                'timestamp': record.recorded_at.isoformat(),
                'temperature': float(record.temperature) if record.temperature is not None else None,
                'ph': float(record.ph) if record.ph is not None else None,
                'dissolved_oxygen': float(record.dissolved_oxygen) if record.dissolved_oxygen is not None else None,
                'conductivity': float(record.conductivity) if record.conductivity is not None else None,
                'turbidity': float(record.turbidity) if record.turbidity is not None else None,
                'permanganate_index': float(record.permanganate) if record.permanganate is not None else None,
                'ammonia_nitrogen': float(record.ammonia_nitrogen) if record.ammonia_nitrogen is not None else None,
                'total_phosphorus': float(record.total_phosphorus) if record.total_phosphorus is not None else None,
                'total_nitrogen': float(record.total_nitrogen) if record.total_nitrogen is not None else None,
                'chlorophyll_a': float(record.chlorophyll_a) if record.chlorophyll_a is not None else None,
                'algae_density': float(record.algae_density) if record.algae_density is not None else None,
            })

        if manual_mode and history_data:
            data_source = 'manual'
        else:
            data_source = 'database' if history_data else 'none'

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'station_id': station_id,
                'data_source': data_source,
                'data': history_data,
                'count': len(history_data),
                'time_range': {
                    'start': time_range['min_time'].isoformat() if time_range['min_time'] else None,
                    'end': time_range['max_time'].isoformat() if time_range['max_time'] else None
                }
            }
        })


class AlertViewSet(viewsets.ModelViewSet):
    """告警视图集 - 统一告警数据"""
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    filterset_fields = ['alert_type', 'alert_level', 'resolved']

    def get_queryset(self):
        queryset = super().get_queryset()
        station_id = self.request.query_params.get('station_id') or self.request.query_params.get('device_id')
        alert_type = self.request.query_params.get('alert_type')
        alert_level = self.request.query_params.get('alert_level')
        resolved = self.request.query_params.get('resolved')

        if station_id:
            queryset = queryset.filter(station_id=station_id)
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        if alert_level:
            queryset = queryset.filter(alert_level=alert_level)
        if resolved is not None:
            is_resolved = str(resolved).lower() in {"1", "true", "yes"}
            queryset = queryset.filter(resolved=is_resolved)

        return queryset.order_by('-created_at')

    def list(self, request, *args, **kwargs):
        """获取告警列表 - 统一多数据源格式"""
        count = int(request.query_params.get('count', 50))
        alerts = []
        source = None
        manual_mode = get_data_source_mode() == 'manual'

        if not manual_mode:
            for preferred in get_data_source_priority():
                if preferred == 'huawei' and HuaweiWaterDataService.enabled():
                    raw_alerts = HuaweiWaterDataService.get_alerts(count=count)
                    if raw_alerts:
                        alerts = [DataTransformer.transform_alert(a, 'huawei') for a in raw_alerts]
                        source = 'huawei'
                        break
                if preferred == 'national' and NationalWaterDataService.enabled():
                    raw_alerts = NationalWaterDataService.get_alerts(count=count)
                    if raw_alerts:
                        alerts = [DataTransformer.transform_alert(a, 'national') for a in raw_alerts]
                        source = 'national'
                        break

        # 最后使用数据库数据
        if not alerts:
            queryset = self.get_queryset()
            if manual_mode:
                queryset = queryset.filter(data_source='manual')
            queryset = queryset[:count]
            serializer = self.get_serializer(queryset, many=True)
            alerts = serializer.data
            source = 'manual' if manual_mode else 'database'

        if not alerts:
            source = source or 'none'

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'alerts': alerts,
                'total': len(alerts),
                'data_source': source
            }
        })

    @action(detail=False, methods=['post'])
    def resolve(self, request):
        """批量解决告警"""
        alert_ids = request.data.get('alert_ids', [])
        if not alert_ids:
            return Response({
                'code': 400,
                'message': '请提供要解决的告警ID列表'
            }, status=400)

        updated = Alert.objects.filter(id__in=alert_ids).update(
            resolved=True,
            resolved_at=timezone.now()
        )

        return Response({
            'code': 200,
            'message': f'已解决 {updated} 条告警',
            'data': {'resolved_count': updated}
        })

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """获取告警统计摘要"""
        hours = int(request.query_params.get('hours', 24))
        time_threshold = timezone.now() - timedelta(hours=hours)

        queryset = Alert.objects.filter(created_at__gte=time_threshold)
        if get_data_source_mode() == 'manual':
            queryset = queryset.filter(data_source='manual')

        total = queryset.count()
        resolved_count = queryset.filter(resolved=True).count()
        pending_count = total - resolved_count

        # 按级别统计
        critical_count = queryset.filter(alert_level='critical', resolved=False).count()
        warning_count = queryset.filter(alert_level='warning', resolved=False).count()
        info_count = queryset.filter(alert_level='info', resolved=False).count()

        # 按类型统计
        type_stats = {}
        for alert_type, _ in Alert.ALERT_TYPE_CHOICES:
            type_count = queryset.filter(alert_type=alert_type, resolved=False).count()
            if type_count > 0:
                type_stats[alert_type] = type_count

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'total': total,
                'resolved': resolved_count,
                'pending': pending_count,
                'by_level': {
                    'critical': critical_count,
                    'warning': warning_count,
                    'info': info_count
                },
                'by_type': type_stats
            }
        })
