"""
数据看板视图 - 使用真实统计数据
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from apps.sensors.models import Device, SensorData, Alert
from core.data_generator import SensorDataGenerator
from core.open_data_provider import OpenWaterDataService
from core.national_water_data import NationalWaterDataService
from core.data_transformer import DataTransformer


@api_view(['GET'])
def overview(request):
    """获取看板概览数据 - 使用真实统计数据"""
    hours = int(request.query_params.get('hours', 24))
    count = int(request.query_params.get('count', 10))

    # 获取实时数据用于展示
    realtime_data = None
    source = None

    # 优先使用国家水质数据
    if NationalWaterDataService.enabled():
        result = NationalWaterDataService.get_realtime(count=count)
        if result.get("sensors"):
            realtime_data = result
            source = 'national'

    # 其次使用外部数据源
    if not realtime_data and OpenWaterDataService.enabled():
        result = OpenWaterDataService.get_realtime(count=count)
        if result.get("sensors"):
            realtime_data = result
            source = 'open'

    # 最后使用模拟数据
    if not realtime_data:
        realtime_data = SensorDataGenerator.generate_multi_sensors_realtime(count=count)
        source = 'simulator'

    # 计算统计数据 - 使用真实数据
    sensors = realtime_data.get('sensors', [])

    # 计算平均值
    temp_values = [s.get('temperature') for s in sensors if s.get('temperature') is not None]
    do_values = [s.get('dissolved_oxygen') for s in sensors if s.get('dissolved_oxygen') is not None]
    avg_temp = sum(temp_values) / len(temp_values) if temp_values else 0
    avg_do = sum(do_values) / len(do_values) if do_values else 0

    # 从数据库获取真实的设备统计
    total_devices = Device.objects.count()
    online_devices = Device.objects.filter(status='online').count()
    offline_devices = total_devices - online_devices

    # 如果数据库为空，使用实时数据统计
    if total_devices == 0:
        total_devices = len(sensors)
        online_devices = sum(1 for s in sensors if _is_device_online(s))
        offline_devices = total_devices - online_devices

    # 获取告警统计
    time_threshold = timezone.now() - timedelta(hours=hours)
    alert_count = Alert.objects.filter(created_at__gte=time_threshold, resolved=False).count()

    # 如果数据库没有告警，从数据源获取
    if alert_count == 0:
        raw_alerts = []
        if NationalWaterDataService.enabled():
            raw_alerts = NationalWaterDataService.get_alerts(count=10)
        elif OpenWaterDataService.enabled():
            raw_alerts = OpenWaterDataService.get_alerts(count=10)
        else:
            raw_alerts = SensorDataGenerator.generate_alerts(count=10)

        alert_count = len([a for a in raw_alerts if not a.get('resolved', False)])

    # 格式化告警数据
    alerts = []
    if NationalWaterDataService.enabled():
        raw_alerts = NationalWaterDataService.get_alerts(count=5)
        alerts = [DataTransformer.transform_alert(a, 'national') for a in raw_alerts]
    elif OpenWaterDataService.enabled():
        raw_alerts = OpenWaterDataService.get_alerts(count=5)
        alerts = [DataTransformer.transform_alert(a, 'open') for a in raw_alerts]
    else:
        raw_alerts = SensorDataGenerator.generate_alerts(count=5)
        alerts = [DataTransformer.transform_alert(a, 'simulator') for a in raw_alerts]

    # 计算水质分布
    water_quality_dist = {}
    for s in sensors:
        wq = s.get('water_quality')
        if wq:
            water_quality_dist[wq] = water_quality_dist.get(wq, 0) + 1

    return Response({
        'code': 200,
        'message': 'success',
        'data': {
            'timestamp': realtime_data.get('timestamp', timezone.now().isoformat()),
            'data_source': source,
            'summary': {
                'total_devices': total_devices,
                'online_devices': online_devices,
                'offline_devices': offline_devices,
                'alert_count': alert_count,
                'avg_temperature': round(avg_temp, 1),
                'avg_dissolved_oxygen': round(avg_do, 1),
                'water_quality_distribution': water_quality_dist
            },
            'sensors': sensors,
            'alerts': alerts
        }
    })


def _is_device_online(sensor_data):
    """判断设备是否在线"""
    timestamp = sensor_data.get('timestamp')
    if not timestamp:
        return False
    try:
        from datetime import datetime
        if isinstance(timestamp, str):
            # 尝试解析ISO格式时间
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            dt = timestamp
        return (timezone.now() - dt).total_seconds() < 3600
    except:
        return True


@api_view(['GET'])
def statistics(request):
    """获取详细统计数据"""
    hours = int(request.query_params.get('hours', 24))
    time_threshold = timezone.now() - timedelta(hours=hours)

    # 设备统计
    total_devices = Device.objects.count()
    online_devices = Device.objects.filter(status='online').count()
    offline_devices = Device.objects.filter(status='offline').count()
    error_devices = Device.objects.filter(status='error').count()

    # 告警统计
    total_alerts = Alert.objects.filter(created_at__gte=time_threshold).count()
    resolved_alerts = Alert.objects.filter(
        created_at__gte=time_threshold,
        resolved=True
    ).count()
    pending_alerts = total_alerts - resolved_alerts

    # 按级别统计告警
    critical_alerts = Alert.objects.filter(
        created_at__gte=time_threshold,
        alert_level='critical',
        resolved=False
    ).count()
    warning_alerts = Alert.objects.filter(
        created_at__gte=time_threshold,
        alert_level='warning',
        resolved=False
    ).count()

    # 数据统计
    data_count = SensorData.objects.filter(recorded_at__gte=time_threshold).count()

    # 水质统计
    sensor_data_qs = SensorData.objects.filter(
        recorded_at__gte=time_threshold,
        water_quality__isnull=False
    )

    quality_distribution = {}
    for quality, _ in SensorData.WATER_QUALITY_CHOICES:
        if hasattr(SensorData, 'WATER_QUALITY_CHOICES'):
            continue
        count = sensor_data_qs.filter(water_quality=quality).count()
        if count > 0:
            quality_distribution[quality] = count

    # 使用数据库数据计算平均值
    recent_data = SensorData.objects.filter(
        recorded_at__gte=time_threshold
    ).aggregate(
        avg_temp=Avg('temperature'),
        avg_do=Avg('dissolved_oxygen'),
        avg_ph=Avg('ph')
    )

    return Response({
        'code': 200,
        'message': 'success',
        'data': {
            'devices': {
                'total': total_devices,
                'online': online_devices,
                'offline': offline_devices,
                'error': error_devices
            },
            'alerts': {
                'total': total_alerts,
                'resolved': resolved_alerts,
                'pending': pending_alerts,
                'critical': critical_alerts,
                'warning': warning_alerts
            },
            'data_records': {
                'count': data_count
            },
            'averages': {
                'temperature': round(recent_data['avg_temp'] or 0, 2),
                'dissolved_oxygen': round(recent_data['avg_do'] or 0, 2),
                'ph': round(recent_data['avg_ph'] or 0, 2)
            },
            'water_quality_distribution': quality_distribution
        }
    })
