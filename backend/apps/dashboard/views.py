"""
数据看板视图 - 使用真实统计数据
"""
import json
import os
import logging
import time
import requests
import re

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Avg, Count, Max, Q
from django.utils import timezone
from datetime import timedelta

from apps.sensors.models import SensorData, SensorSnapshot, Alert
from apps.dashboard.models import AiInsightLog
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

SMALLTALK_KEYWORDS = {
    'hello', 'hi', 'hey',
    '你好', '您好', '在吗', '在么', '在不在',
    '哈喽', '嗨',
}

PROVINCE_ALIASES = {
    '山西': '山西省',
    '北京': '北京市',
    '天津': '天津市',
    '上海': '上海市',
    '重庆': '重庆市',
}


def _extract_province_focus(question: str) -> str | None:
    """从问题中提取省份/直辖市（用于定向补充上下文），返回规范名称。"""
    if not question:
        return None
    text = question.strip()
    if not text:
        return None
    m = re.search(r'([一-龥]{2,4})(省|市|自治区)', text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    for short, full in PROVINCE_ALIASES.items():
        if short in text:
            return full
    return None


def _safe_create_ai_log(
    *,
    question: str,
    answer: str | None,
    model: str | None,
    success: bool,
    error_message: str | None,
    request_payload: dict | None,
    response_meta: dict | None,
    request,
    duration_ms: int | None,
):
    try:
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or None
        user_agent = request.META.get('HTTP_USER_AGENT') or None
        AiInsightLog.objects.create(
            question=question,
            answer=answer,
            model=model,
            success=success,
            error_message=error_message,
            request_payload=request_payload,
            response_meta=response_meta,
            ip_address=client_ip,
            user_agent=user_agent,
            duration_ms=duration_ms,
        )
    except Exception:
        logger.warning("Failed to persist AiInsightLog", exc_info=True)


def _build_ai_log_payload(context: dict) -> dict:
    sensors = context.get('sensors') or []
    province_sensors = context.get('province_sensors') or []
    return {
        'timestamp': context.get('timestamp'),
        'data_source': context.get('data_source'),
        'source_table': context.get('source_table'),
        'summary': context.get('summary'),
        'province_focus': context.get('province_focus'),
        'ctx_sensors_station_ids': [s.get('station_id') for s in sensors if isinstance(s, dict) and s.get('station_id')][:50],
        'province_sensors_station_ids': [
            s.get('station_id') for s in province_sensors if isinstance(s, dict) and s.get('station_id')
        ][:50],
    }


def _is_smalltalk(question: str) -> bool:
    if not question:
        return False
    normalized = ''.join(question.strip().lower().split())
    if not normalized:
        return False
    if normalized in SMALLTALK_KEYWORDS:
        return True
    if normalized in {'hello!', 'hi!', 'hey!'}:
        return True
    return False


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
    # 告警列表：基于 sensor_data_latest（SensorSnapshot）即时规则生成，不触发外部抓取
    alerts = _build_snapshot_rule_alerts(snapshot_qs, limit=5)

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

    client_context = payload.get('context') or {}
    model = payload.get('model') or 'glm-4.7'
    t0 = time.monotonic()
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or '-'
    logger.info(
        "AI insight request (model=%s q_len=%s ip=%s)",
        model,
        len(question),
        client_ip,
    )
    try:
        snapshot_context = _build_snapshot_ai_context()
        t1 = time.monotonic()
        merged_context = {**client_context, **snapshot_context}

        # 若问题包含某省/市，补充该区域的快照样本，避免模型基于小样本误判“没有数据”
        province_focus = _extract_province_focus(question)
        if province_focus:
            merged_context['province_focus'] = province_focus
            merged_context['province_sensors'] = _get_snapshot_samples_by_province(province_focus, limit=20)

        if _is_smalltalk(question):
            summary = merged_context.get('summary') or {}
            ts = merged_context.get('timestamp') or ''
            quick_answer = (
                "你好，我是智慧渔业水质监控系统的AI助手。\n"
                f"- 数据时间：{ts or '未知'}\n"
                f"- 监测断面：{summary.get('total_devices', 0)}\n"
                f"- 在线监测：{summary.get('online_devices', 0)}\n"
                f"- 未恢复告警：{summary.get('alert_count', 0)}\n\n"
                "你可以直接问我：哪些断面风险最高？需要如何处理？我会基于最新快照给出建议。"
            )
            logger.info(
                "AI insight smalltalk served locally (build_ctx=%.3fs total=%.3fs)",
                (t1 - t0),
                (time.monotonic() - t0),
            )
            _safe_create_ai_log(
                question=question,
                answer=quick_answer,
                model='local',
                success=True,
                error_message=None,
                request_payload={'question': question, 'context': _build_ai_log_payload(merged_context)},
                response_meta={'source': 'local'},
                request=request,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
            return Response({'code': 200, 'message': 'success', 'data': {'answer': quick_answer, 'model': 'local'}})

        api_key = os.environ.get('BIGMODEL_API_KEY') or os.environ.get('ZHIPU_API_KEY')
        if not api_key:
            logger.warning(
                "AI insight blocked: missing BIGMODEL_API_KEY/ZHIPU_API_KEY (build_ctx=%.3fs total=%.3fs)",
                (t1 - t0),
                (time.monotonic() - t0),
            )
            _safe_create_ai_log(
                question=question,
                answer=None,
                model=model,
                success=False,
                error_message='未配置 BIGMODEL_API_KEY/ZHIPU_API_KEY',
                request_payload={'question': question, 'context': _build_ai_log_payload(merged_context)},
                response_meta={'source': 'blocked'},
                request=request,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
            return Response(
                {'code': 400, 'message': '未配置 BIGMODEL_API_KEY/ZHIPU_API_KEY'},
                status=400
            )

        t2 = time.monotonic()
        answer = _call_bigmodel(api_key, model, question, merged_context)
        t3 = time.monotonic()
        logger.info(
            "AI insight ok (model=%s build_ctx=%.3fs call_model=%.3fs total=%.3fs ctx_sensors=%s)",
            model,
            (t1 - t0),
            (t3 - t2),
            (t3 - t0),
            len((merged_context.get('sensors') or [])),
        )
        _safe_create_ai_log(
            question=question,
            answer=answer,
            model=model,
            success=True,
            error_message=None,
            request_payload={'question': question, 'context': _build_ai_log_payload(merged_context)},
            response_meta={'source': 'bigmodel'},
            request=request,
            duration_ms=int((t3 - t0) * 1000),
        )
    except RuntimeError as exc:
        logger.info(
            "AI insight failed timing (model=%s elapsed=%.3fs)",
            model,
            (time.monotonic() - t0),
        )
        logger.exception("AI insight failed (model=%s)", model)
        _safe_create_ai_log(
            question=question,
            answer=None,
            model=model,
            success=False,
            error_message=str(exc),
            request_payload={'question': question},
            response_meta={'source': 'bigmodel'},
            request=request,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
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
        "你是智慧渔业水质监控系统的AI助手，负责基于监测数据提供风险识别、异常解释、运维建议与可执行行动。\n"
        "数据来源与约束：\n"
        "1) 你只能基于我提供的上下文 JSON（来自数据库表 sensor_data_latest 的最新快照）做判断；不得编造不存在的站点/省份/指标。\n"
        "2) 上下文中的 sensors 可能是抽样/Top 列表；如果未看到某省数据，不允许断言“数据库没有”，只能说“本次样本未覆盖/未看到”。\n"
        "3) 若提供 province_focus/province_sensors：必须优先用 province_sensors 做该省结论；若 province_sensors 为空，只能说“当前快照查询未覆盖该省（或该省样本为空）”，并建议刷新数据/检查筛选条件。\n"
        "输出要求：\n"
        "- 先给出【结论】（2-4条要点），再给出【依据】（引用上下文里的关键指标/站点），最后给出【建议】（可执行、分点）。\n"
    )
    payload = {
        'context': {
            'summary': context.get('summary'),
            'sensors': context.get('sensors'),
            'province_focus': context.get('province_focus'),
            'province_sensors': context.get('province_sensors'),
            'data_source': context.get('data_source'),
            'timestamp': context.get('timestamp'),
            'source_table': context.get('source_table'),
            'water_quality_distribution': context.get('water_quality_distribution'),
            'province_distribution': context.get('province_distribution'),
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

    try:
        max_tokens = int(os.environ.get('BIGMODEL_MAX_TOKENS', '1024'))
    except (TypeError, ValueError):
        max_tokens = 1024

    try:
        timeout_seconds = int(os.environ.get('BIGMODEL_TIMEOUT_SECONDS', '30'))
    except (TypeError, ValueError):
        timeout_seconds = 30

    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
        "temperature": 0.3
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
            logger.info(
                "BigModel API status=%s log_id=%s",
                response.status_code,
                response.headers.get("x-log-id") or response.headers.get("X-Log-Id") or "-",
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                sleep_seconds = None
                if retry_after:
                    try:
                        sleep_seconds = max(float(retry_after), 0.0)
                    except (TypeError, ValueError):
                        sleep_seconds = None
                if sleep_seconds is None:
                    sleep_seconds = 1.0 + attempt * 1.5
                if attempt < max_attempts - 1:
                    time.sleep(min(sleep_seconds, 10.0))
                    continue
                raise RuntimeError(f'AI服务触发限流(HTTP 429)，请稍后再试: {response.text}')

            if 500 <= response.status_code < 600 and attempt < max_attempts - 1:
                time.sleep(0.8 + attempt * 0.6)
                continue

            if response.status_code != 200:
                raise RuntimeError(f'AI服务响应异常(HTTP {response.status_code}): {response.text}')
            data = response.json()
            break
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f'AI服务连接失败: {exc}') from exc
        except requests.exceptions.Timeout as exc:
            if attempt < max_attempts - 1:
                time.sleep(0.8 + attempt * 0.6)
                continue
            raise RuntimeError(f'AI服务响应超时({timeout_seconds}s)') from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f'AI服务请求失败: {exc}') from exc
        except RuntimeError:
            raise
    else:
        raise RuntimeError(f'AI服务响应超时({timeout_seconds}s)')

    choices = data.get('choices') or []
    if not choices:
        raise RuntimeError('AI服务未返回有效结果')

    def _extract_content(choice):
        if not isinstance(choice, dict):
            return ''
        message = choice.get('message')
        if isinstance(message, dict):
            content = message.get('content')
            if isinstance(content, str) and content.strip():
                return content.strip()
            reasoning_content = message.get('reasoning_content')
            if isinstance(reasoning_content, str) and reasoning_content.strip():
                return reasoning_content.strip()
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(item)
                        continue
                    if isinstance(item, dict):
                        parts.append(str(item.get('text') or item.get('content') or ''))
                return '\n'.join([p for p in parts if p]).strip()
            for key in ('final', 'answer', 'result', 'reasoning', 'reasoning_content'):
                value = message.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        text = choice.get('text')
        if isinstance(text, str):
            return text.strip()
        return ''

    answer = _extract_content(choices[0])
    if not answer:
        choice0 = choices[0] if isinstance(choices[0], dict) else {}
        message0 = choice0.get('message') if isinstance(choice0, dict) else None
        logger.warning(
            "BigModel returned empty content (data_keys=%s choice_keys=%s message_keys=%s)",
            list(data.keys()) if isinstance(data, dict) else type(data),
            list(choice0.keys()) if isinstance(choice0, dict) else type(choice0),
            list(message0.keys()) if isinstance(message0, dict) else type(message0),
        )
        raise RuntimeError('AI服务返回空内容，请稍后重试')

    return answer


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
    # AI 上下文：只基于本地快照表，不触发外部抓取；不再按数据源过滤，避免误漏省份数据

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

    province_dist = {
        row['province']: row['count']
        for row in snapshot_qs.exclude(province__isnull=True)
        .exclude(province__exact='')
        .values('province')
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
        'province_distribution': province_dist,
        'sensors': rows[:20],
    }


def _get_snapshot_samples_by_province(province: str, limit: int = 20):
    if not province or limit <= 0:
        return []
    snapshot_qs = SensorSnapshot.objects.exclude(station_id__isnull=True).filter(province__icontains=province)
    latest_qs = snapshot_qs.order_by('-recorded_at')[:limit]
    rows = list(latest_qs.values(
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

    def _to_float(value, digits=2):
        if value is None:
            return None
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return None

    for row in rows:
        recorded_at = row.get('recorded_at')
        row['timestamp'] = recorded_at.isoformat() if recorded_at else None
        row['water_quality'] = DataTransformer.normalize_water_quality(row.get('water_quality'))
        row['temperature'] = _to_float(row.get('temperature'), 2)
        row['ph'] = _to_float(row.get('ph'), 2)
        row['dissolved_oxygen'] = _to_float(row.get('dissolved_oxygen'), 2)
        row['conductivity'] = _to_float(row.get('conductivity'), 2)
        row['turbidity'] = _to_float(row.get('turbidity'), 2)
        row.pop('recorded_at', None)

    return rows


def _build_snapshot_rule_alerts(snapshot_qs, limit=5):
    """基于快照表即时生成告警列表（不触发外部接口）。"""
    if limit <= 0:
        return []

    # 筛选满足任一规则的断面（取最近一批，避免全表扫描）
    rule_qs = snapshot_qs.filter(
        Q(water_quality__in=POOR_WATER_QUALITIES)
        | Q(temperature__gt=30)
        | Q(dissolved_oxygen__lt=5)
        | Q(ph__lt=6.5)
        | Q(ph__gt=8.5)
    ).order_by('-recorded_at')[:200]

    alerts = []
    for record in rule_qs:
        station_id = record.station_id
        station_name = record.station_name
        created_at = record.recorded_at.isoformat() if record.recorded_at else timezone.now().isoformat()

        wq = DataTransformer.normalize_water_quality(record.water_quality)
        if wq in ['Ⅳ', 'Ⅴ', '劣Ⅴ', 'Ⅳ类', 'Ⅴ类', '劣Ⅴ类', '劣V', '劣V类']:
            level = 'critical' if wq in ['劣Ⅴ', '劣Ⅴ类', '劣V', '劣V类'] else 'warning'
            raw = {
                'station_id': station_id,
                'station_name': station_name,
                'type': 'water_quality',
                'level': level,
                'message': f'水质{wq}',
                # DataTransformer.transform_alert 会把 value 转 Decimal；水质类为字符串，避免传入导致报错
                'value': None,
                'timestamp': created_at,
            }
            alerts.append(DataTransformer.transform_alert(raw, 'database'))

        if record.temperature is not None:
            try:
                if float(record.temperature) > 30:
                    raw = {
                        'station_id': station_id,
                        'station_name': station_name,
                        'type': 'temperature',
                        'level': 'warning',
                        'message': '水温偏高',
                        'value': float(record.temperature),
                        'value_unit': '℃',
                        'timestamp': created_at,
                    }
                    alerts.append(DataTransformer.transform_alert(raw, 'database'))
            except (TypeError, ValueError):
                pass

        if record.dissolved_oxygen is not None:
            try:
                if float(record.dissolved_oxygen) < 5:
                    raw = {
                        'station_id': station_id,
                        'station_name': station_name,
                        'type': 'dissolved_oxygen',
                        'level': 'warning',
                        'message': '溶解氧偏低',
                        'value': float(record.dissolved_oxygen),
                        'value_unit': 'mg/L',
                        'timestamp': created_at,
                    }
                    alerts.append(DataTransformer.transform_alert(raw, 'database'))
            except (TypeError, ValueError):
                pass

        if record.ph is not None:
            try:
                ph_value = float(record.ph)
                if ph_value < 6.5 or ph_value > 8.5:
                    raw = {
                        'station_id': station_id,
                        'station_name': station_name,
                        'type': 'ph',
                        'level': 'warning',
                        'message': 'pH异常',
                        'value': ph_value,
                        'timestamp': created_at,
                    }
                    alerts.append(DataTransformer.transform_alert(raw, 'database'))
            except (TypeError, ValueError):
                pass

        if len(alerts) >= limit:
            break

    # 优先 critical，再按时间倒序（created_at 为字符串，按 ISO 处理）
    level_rank = {'critical': 0, 'warning': 1, 'info': 2}
    alerts.sort(
        key=lambda a: (
            level_rank.get(a.get('alert_level'), 9),
            a.get('created_at') or '',
        ),
        reverse=False,
    )
    return alerts[:limit]
