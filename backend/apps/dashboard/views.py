"""
数据看板视图 - 使用真实统计数据
"""
import json
import os
import logging
import urllib.request
import urllib.error

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Avg, Count, Max, Q
from django.utils import timezone
from datetime import timedelta

from apps.sensors.models import SensorData, SensorSnapshot, Alert
from core.national_water_data import NationalWaterDataService
from core.huawei_water_data import HuaweiWaterDataService
from core.data_transformer import DataTransformer
from core.data_source_preference import (
    get_allowed_sources,
    get_data_source_mode,
    get_data_source_priority,
    set_data_source_mode,
)

logger = logging.getLogger(__name__)

POOR_WATER_QUALITIES = [
    'Ⅲ', 'Ⅳ', 'Ⅴ', '劣Ⅴ',
    'Ⅲ类', 'Ⅳ类', 'Ⅴ类', '劣Ⅴ类',
    '劣V', '劣V类',
]


@api_view(['GET'])
def overview(request):
    """获取看板概览数据 - 使用真实统计数据"""
    hours = int(request.query_params.get('hours', 24))
    count = int(request.query_params.get('count', 10))
    manual_mode = get_data_source_mode() == 'manual'

    # 获取实时数据用于展示
    realtime_data = None
    source = None

    snapshot_qs = SensorSnapshot.objects.exclude(station_id__isnull=True)
    allowed_sources = get_allowed_sources()
    if allowed_sources:
        snapshot_qs = snapshot_qs.filter(data_source__in=allowed_sources)
    latest_time = snapshot_qs.aggregate(max_time=Max('recorded_at')).get('max_time')
    preview_sensors = []
    for record in snapshot_qs.order_by('-recorded_at')[:count]:
        transformed = DataTransformer.transform_realtime_data({
            'station_id': record.station_id,
            'station_name': record.station_name,
            'location': record.location,
            'province': record.province,
            'city': record.city,
            'river_basin': record.river_basin,
            'longitude': float(record.longitude) if record.longitude is not None else None,
            'latitude': float(record.latitude) if record.latitude is not None else None,
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
            'recorded_at': record.recorded_at,
        }, 'database')
        transformed['data_source'] = record.data_source or ('manual' if manual_mode else 'auto')
        preview_sensors.append(transformed)
    realtime_data = {
        'sensors': preview_sensors,
        'timestamp': (latest_time or timezone.now()).isoformat()
    }
    source = 'manual' if manual_mode else ('auto' if preview_sensors else 'none')

    # 无可用数据源时返回空结果
    if not realtime_data:
        realtime_data = {'sensors': [], 'timestamp': timezone.now().isoformat()}
        source = 'none'

    def _round_agg(value, digits=2):
        if value is None:
            return 0
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return 0

    # 计算统计数据 - 使用真实数据
    sensors = realtime_data.get('sensors', [])

    # 核心指标均值：来自 sensor_data_latest（SensorSnapshot），不依赖 count / hours
    avg_agg = snapshot_qs.aggregate(
        avg_temperature=Avg('temperature'),
        avg_ph=Avg('ph'),
        avg_dissolved_oxygen=Avg('dissolved_oxygen'),
        avg_conductivity=Avg('conductivity'),
        avg_turbidity=Avg('turbidity'),
        avg_permanganate=Avg('permanganate'),
        avg_ammonia_nitrogen=Avg('ammonia_nitrogen'),
        avg_total_phosphorus=Avg('total_phosphorus'),
        avg_total_nitrogen=Avg('total_nitrogen'),
        avg_chlorophyll_a=Avg('chlorophyll_a'),
        avg_algae_density=Avg('algae_density'),
    )

    # 设备统计：来自 sensor_data_latest（SensorSnapshot），不依赖 count / hours
    total_devices = snapshot_qs.values('station_id').distinct().count()
    online_threshold = timezone.now() - timedelta(hours=1)
    online_devices = snapshot_qs.filter(recorded_at__gte=online_threshold).values('station_id').distinct().count()
    offline_devices = max(total_devices - online_devices, 0)

    if total_devices == 0:
        total_devices, online_devices, offline_devices = _get_device_counts_from_history(
            hours,
            manual_mode=manual_mode,
            allowed_sources=allowed_sources,
        )

    # 告警数量（用于“AI 智能分析”卡片）：来自 sensor_data_latest 中水质较差的断面数量
    # 说明：这里按最新快照统计，不受 hours 参数影响
    alert_count = snapshot_qs.filter(water_quality__in=POOR_WATER_QUALITIES).count()

    # 格式化告警数据
    alerts = []
    if manual_mode:
        alerts = list(Alert.objects.filter(data_source='manual').order_by('-created_at')[:5].values())
    else:
        for preferred in get_data_source_priority():
            if preferred == 'huawei' and HuaweiWaterDataService.enabled():
                raw_alerts = HuaweiWaterDataService.get_alerts(count=5)
                alerts = [DataTransformer.transform_alert(a, 'huawei') for a in raw_alerts]
                break
            if preferred == 'national' and NationalWaterDataService.enabled():
                raw_alerts = NationalWaterDataService.get_alerts(count=5)
                alerts = [DataTransformer.transform_alert(a, 'national') for a in raw_alerts]
                break
        else:
            alerts = []

    # 计算水质分布：来自 sensor_data_latest（SensorSnapshot），不依赖 count / hours
    water_quality_dist = {
        row['water_quality']: row['count']
        for row in snapshot_qs.exclude(water_quality__isnull=True)
        .values('water_quality')
        .annotate(count=Count('id'))
    }

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
                'avg_temperature': _round_agg(avg_agg.get('avg_temperature'), 1),
                'avg_ph': _round_agg(avg_agg.get('avg_ph'), 2),
                'avg_dissolved_oxygen': _round_agg(avg_agg.get('avg_dissolved_oxygen'), 2),
                'avg_conductivity': _round_agg(avg_agg.get('avg_conductivity'), 2),
                'avg_turbidity': _round_agg(avg_agg.get('avg_turbidity'), 2),
                'avg_permanganate_index': _round_agg(avg_agg.get('avg_permanganate'), 2),
                'avg_ammonia_nitrogen': _round_agg(avg_agg.get('avg_ammonia_nitrogen'), 2),
                'avg_total_phosphorus': _round_agg(avg_agg.get('avg_total_phosphorus'), 2),
                'avg_total_nitrogen': _round_agg(avg_agg.get('avg_total_nitrogen'), 2),
                'avg_chlorophyll_a': _round_agg(avg_agg.get('avg_chlorophyll_a'), 2),
                'avg_algae_density': _round_agg(avg_agg.get('avg_algae_density'), 2),
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
    manual_mode = get_data_source_mode() == 'manual'
    allowed_sources = get_allowed_sources()

    # 设备统计
    total_devices, online_devices, offline_devices = _get_device_counts_from_history(
        hours,
        manual_mode=manual_mode,
        allowed_sources=allowed_sources,
    )
    error_devices = 0

    # 告警统计
    alerts_qs = Alert.objects.filter(created_at__gte=time_threshold)
    if manual_mode:
        alerts_qs = alerts_qs.filter(data_source='manual')
    total_alerts = alerts_qs.count()
    resolved_alerts = alerts_qs.filter(resolved=True).count()
    pending_alerts = total_alerts - resolved_alerts

    # 按级别统计告警
    critical_alerts = alerts_qs.filter(
        created_at__gte=time_threshold,
        alert_level='critical',
        resolved=False
    ).count()
    warning_alerts = alerts_qs.filter(
        created_at__gte=time_threshold,
        alert_level='warning',
        resolved=False
    ).count()

    # 数据统计
    data_qs = SensorData.objects.filter(recorded_at__gte=time_threshold)
    if allowed_sources:
        data_qs = data_qs.filter(data_source__in=allowed_sources)
    data_count = data_qs.count()

    # 水质统计
    sensor_data_qs = SensorData.objects.filter(
        recorded_at__gte=time_threshold,
        water_quality__isnull=False
    )
    if allowed_sources:
        sensor_data_qs = sensor_data_qs.filter(data_source__in=allowed_sources)

    quality_distribution = {}
    quality_levels = ['Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', '劣Ⅴ']
    for quality in quality_levels:
        count = sensor_data_qs.filter(water_quality=quality).count()
        if count > 0:
            quality_distribution[quality] = count

    # 使用数据库数据计算平均值
    recent_data = SensorData.objects.filter(recorded_at__gte=time_threshold)
    if allowed_sources:
        recent_data = recent_data.filter(data_source__in=allowed_sources)
    recent_data = recent_data.aggregate(
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


@api_view(['POST'])
def ai_insight(request):
    """AI 智能洞察 - 基于当前水质数据生成建议"""
    payload = request.data or {}
    question = (payload.get('question') or '').strip()
    if not question:
        return Response({'code': 400, 'message': '请提供问题或需求描述'}, status=400)

    api_key = os.environ.get('BIGMODEL_API_KEY') or os.environ.get('ZHIPU_API_KEY')
    if not api_key:
        return Response(
            {'code': 400, 'message': '未配置 BIGMODEL_API_KEY/ZHIPU_API_KEY'},
            status=400
        )

    client_context = payload.get('context') or {}
    model = payload.get('model') or 'glm-4.7-flash'
    try:
        snapshot_context = _build_snapshot_ai_context()
        merged_context = {**client_context, **snapshot_context}
        answer = _call_bigmodel(api_key, model, question, merged_context)
    except RuntimeError as exc:
        logger.exception("AI insight failed (model=%s)", model)
        return Response({'code': 502, 'message': str(exc)}, status=502)

    return Response({
        'code': 200,
        'message': 'success',
        'data': {
            'answer': answer,
            'model': model
        }
    })


def _call_bigmodel(api_key, model, question, context):
    system_prompt = (
        "你是智慧渔业水质监控系统的AI助手，负责基于监测数据提供"
        "风险识别、异常解释、运维建议与可执行行动。"
        "上下文数据均来源于数据库表 sensor_data_latest（最新快照）。"
        "回答需简洁、可落地，分点给出结论与建议。"
    )
    payload = {
        'context': {
            'summary': context.get('summary'),
            'sensors': context.get('sensors'),
            'data_source': context.get('data_source'),
            'timestamp': context.get('timestamp'),
            'source_table': context.get('source_table'),
            'water_quality_distribution': context.get('water_quality_distribution'),
        },
        'question': question
    }
    messages = [
        {'role': 'system', 'content': system_prompt},
        {
            'role': 'user',
            'content': f"问题: {question}\n\n上下文数据(JSON):\n{json.dumps(payload['context'], ensure_ascii=False)}"
        }
    ]

    request_body = json.dumps({
        'model': model,
        'messages': messages,
        'max_tokens': 2048,
        'temperature': 0.3
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        data=request_body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            data = json.loads(raw.decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8') if exc.fp else str(exc)
        raise RuntimeError(f'AI服务响应异常(HTTP {exc.code}): {detail}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'AI服务连接失败: {exc.reason}') from exc

    choices = data.get('choices') or []
    if not choices:
        raise RuntimeError('AI服务未返回有效结果')
    message = choices[0].get('message') or {}
    return message.get('content', '').strip()


@api_view(['GET', 'POST'])
def data_source_settings(request):
    if request.method == 'POST':
        payload = request.data or {}
        mode = payload.get('mode')
        preference = set_data_source_mode(mode)
    else:
        preference = None

    current_mode = preference.mode if preference else get_data_source_mode()
    return Response({
        'code': 200,
        'message': 'success',
        'data': {
            'mode': current_mode,
                'availability': {
                    'national_enabled': NationalWaterDataService.enabled(),
                    'huawei_enabled': HuaweiWaterDataService.enabled(),
                }
        }
    })


def _get_device_counts_from_history(hours, manual_mode=False, allowed_sources=None):
    time_threshold = timezone.now() - timedelta(hours=hours)
    data_qs = SensorData.objects.filter(recorded_at__gte=time_threshold)
    if allowed_sources is None:
        allowed_sources = get_allowed_sources()
    if allowed_sources:
        data_qs = data_qs.filter(data_source__in=allowed_sources)
    if not data_qs.exists():
        return 0, 0, 0
    total = data_qs.values('station_id').distinct().count()
    online_threshold = timezone.now() - timedelta(hours=1)
    online = data_qs.filter(recorded_at__gte=online_threshold).values('station_id').distinct().count()
    offline = max(total - online, 0)
    return total, online, offline


def _build_snapshot_ai_context():
    """构建 AI 上下文：强制以 sensor_data_latest（SensorSnapshot）为准。"""
    snapshot_qs = SensorSnapshot.objects.exclude(station_id__isnull=True)
    allowed_sources = get_allowed_sources()
    if allowed_sources:
        snapshot_qs = snapshot_qs.filter(data_source__in=allowed_sources)

    latest_time = snapshot_qs.aggregate(max_time=Max('recorded_at')).get('max_time')
    now = timezone.now()
    online_threshold = now - timedelta(hours=1)

    total_devices = snapshot_qs.values('station_id').distinct().count()
    online_devices = snapshot_qs.filter(recorded_at__gte=online_threshold).values('station_id').distinct().count()
    offline_devices = max(total_devices - online_devices, 0)

    avg_agg = snapshot_qs.aggregate(
        avg_temperature=Avg('temperature'),
        avg_ph=Avg('ph'),
        avg_dissolved_oxygen=Avg('dissolved_oxygen'),
        avg_conductivity=Avg('conductivity'),
        avg_turbidity=Avg('turbidity'),
    )

    def _to_float(value, digits=2):
        if value is None:
            return None
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return None

    alert_count = snapshot_qs.filter(water_quality__in=POOR_WATER_QUALITIES).count()
    water_quality_dist = {
        row['water_quality']: row['count']
        for row in snapshot_qs.exclude(water_quality__isnull=True)
        .values('water_quality')
        .annotate(count=Count('id'))
    }

    risk_qs = snapshot_qs.filter(
        Q(water_quality__in=POOR_WATER_QUALITIES)
        | Q(dissolved_oxygen__lt=5)
        | Q(ph__lt=6.5)
        | Q(ph__gt=8.5)
    ).order_by('-recorded_at')[:200]

    rows = list(risk_qs.values(
        'station_id',
        'station_name',
        'province',
        'city',
        'river_basin',
        'water_quality',
        'temperature',
        'ph',
        'dissolved_oxygen',
        'conductivity',
        'turbidity',
        'recorded_at',
    ))

    def _risk_score(row):
        score = 0
        do = row.get('dissolved_oxygen')
        ph = row.get('ph')
        wq = row.get('water_quality')
        try:
            if do is not None and float(do) < 5:
                score += 3
        except (TypeError, ValueError):
            pass
        try:
            if ph is not None:
                phf = float(ph)
                if phf < 6.5 or phf > 8.5:
                    score += 2
        except (TypeError, ValueError):
            pass
        if wq in ['Ⅴ', '劣Ⅴ', 'Ⅴ类', '劣Ⅴ类', '劣V', '劣V类']:
            score += 4
        elif wq in ['Ⅳ', 'Ⅳ类']:
            score += 3
        elif wq in ['Ⅲ', 'Ⅲ类']:
            score += 2
        return score

    for row in rows:
        row['risk_score'] = _risk_score(row)
        recorded_at = row.get('recorded_at')
        row['timestamp'] = recorded_at.isoformat() if recorded_at else None
        row['temperature'] = _to_float(row.get('temperature'), 2)
        row['ph'] = _to_float(row.get('ph'), 2)
        row['dissolved_oxygen'] = _to_float(row.get('dissolved_oxygen'), 2)
        row['conductivity'] = _to_float(row.get('conductivity'), 2)
        row['turbidity'] = _to_float(row.get('turbidity'), 2)
        row.pop('recorded_at', None)

    rows.sort(key=lambda r: (r.get('risk_score', 0), r.get('timestamp') or ''), reverse=True)

    return {
        'source_table': 'sensor_data_latest',
        'timestamp': (latest_time or now).isoformat(),
        'data_source': 'database',
        'summary': {
            'total_devices': total_devices,
            'online_devices': online_devices,
            'offline_devices': offline_devices,
            'alert_count': alert_count,
            'avg_temperature': _to_float(avg_agg.get('avg_temperature'), 2),
            'avg_ph': _to_float(avg_agg.get('avg_ph'), 2),
            'avg_dissolved_oxygen': _to_float(avg_agg.get('avg_dissolved_oxygen'), 2),
            'avg_conductivity': _to_float(avg_agg.get('avg_conductivity'), 2),
            'avg_turbidity': _to_float(avg_agg.get('avg_turbidity'), 2),
        },
        'water_quality_distribution': water_quality_dist,
        'sensors': rows[:20],
    }
