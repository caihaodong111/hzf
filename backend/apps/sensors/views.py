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
from django.db.models import Avg, Count, Q, F
from django.db.models.functions import Coalesce

from .models import SensorData, Alert
from .serializers import (
    SensorDataSerializer, RealtimeDataSerializer,
    HistoricalDataSerializer, AlertSerializer, DashboardSummarySerializer
)
from core.open_data_provider import OpenWaterDataService
from core.national_water_data import NationalWaterDataService
from core.data_transformer import DataTransformer
from core.city_matcher import matches_city
from core.city_resolver import infer_city_name, resolve_area_name


def _compute_data_version(sensors):
    hasher = hashlib.md5()
    ordered = sorted(
        sensors,
        key=lambda item: (
            item.get("device_id") or "",
            str(item.get("timestamp") or "")
        ),
    )
    for sensor in ordered:
        parts = [
            sensor.get("device_id") or "",
            sensor.get("timestamp") or "",
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
        device_id = self.request.query_params.get('device_id')

        if device_id:
            queryset = queryset.filter(device_id=device_id)

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
        last_version = request.query_params.get('last_version', '')
        force_refresh_param = request.query_params.get('force_refresh', '')
        force_refresh = str(force_refresh_param).lower() in {"1", "true", "yes"}

        raw_data = []
        source = None
        total = 0

        # 优先使用国家水质数据
        if NationalWaterDataService.enabled():
            result = NationalWaterDataService.get_realtime(
                count=count,
                area_id=area_id,
                river_id=river_id,
                search_name=search_name,
                city_name=city_name,  # 传递城市参数
                force_refresh=force_refresh
            )
            raw_data = result.get("sensors", [])
            if raw_data:
                source = 'national'
                total = result.get("total", len(raw_data))

        # 其次使用外部数据源
        if not raw_data and OpenWaterDataService.enabled():
            result = OpenWaterDataService.get_realtime(
                count=count,
                area_id=area_id,
                city_name=city_name
            )
            raw_data = result.get("sensors", [])
            if raw_data:
                source = 'open'
                total = len(raw_data)

        # 最后使用数据库快照数据作为备用
        if not raw_data:
            from apps.sensors.models import SensorDataSnapshot
            from datetime import timedelta

            # 获取最近24小时的快照数据
            time_threshold = timezone.now() - timedelta(hours=24)
            snapshots = SensorDataSnapshot.objects.filter(
                snapshot_time__gte=time_threshold
            ).order_by('-snapshot_time')

            # 应用筛选条件
            if search_name:
                snapshots = snapshots.filter(device_name__icontains=search_name)
            area_name = resolve_area_name(area_id)
            if area_name:
                if area_id.endswith("0000"):
                    snapshots = snapshots.filter(province__icontains=area_name)
                else:
                    snapshots = snapshots.filter(
                        Q(city__icontains=area_name) |
                        Q(location__icontains=area_name) |
                        Q(device_name__icontains=area_name) |
                        Q(province__icontains=area_name)
                    )
            if city_name:
                snapshots = snapshots.filter(
                    Q(city__icontains=city_name) |
                    Q(location__icontains=city_name) |
                    Q(device_name__icontains=city_name)
                )

            # 按设备分组，取每个设备的最新数据
            from django.db.models import Max
            latest_snapshots = snapshots.values('device_id').annotate(
                latest_time=Max('snapshot_time')
            )

            sensors_data = []
            for item in latest_snapshots[:count]:
                snapshot = SensorDataSnapshot.objects.filter(
                    device_id=item['device_id'],
                    snapshot_time=item['latest_time']
                ).first()

                if snapshot:
                    sensors_data.append({
                        'device_id': snapshot.device_id,
                        'device_name': snapshot.device_name,
                        'province': snapshot.province or '',
                        'city': snapshot.city or '',  # 添加city字段
                        'river_basin': snapshot.river_basin or '',
                        'water_quality': snapshot.water_quality or '',
                        'timestamp': snapshot.snapshot_time.isoformat(),
                        'temperature': float(snapshot.temperature) if snapshot.temperature else None,
                        'ph': float(snapshot.ph) if snapshot.ph else None,
                        'dissolved_oxygen': float(snapshot.dissolved_oxygen) if snapshot.dissolved_oxygen else None,
                        'conductivity': float(snapshot.conductivity) if snapshot.conductivity else None,
                        'turbidity': float(snapshot.turbidity) if snapshot.turbidity else None,
                        'permanganate': float(snapshot.permanganate) if snapshot.permanganate else None,
                        'ammonia_nitrogen': float(snapshot.ammonia_nitrogen) if snapshot.ammonia_nitrogen else None,
                        'total_phosphorus': float(snapshot.total_phosphorus) if snapshot.total_phosphorus else None,
                        'total_nitrogen': float(snapshot.total_nitrogen) if snapshot.total_nitrogen else None,
                        'chlorophyll_a': float(snapshot.chlorophyll_a) if snapshot.chlorophyll_a else None,
                        'algae_density': float(snapshot.algae_density) if snapshot.algae_density else None,
                    })

            raw_data = sensors_data
            source = 'database'
            total = len(latest_snapshots)

        # 通过数据转换层统一格式
        sensors = []
        for item in raw_data:
            transformed = DataTransformer.transform_realtime_data(item, source)
            if not transformed.get("city"):
                transformed["city"] = infer_city_name(
                    (transformed.get("device_name"), transformed.get("location")),
                    transformed.get("province") or "",
                    transformed.get("device_id") or ""
                )
            sensors.append(transformed)

        if source == 'database':
            filter_city = city_name
            if not filter_city and area_id and not area_id.endswith("0000"):
                filter_city = resolve_area_name(area_id)
            if filter_city:
                sensors = [
                    sensor for sensor in sensors
                    if matches_city(
                        filter_city,
                        (
                            sensor.get("location"),
                            sensor.get("device_name"),
                            sensor.get("city"),
                            sensor.get("province"),
                        )
                    )
                ]
                total = len(sensors)

        data_version = _compute_data_version(sensors)
        changed = not last_version or last_version != data_version
        response_sensors = sensors if changed else []

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'sensors': response_sensors,
                'total': total,
                'timestamp': timezone.now().isoformat(),
                'data_version': data_version,
                'changed': changed
            }
        })

    @action(detail=False, methods=['get'])
    def history(self, request):
        """获取历史数据 - 从数据库快照中读取"""
        from apps.sensors.models import SensorDataSnapshot

        device_id = request.query_params.get('device_id')
        hours = int(request.query_params.get('hours', 24))

        # 计算时间范围
        from datetime import timedelta
        time_threshold = timezone.now() - timedelta(hours=hours)

        # 优先从数据库快照读取
        snapshots = SensorDataSnapshot.objects.filter(
            snapshot_time__gte=time_threshold
        ).order_by('snapshot_time')

        # 如果指定了设备ID，过滤该设备的数据
        if device_id:
            snapshots = snapshots.filter(device_id=device_id)
        else:
            # 如果没有指定设备ID，获取第一个有数据的设备
            first_snapshot = snapshots.first()
            if first_snapshot:
                device_id = first_snapshot.device_id
                snapshots = snapshots.filter(device_id=device_id)

        # 转换为历史数据格式
        history_data = []
        for snapshot in snapshots:
            # 格式化时间标签
            if hours >= 24:
                time_label = snapshot.snapshot_time.strftime('%m-%d')
            else:
                time_label = snapshot.snapshot_time.strftime('%H:%M')

            history_data.append({
                'time': time_label,
                'timestamp': snapshot.snapshot_time.isoformat(),
                'temperature': float(snapshot.temperature) if snapshot.temperature is not None else None,
                'ph': float(snapshot.ph) if snapshot.ph is not None else None,
                'dissolved_oxygen': float(snapshot.dissolved_oxygen) if snapshot.dissolved_oxygen is not None else None,
                'conductivity': float(snapshot.conductivity) if snapshot.conductivity is not None else None,
                'turbidity': float(snapshot.turbidity) if snapshot.turbidity is not None else None,
            })

        data_source = 'database' if history_data else 'none'

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'device_id': device_id,
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
        device_id = self.request.query_params.get('device_id')
        alert_type = self.request.query_params.get('alert_type')
        alert_level = self.request.query_params.get('alert_level')
        resolved = self.request.query_params.get('resolved')

        if device_id:
            queryset = queryset.filter(device_id=device_id)
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

        # 优先使用国家水质数据
        if NationalWaterDataService.enabled():
            raw_alerts = NationalWaterDataService.get_alerts(count=count)
            if raw_alerts:
                alerts = [DataTransformer.transform_alert(a, 'national') for a in raw_alerts]
                source = 'national'

        # 其次使用外部数据源
        if not alerts and OpenWaterDataService.enabled():
            raw_alerts = OpenWaterDataService.get_alerts(count=count)
            if raw_alerts:
                alerts = [DataTransformer.transform_alert(a, 'open') for a in raw_alerts]
                source = 'open'

        # 最后使用数据库数据
        if not alerts:
            queryset = self.get_queryset()[:count]
            serializer = self.get_serializer(queryset, many=True)
            alerts = serializer.data
            source = 'database'

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
