"""
传感器数据视图 - 统一多数据源接口
使用数据转换层确保输出格式一致
"""
import hashlib

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.db.models.functions import Coalesce

from .models import SensorData, SensorSnapshot, Alert
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

        use_source_filter = (not manual_mode) and (area_id or river_id or search_name or city_name)
        source_filter_applied = False
        if use_source_filter:
            station_ids = set()
            source_available = False
            if HuaweiWaterDataService.enabled():
                source_available = True
                try:
                    from core.huawei_water_data import fetch_records as huawei_fetch_records
                    huawei_records = huawei_fetch_records()
                    station_ids.update(
                        (getattr(record, "station_id", None) or getattr(record, "device_id", None))
                        for record in huawei_records
                        if getattr(record, "station_id", None) or getattr(record, "device_id", None)
                    )
                except Exception:
                    pass
            if NationalWaterDataService.enabled():
                source_available = True
                try:
                    records = NationalWaterDataService.api().fetch_records(
                        area_id=area_id,
                        river_id=river_id,
                        search_name=search_name,
                        city_name=city_name,
                        force_refresh=force_refresh,
                        max_pages=10,
                    )
                    station_ids.update(
                        (getattr(record, "station_id", None) or getattr(record, "device_id", None))
                        for record in records
                        if getattr(record, "station_id", None) or getattr(record, "device_id", None)
                    )
                except Exception:
                    pass
            if source_available:
                source_filter_applied = True
                if station_ids:
                    base_queryset = base_queryset.filter(station_id__in=station_ids)
                else:
                    base_queryset = base_queryset.none()

        if not source_filter_applied:
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

        city_post_filter = bool(city_name) and not source_filter_applied

        sensors = []
        latest_time = None
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
            if not transformed.get("city"):
                transformed["city"] = infer_city_name(
                    (transformed.get("station_name"), transformed.get("location")),
                    transformed.get("province") or "",
                    transformed.get("station_id") or ""
                )
            transformed["data_source"] = record.data_source or ("manual" if manual_mode else "auto")
            transformed["_recorded_at"] = record.recorded_at
            sensors.append(transformed)

        if city_name and (manual_mode or city_post_filter):
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
        count = int(payload.get('count') or 1000)
        manual = payload.get('manual', True)
        if isinstance(manual, str):
            manual = manual.strip().lower() in ('1', 'true', 'yes')
        result = sync_realtime_data(source=source, count=count, manual=bool(manual))
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
