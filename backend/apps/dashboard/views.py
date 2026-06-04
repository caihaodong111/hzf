"""
数据看板视图 - 使用真实统计数据
"""
import json
import os
import logging
import time
import requests
import re
from typing import Any

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import StreamingHttpResponse
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

PROVINCE_ALIASES = {
    '山西': '山西省',
    '北京': '北京市',
    '天津': '天津市',
    '上海': '上海市',
    '重庆': '重庆市',
}

SMALLTALK_KEYWORDS = {
    'hello', 'hi', 'hey',
    '你好', '您好', '哈喽', '嗨',
    '在吗', '在么',
    'help', '帮助', '怎么用', '如何使用',
}

DEFAULT_BIGMODEL_MODEL = (
    os.environ.get('MODELSCOPE_MODEL')
    or os.environ.get('SILICONFLOW_MODEL')
    or 'moonshotai/Kimi-K2.5'
)
BIGMODEL_API_URL = (
    os.environ.get('MODELSCOPE_API_URL')
    or os.environ.get('SILICONFLOW_API_URL')
    or 'https://api-inference.modelscope.cn/v1/chat/completions'
)
AI_PROVIDER_SOURCE = (os.environ.get('AI_PROVIDER_SOURCE') or 'modelscope').strip().lower()
BIGMODEL_SYSTEM_PROMPT = (
    "你是智慧渔业水质监控系统的AI助手，负责基于监测数据提供风险识别、异常解释、运维建议与可执行行动。\n"
    "数据来源与约束：\n"
    "1) 你只能基于我提供的上下文 JSON（来自数据库表 sensor_data_latest 的最新快照）做判断；不得编造不存在的站点/省份/指标。\n"
    "2) 上下文中的 sensors 可能是抽样/Top 列表；如果未看到某省数据，不允许断言“数据库没有”，只能说“本次样本未覆盖/未看到”。\n"
    "3) 若提供 province_focus/province_sensors：必须优先用 province_sensors 做该省结论；若 province_sensors 为空，只能说“当前快照查询未覆盖该省（或该省样本为空）”，并建议刷新数据/检查筛选条件。\n"
    "4) 按用户问题类型直接作答，不要把所有问题都写成同一个模板；优先引用具体站点、具体指标、具体时间。\n"
    "5) 严禁输出任何思考过程、推理标签、占位符、控制 token、JSON、Markdown 代码块；只输出完整可读的最终回答。\n"
    "6) 若上下文证据不足，明确说证据不足，不要虚构阈值判断。\n"
    "输出要求：\n"
    "- 先给出【结论】（2-4条要点），再给出【依据】（引用上下文里的关键指标/站点），最后给出【建议】（可执行、分点）。\n"
    "- 最后一行必须是明确的处置建议或结论句，不能半句收尾。\n"
)
SMALLTALK_SYSTEM_PROMPT = (
    "你是智慧渔业水质监控系统的AI助手。\n"
    "当用户是在打招呼、确认你是否在线、或询问你能做什么时，用自然、简短、友好的中文直接回答。\n"
    "不要套用【结论】【依据】【建议】模板，不要引用监测数据，不要假装在做水质研判。\n"
    "如果用户是在问“怎么用/能做什么”，简要说明你可以帮助解读水质风险、定位异常断面、总结监测结论和给出处置建议。\n"
)

INLINE_PLACEHOLDER_PATTERNS = [
    re.compile(r'\{\{[^{}\n]{1,80}\}\}'),
    re.compile(r'【(?:待补充|占位符|placeholder)[^】]{0,80}】', re.IGNORECASE),
    re.compile(r'\[(?:待补充|占位符|placeholder|todo|tbd)[^\]]{0,80}\]', re.IGNORECASE),
    re.compile(r'（(?:待补充|占位符|placeholder|todo|tbd|请替换)[^）]{0,80}）', re.IGNORECASE),
]


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_float(value, digits=2):
    numeric = _safe_float(value)
    if numeric is None:
        return None
    return round(numeric, digits)


def _truncate_for_log(text: str | None, limit: int = 240) -> str:
    if not text:
        return ''
    cleaned = ' '.join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit - 3]}..."


def _compute_risk_score(row: dict[str, Any]) -> int:
    score = 0
    do = _safe_float(row.get('dissolved_oxygen'))
    ph = _safe_float(row.get('ph'))
    wq = DataTransformer.normalize_water_quality(row.get('water_quality'))
    if do is not None and do < 5:
        score += 3
    if ph is not None and (ph < 6.5 or ph > 8.5):
        score += 2
    if wq in ['Ⅴ', '劣Ⅴ', 'Ⅴ类', '劣Ⅴ类', '劣V', '劣V类']:
        score += 4
    elif wq in ['Ⅳ', 'Ⅳ类']:
        score += 3
    elif wq in ['Ⅲ', 'Ⅲ类']:
        score += 2
    return score


def _normalize_snapshot_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metric_digits = {
        'temperature': 2,
        'ph': 2,
        'dissolved_oxygen': 2,
        'conductivity': 2,
        'turbidity': 2,
        'permanganate': 3,
        'ammonia_nitrogen': 3,
        'total_phosphorus': 3,
        'total_nitrogen': 3,
        'chlorophyll_a': 3,
        'algae_density': 2,
    }
    for row in rows:
        row['water_quality'] = DataTransformer.normalize_water_quality(row.get('water_quality'))
        row['risk_score'] = _compute_risk_score(row)
        recorded_at = row.get('recorded_at')
        row['timestamp'] = recorded_at.isoformat() if recorded_at else None
        for field, digits in metric_digits.items():
            row[field] = _round_float(row.get(field), digits)
        row.pop('recorded_at', None)
    rows.sort(key=lambda r: (r.get('risk_score', 0), r.get('timestamp') or ''), reverse=True)
    return rows


def _summarize_ai_signals(sensors: list[dict[str, Any]]) -> dict[str, Any]:
    low_do_count = 0
    abnormal_ph_count = 0
    high_temperature_count = 0
    poor_quality_count = 0
    nutrient_sample_count = 0

    for sensor in sensors:
        do = _safe_float(sensor.get('dissolved_oxygen'))
        ph = _safe_float(sensor.get('ph'))
        temperature = _safe_float(sensor.get('temperature'))
        water_quality = sensor.get('water_quality')
        if do is not None and do < 5:
            low_do_count += 1
        if ph is not None and (ph < 6.5 or ph > 8.5):
            abnormal_ph_count += 1
        if temperature is not None and temperature > 30:
            high_temperature_count += 1
        if water_quality in POOR_WATER_QUALITIES:
            poor_quality_count += 1
        if any(
            _safe_float(sensor.get(field)) is not None
            for field in ('total_phosphorus', 'total_nitrogen', 'chlorophyll_a', 'algae_density')
        ):
            nutrient_sample_count += 1

    top_risk_stations = []
    for sensor in sorted(sensors, key=lambda item: item.get('risk_score', 0), reverse=True)[:5]:
        top_risk_stations.append({
            'station_id': sensor.get('station_id'),
            'station_name': sensor.get('station_name'),
            'water_quality': sensor.get('water_quality'),
            'risk_score': sensor.get('risk_score'),
            'dissolved_oxygen': sensor.get('dissolved_oxygen'),
            'ph': sensor.get('ph'),
            'temperature': sensor.get('temperature'),
            'total_phosphorus': sensor.get('total_phosphorus'),
            'total_nitrogen': sensor.get('total_nitrogen'),
            'chlorophyll_a': sensor.get('chlorophyll_a'),
            'algae_density': sensor.get('algae_density'),
            'timestamp': sensor.get('timestamp'),
        })

    return {
        'sample_size': len(sensors),
        'poor_quality_count': poor_quality_count,
        'low_do_count': low_do_count,
        'abnormal_ph_count': abnormal_ph_count,
        'high_temperature_count': high_temperature_count,
        'nutrient_sample_count': nutrient_sample_count,
        'top_risk_stations': top_risk_stations,
    }


def _build_question_profile(question: str) -> dict[str, Any]:
    text = question or ''
    normalized = text.lower()
    smalltalk_text = re.sub(r'[\s\W_]+', '', normalized, flags=re.UNICODE)
    smalltalk_keywords = {
        re.sub(r'[\s\W_]+', '', keyword.lower(), flags=re.UNICODE)
        for keyword in SMALLTALK_KEYWORDS
    }
    if smalltalk_text and smalltalk_text in smalltalk_keywords:
        intent = 'smalltalk'
        output_hint = '自然简短回答，不要套用水质研判模板。'
    elif any(keyword in text for keyword in ('日报', '周报', '简报', '汇总', '摘要')):
        intent = 'report'
        output_hint = '用简报风格回答，突出总体状态、重点风险与当班建议。'
    elif any(keyword in text for keyword in ('优先', '排序', '风险最高', '重点处理', '哪些断面', '排名')):
        intent = 'prioritize'
        output_hint = '优先输出高风险断面排序，并说明为什么要先处理。'
    elif any(keyword in text for keyword in ('富营养化', '叶绿素', '藻', '总磷', '总氮')):
        intent = 'eutrophication'
        output_hint = '优先分析营养盐、叶绿素a、藻密度相关信号，并说明是否足以支持富营养化判断。'
    elif any(keyword in text for keyword in ('增氧', '溶解氧', '缺氧')):
        intent = 'oxygen'
        output_hint = '优先分析溶解氧风险与增氧处置顺序。'
    else:
        intent = 'general'
        output_hint = '按问题直接作答，不要套用空泛模板。'

    focus_metrics = []
    keyword_metric_map = {
        '溶解氧': 'dissolved_oxygen',
        '增氧': 'dissolved_oxygen',
        '缺氧': 'dissolved_oxygen',
        'pH': 'ph',
        '酸碱': 'ph',
        '水温': 'temperature',
        '温度': 'temperature',
        '浊度': 'turbidity',
        '电导率': 'conductivity',
        '总磷': 'total_phosphorus',
        '总氮': 'total_nitrogen',
        '叶绿素': 'chlorophyll_a',
        '藻': 'algae_density',
        '富营养化': 'eutrophication',
    }
    for keyword, metric in keyword_metric_map.items():
        if keyword.lower() in normalized or keyword in text:
            focus_metrics.append(metric)
    if intent == 'smalltalk':
        focus_metrics = []
    elif not focus_metrics:
        focus_metrics = ['water_quality', 'dissolved_oxygen', 'ph']

    return {
        'intent': intent,
        'focus_metrics': list(dict.fromkeys(focus_metrics)),
        'output_hint': output_hint,
    }


def _is_placeholder_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.fullmatch(r'[-*•]+', stripped):
        return True
    if re.fullmatch(r'[\[{(（【<][^\n]{0,80}(?:待补充|待填写|占位符|placeholder|todo|tbd)[^\n]{0,80}[\]})）】>]', stripped, re.IGNORECASE):
        return True
    if re.fullmatch(r'(?:待补充|待填写|占位符|placeholder|todo|tbd)[：:\- ]?.*', stripped, re.IGNORECASE):
        return True
    return False


def _clean_ai_output(text: str | None) -> tuple[str, dict[str, Any]]:
    original = text or ''
    cleaned = original.replace('\r\n', '\n').replace('\r', '\n')
    cleaned = re.sub(r'<(think|analysis|reasoning)>.*?</\1>', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r'<\|[^>\n]+\|>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r'(?is)(?:^|\n)(?:#+\s*)?(?:思考过程|推理过程|分析过程|reasoning|thinking)[：:]\s*.*?(?=\n(?:#+\s*)?(?:结论|回答|建议|【结论】|【依据】|【建议】)|\Z)',
        '\n',
        cleaned,
    )

    inline_placeholder_hits = 0
    for pattern in INLINE_PLACEHOLDER_PATTERNS:
        cleaned, hits = pattern.subn('', cleaned)
        inline_placeholder_hits += hits

    filtered_lines = []
    placeholder_line_hits = 0
    for line in cleaned.split('\n'):
        if _is_placeholder_line(line):
            placeholder_line_hits += 1
            continue
        filtered_lines.append(line.rstrip())

    cleaned = '\n'.join(filtered_lines)
    cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
    cleaned = cleaned.strip()

    return cleaned, {
        'original_length': len(original),
        'cleaned_length': len(cleaned),
        'placeholder_hits': inline_placeholder_hits + placeholder_line_hits,
    }


def _looks_truncated(text: str, finish_reason: str | None) -> bool:
    if finish_reason in {'length', 'max_tokens'}:
        return True
    stripped = (text or '').rstrip()
    if len(stripped) < 32:
        return False
    if stripped.endswith(('【', '[', '(', '（', '，', ',', '：', ':', '；', ';', '和', '及', '并', '-', '—')):
        return True
    if stripped.endswith(('...', '……')):
        return True
    return False


def _collect_text_parts(value) -> tuple[list[str], list[str]]:
    final_parts = []
    reasoning_parts = []
    if isinstance(value, str):
        if value.strip():
            final_parts.append(value.strip())
        return final_parts, reasoning_parts
    if not isinstance(value, list):
        return final_parts, reasoning_parts
    for item in value:
        if isinstance(item, str):
            if item.strip():
                final_parts.append(item.strip())
            continue
        if not isinstance(item, dict):
            continue
        text = item.get('text') or item.get('content') or item.get('output_text') or item.get('value')
        if not isinstance(text, str) or not text.strip():
            continue
        item_type = str(item.get('type') or item.get('role') or '').lower()
        if any(token in item_type for token in ('reason', 'thinking', 'thought')):
            reasoning_parts.append(text.strip())
        else:
            final_parts.append(text.strip())
    return final_parts, reasoning_parts


def _join_unique_parts(parts: list[str]) -> str:
    merged = []
    seen = set()
    for part in parts:
        normalized = part.strip()
        if not normalized or normalized in seen:
            continue
        merged.append(normalized)
        seen.add(normalized)
    return '\n'.join(merged).strip()


def _extract_bigmodel_result(data, *, finish_reason=None, log_id=None, attempts=1, token_budget=None):
    choices = data.get('choices') or []
    if not choices:
        raise RuntimeError('AI服务未返回有效结果')

    choice0 = choices[0] if isinstance(choices[0], dict) else {}
    message0 = choice0.get('message') if isinstance(choice0, dict) else None

    final_parts = []
    reasoning_parts = []

    if isinstance(message0, dict):
        parts, thinking_parts = _collect_text_parts(message0.get('content'))
        final_parts.extend(parts)
        reasoning_parts.extend(thinking_parts)

        for key in ('final', 'answer', 'result'):
            value = message0.get(key)
            parts, thinking_parts = _collect_text_parts(value)
            final_parts.extend(parts)
            reasoning_parts.extend(thinking_parts)
            if isinstance(value, str) and value.strip():
                final_parts.append(value.strip())

        for key in ('reasoning_content', 'reasoning'):
            value = message0.get(key)
            if isinstance(value, str) and value.strip():
                reasoning_parts.append(value.strip())
            else:
                _, thinking_parts = _collect_text_parts(value)
                reasoning_parts.extend(thinking_parts)

    text = choice0.get('text') if isinstance(choice0, dict) else None
    if isinstance(text, str) and text.strip():
        final_parts.append(text.strip())

    answer_raw = _join_unique_parts(final_parts)
    reasoning_raw = _join_unique_parts(reasoning_parts)
    answer, answer_clean_meta = _clean_ai_output(answer_raw)
    reasoning, reasoning_clean_meta = _clean_ai_output(reasoning_raw)
    final_finish_reason = finish_reason or choice0.get('finish_reason')

    return {
        'answer': answer,
        'reasoning': reasoning,
        'answer_raw': answer_raw,
        'reasoning_raw': reasoning_raw,
        'finish_reason': final_finish_reason,
        'usage': data.get('usage'),
        'attempts': attempts,
        'token_budget': token_budget,
        'truncated': _looks_truncated(answer, final_finish_reason),
        'answer_clean_meta': answer_clean_meta,
        'reasoning_clean_meta': reasoning_clean_meta,
        'choice_keys': list(choice0.keys()) if isinstance(choice0, dict) else [],
        'message_keys': list(message0.keys()) if isinstance(message0, dict) else [],
        'log_id': log_id,
    }


def _build_bigmodel_context_payload(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    question_profile = context.get('question_profile') or {}
    intent = question_profile.get('intent') or 'general'
    try:
        sensor_limit = int(os.environ.get('BIGMODEL_SENSOR_LIMIT', '0'))
    except (TypeError, ValueError):
        sensor_limit = 0
    if sensor_limit <= 0:
        sensor_limit = {
            'report': 10,
            'prioritize': 10,
            'eutrophication': 8,
            'oxygen': 8,
            'general': 8,
        }.get(intent, 8)

    try:
        province_sensor_limit = int(os.environ.get('BIGMODEL_PROVINCE_SENSOR_LIMIT', '0'))
    except (TypeError, ValueError):
        province_sensor_limit = 0
    if province_sensor_limit <= 0:
        province_sensor_limit = min(sensor_limit, 8)

    base_fields = ['station_id', 'station_name', 'province', 'city', 'water_quality', 'risk_score', 'timestamp']
    focus_map = {
        'dissolved_oxygen': ['dissolved_oxygen'],
        'ph': ['ph'],
        'temperature': ['temperature'],
        'turbidity': ['turbidity'],
        'conductivity': ['conductivity'],
        'total_phosphorus': ['total_phosphorus'],
        'total_nitrogen': ['total_nitrogen'],
        'chlorophyll_a': ['chlorophyll_a'],
        'algae_density': ['algae_density'],
        'eutrophication': ['total_phosphorus', 'total_nitrogen', 'chlorophyll_a', 'algae_density'],
    }

    fields = list(base_fields)
    for metric in question_profile.get('focus_metrics') or []:
        for field in focus_map.get(metric, [metric]):
            if field not in fields:
                fields.append(field)
    for common_field in ('dissolved_oxygen', 'ph', 'temperature'):
        if common_field not in fields:
            fields.append(common_field)

    required_fields = {'station_id', 'station_name', 'water_quality', 'risk_score', 'timestamp'}

    def _compact_rows(rows: list[dict[str, Any]], limit: int):
        compact = []
        for row in (rows or [])[:limit]:
            item = {}
            for field in fields:
                value = row.get(field)
                if value is None and field not in required_fields:
                    continue
                item[field] = value
            compact.append(item)
        return compact

    compact_sensors = _compact_rows(context.get('sensors') or [], sensor_limit)
    compact_province_sensors = _compact_rows(context.get('province_sensors') or [], province_sensor_limit)
    payload = {
        'summary': context.get('summary'),
        'data_source': context.get('data_source'),
        'timestamp': context.get('timestamp'),
        'source_table': context.get('source_table'),
        'province_focus': context.get('province_focus'),
        'water_quality_distribution': context.get('water_quality_distribution'),
        'province_distribution': context.get('province_distribution'),
        'risk_signal_summary': context.get('risk_signal_summary'),
        'focus_signal_summary': context.get('focus_signal_summary'),
        'question_profile': question_profile,
        'sensors': compact_sensors,
        'province_sensors': compact_province_sensors,
    }
    stats = {
        'sensor_count': len(compact_sensors),
        'province_sensor_count': len(compact_province_sensors),
        'sensor_limit': sensor_limit,
        'province_sensor_limit': province_sensor_limit,
    }
    return payload, stats


def _get_bigmodel_request_plan(question_profile: dict[str, Any]) -> dict[str, Any]:
    intent = (question_profile or {}).get('intent') or 'general'

    try:
        max_tokens = int(os.environ.get('BIGMODEL_MAX_TOKENS', '0'))
    except (TypeError, ValueError):
        max_tokens = 0
    if max_tokens <= 0:
        max_tokens = {
            'report': 896,
            'prioritize': 896,
            'eutrophication': 640,
            'oxygen': 640,
            'general': 640,
        }.get(intent, 640)
    max_tokens = max(max_tokens, 512)

    try:
        timeout_seconds = int(os.environ.get('BIGMODEL_TIMEOUT_SECONDS', '45'))
    except (TypeError, ValueError):
        timeout_seconds = 45
    timeout_seconds = max(timeout_seconds, 30)

    try:
        max_attempts = int(os.environ.get('BIGMODEL_MAX_ATTEMPTS', '1'))
    except (TypeError, ValueError):
        max_attempts = 1
    max_attempts = max(1, min(max_attempts, 3))

    thinking_type = (os.environ.get('BIGMODEL_THINKING_TYPE') or 'disabled').strip().lower()
    if thinking_type not in {'enabled', 'disabled'}:
        thinking_type = 'disabled'

    retry_budget = min(max(max_tokens + 384, int(max_tokens * 1.75)), 1536)

    return {
        'max_tokens': max_tokens,
        'retry_budget': retry_budget,
        'timeout_seconds': timeout_seconds,
        'max_attempts': max_attempts,
        'thinking_type': thinking_type,
    }


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}
    return bool(value)


def _get_ai_api_key() -> str:
    return (os.environ.get('MODELSCOPE_API_KEY') or os.environ.get('SILICONFLOW_API_KEY') or '').strip()


def _build_bigmodel_messages(question: str, context: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, int], dict[str, Any]]:
    question_profile = context.get('question_profile') or {}
    context_payload, context_stats = _build_bigmodel_context_payload(context)
    if question_profile.get('intent') == 'smalltalk':
        messages = [
            {'role': 'system', 'content': SMALLTALK_SYSTEM_PROMPT},
            {'role': 'user', 'content': question},
        ]
        return messages, context_stats, _get_bigmodel_request_plan(question_profile)

    messages = [
        {'role': 'system', 'content': BIGMODEL_SYSTEM_PROMPT},
        {
            'role': 'user',
            'content': (
                f"问题: {question}\n"
                f"问题类型: {question_profile.get('intent') or 'general'}\n"
                f"回答提示: {question_profile.get('output_hint') or '直接回答'}\n"
                f"关注指标: {', '.join(question_profile.get('focus_metrics') or [])}\n\n"
                f"上下文数据(JSON):\n{json.dumps(context_payload, ensure_ascii=False)}"
            )
        }
    ]
    return messages, context_stats, _get_bigmodel_request_plan(question_profile)


def _build_bigmodel_request_payload(
    model: str,
    messages: list[dict[str, str]],
    *,
    token_budget: int,
    thinking_type: str,
    stream: bool,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": token_budget,
        "stream": stream,
        "temperature": 0.25,
    }
    if AI_PROVIDER_SOURCE == 'siliconflow':
        payload["thinking"] = {"type": thinking_type}
    return payload


def _extract_stream_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return ''
    parts = []
    for item in value:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        text = item.get('text') or item.get('content') or item.get('output_text') or item.get('value')
        if isinstance(text, str):
            parts.append(text)
    return ''.join(parts)


def _iter_sse_payloads(lines) -> Any:
    event = 'message'
    data_lines = []
    for raw_line in lines:
        if raw_line is None:
            continue
        if isinstance(raw_line, bytes):
            line = raw_line.decode('utf-8', errors='replace').rstrip('\r')
        else:
            line = str(raw_line).rstrip('\r')
        if not line:
            if data_lines:
                yield event, '\n'.join(data_lines)
                event = 'message'
                data_lines = []
            continue
        if line.startswith(':'):
            continue
        if line.startswith('event:'):
            event = line[6:].strip() or 'message'
            continue
        if line.startswith('data:'):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        yield event, '\n'.join(data_lines)


def _format_sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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
        'question_profile': context.get('question_profile'),
        'risk_signal_summary': context.get('risk_signal_summary'),
        'focus_signal_summary': context.get('focus_signal_summary'),
        'ctx_sensors_station_ids': [s.get('station_id') for s in sensors if isinstance(s, dict) and s.get('station_id')][:50],
        'province_sensors_station_ids': [
            s.get('station_id') for s in province_sensors if isinstance(s, dict) and s.get('station_id')
        ][:50],
    }


def _build_merged_ai_context(
    client_context: dict[str, Any],
    *,
    question: str,
    question_profile: dict[str, Any],
    trace: list[dict[str, Any]],
    started_at: float,
) -> tuple[dict[str, Any], float]:
    snapshot_context = _build_snapshot_ai_context()
    merged_context = {**client_context, **snapshot_context}
    merged_context['question_profile'] = question_profile
    merged_context['focus_signal_summary'] = merged_context.get('risk_signal_summary')

    ready_at = time.monotonic()
    trace.append({
        'phase': 'snapshot_context_ready',
        'elapsed_seconds': round(ready_at - started_at, 3),
        'sensor_count': len(merged_context.get('sensors') or []),
        'summary': merged_context.get('summary'),
        'risk_signal_summary': merged_context.get('risk_signal_summary'),
        'question_profile': question_profile,
    })

    province_focus = _extract_province_focus(question)
    if province_focus:
        merged_context['province_focus'] = province_focus
        merged_context['province_sensors'] = _get_snapshot_samples_by_province(province_focus, limit=20)
        merged_context['focus_signal_summary'] = _summarize_ai_signals(merged_context.get('province_sensors') or [])
        trace.append({
            'phase': 'province_focus_detected',
            'province_focus': province_focus,
            'province_sensor_count': len(merged_context.get('province_sensors') or []),
        })

    return merged_context, ready_at - started_at


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
    model = payload.get('model') or DEFAULT_BIGMODEL_MODEL
    stream_requested = _is_truthy(payload.get('stream'))
    t0 = time.monotonic()
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or '-'
    question_profile = _build_question_profile(question)
    merged_context = {**client_context, 'question_profile': question_profile}
    trace = [
        {
            'phase': 'request_received',
            'model': model,
            'question': question,
            'question_preview': _truncate_for_log(question, 180),
            'client_ip': client_ip,
        }
    ]
    logger.info(
        "AI insight request model=%s ip=%s question=%s",
        model,
        client_ip,
        _truncate_for_log(question, 240),
    )

    if stream_requested:
        return _build_ai_insight_stream_response(
            request=request,
            question=question,
            model=model,
            client_context=client_context,
            question_profile=question_profile,
            trace=trace,
            started_at=t0,
        )

    def _respond_with_ai_error(status_code: int, reason: str, *, build_ctx_elapsed=None, exc: Exception | None = None):
        total_elapsed = time.monotonic() - t0
        trace.append({
            'phase': 'ai_error',
            'reason': reason,
            'status_code': status_code,
            'build_ctx_seconds': round(build_ctx_elapsed or 0.0, 3),
            'total_seconds': round(total_elapsed, 3),
        })
        if exc:
            logger.warning(
                "AI insight failed model=%s status=%s reason=%s question=%s",
                model,
                status_code,
                reason,
                _truncate_for_log(question, 180),
                exc_info=True,
            )
        else:
            logger.warning(
                "AI insight failed model=%s status=%s reason=%s question=%s",
                model,
                status_code,
                reason,
                _truncate_for_log(question, 180),
            )
        _safe_create_ai_log(
            question=question,
            answer=None,
            model=model,
            success=False,
            error_message=reason,
            request_payload={'question': question, 'context': _build_ai_log_payload(merged_context)},
            response_meta={
                'source': AI_PROVIDER_SOURCE,
                'status_code': status_code,
                'reason': reason,
                'trace': trace,
            },
            request=request,
            duration_ms=int(total_elapsed * 1000),
        )
        return Response({'code': status_code, 'message': reason}, status=status_code)

    try:
        merged_context, build_ctx_elapsed = _build_merged_ai_context(
            client_context,
            question=question,
            question_profile=question_profile,
            trace=trace,
            started_at=t0,
        )

        api_key = _get_ai_api_key()
        if not api_key:
            return _respond_with_ai_error(400, '未配置 MODELSCOPE_API_KEY', build_ctx_elapsed=build_ctx_elapsed)

        t2 = time.monotonic()
        model_result = _call_bigmodel(api_key, model, question, merged_context)
        t3 = time.monotonic()
        trace.append({
            'phase': 'bigmodel_completed',
            'elapsed_seconds': round(t3 - t2, 3),
            'build_ctx_seconds': round(build_ctx_elapsed, 3),
            'attempts': model_result.get('attempts'),
            'token_budget': model_result.get('token_budget'),
            'thinking_type': model_result.get('thinking_type'),
            'finish_reason': model_result.get('finish_reason'),
            'log_id': model_result.get('log_id'),
            'usage': model_result.get('usage'),
            'context_stats': model_result.get('context_stats'),
            'request_plan': model_result.get('request_plan'),
            'answer_clean_meta': model_result.get('answer_clean_meta'),
            'reasoning_clean_meta': model_result.get('reasoning_clean_meta'),
            'truncated': model_result.get('truncated'),
        })
        if model_result.get('reasoning'):
            logger.info(
                "AI insight provider reasoning=%s",
                _truncate_for_log(model_result.get('reasoning'), 300),
            )
        if not model_result.get('answer'):
            return _respond_with_ai_error(502, 'AI服务未返回可用的最终回答', build_ctx_elapsed=build_ctx_elapsed)
        answer = model_result['answer']
        if model_result.get('truncated'):
            logger.warning(
                "AI insight answer looks truncated; returning partial answer model=%s question=%s answer=%s",
                model,
                _truncate_for_log(question, 180),
                _truncate_for_log(answer, 300),
            )
        logger.info(
            "AI insight ok model=%s build_ctx=%.3fs call_model=%.3fs total=%.3fs question=%s answer=%s",
            model,
            build_ctx_elapsed,
            (t3 - t2),
            (t3 - t0),
            _truncate_for_log(question, 180),
            _truncate_for_log(answer, 300),
        )
        _safe_create_ai_log(
            question=question,
            answer=answer,
            model=model,
            success=True,
            error_message=None,
            request_payload={'question': question, 'context': _build_ai_log_payload(merged_context)},
            response_meta={
                'source': AI_PROVIDER_SOURCE,
                'trace': trace,
                'usage': model_result.get('usage'),
                'finish_reason': model_result.get('finish_reason'),
                'attempts': model_result.get('attempts'),
                'token_budget': model_result.get('token_budget'),
                'thinking_type': model_result.get('thinking_type'),
                'log_id': model_result.get('log_id'),
                'context_stats': model_result.get('context_stats'),
                'request_plan': model_result.get('request_plan'),
                'reasoning': model_result.get('reasoning'),
                'answer_preview': _truncate_for_log(answer, 300),
                'truncated': model_result.get('truncated'),
            },
            request=request,
            duration_ms=int((t3 - t0) * 1000),
        )
    except RuntimeError as exc:
        return _respond_with_ai_error(502, str(exc), build_ctx_elapsed=(build_ctx_elapsed if 'build_ctx_elapsed' in locals() else 0.0), exc=exc)
    except Exception as exc:
        return _respond_with_ai_error(500, f'内部处理异常: {exc}', build_ctx_elapsed=(build_ctx_elapsed if 'build_ctx_elapsed' in locals() else 0.0), exc=exc)

    return Response({
        'code': 200,
        'message': 'success',
        'data': {
            'answer': answer,
            'model': model,
            'source': AI_PROVIDER_SOURCE,
            'degraded': bool(model_result.get('truncated')),
            'truncated': bool(model_result.get('truncated')),
        }
    })


def _build_ai_insight_stream_response(
    *,
    request,
    question: str,
    model: str,
    client_context: dict[str, Any],
    question_profile: dict[str, Any],
    trace: list[dict[str, Any]],
    started_at: float,
):
    def event_stream():
        merged_context = {**client_context, 'question_profile': question_profile}
        build_ctx_elapsed = 0.0
        state = {
            'source': AI_PROVIDER_SOURCE,
            'answer': None,
            'reasoning': None,
            'usage': None,
            'finish_reason': None,
            'attempts': None,
            'token_budget': None,
            'thinking_type': None,
            'log_id': None,
            'context_stats': None,
            'request_plan': None,
            'answer_clean_meta': None,
            'reasoning_clean_meta': None,
            'stream_chunk_count': 0,
            'first_chunk_seconds': None,
            'truncated': False,
        }
        error_message = None

        try:
            merged_context, build_ctx_elapsed = _build_merged_ai_context(
                client_context,
                question=question,
                question_profile=question_profile,
                trace=trace,
                started_at=started_at,
            )

            api_key = _get_ai_api_key()
            if not api_key:
                raise RuntimeError('未配置 MODELSCOPE_API_KEY')

            trace.append({
                'phase': 'stream_opened',
                'build_ctx_seconds': round(build_ctx_elapsed, 3),
            })
            yield _format_sse_event('meta', {
                'model': model,
                'source': AI_PROVIDER_SOURCE,
                'degraded': False,
            })

            t2 = time.monotonic()
            for chunk in _stream_bigmodel_events(api_key, model, question, merged_context, state):
                yield chunk
            t3 = time.monotonic()

            trace.append({
                'phase': 'bigmodel_stream_completed',
                'elapsed_seconds': round(t3 - t2, 3),
                'build_ctx_seconds': round(build_ctx_elapsed, 3),
                'attempts': state.get('attempts'),
                'token_budget': state.get('token_budget'),
                'thinking_type': state.get('thinking_type'),
                'finish_reason': state.get('finish_reason'),
                'log_id': state.get('log_id'),
                'usage': state.get('usage'),
                'context_stats': state.get('context_stats'),
                'request_plan': state.get('request_plan'),
                'answer_clean_meta': state.get('answer_clean_meta'),
                'reasoning_clean_meta': state.get('reasoning_clean_meta'),
                'stream_chunk_count': state.get('stream_chunk_count'),
                'first_chunk_seconds': state.get('first_chunk_seconds'),
                'truncated': state.get('truncated'),
            })
        except RuntimeError as exc:
            error_message = str(exc)
            total_elapsed = time.monotonic() - started_at
            trace.append({
                'phase': 'ai_error',
                'reason': error_message,
                'status_code': 502,
                'build_ctx_seconds': round(build_ctx_elapsed, 3),
                'total_seconds': round(total_elapsed, 3),
            })
            logger.warning(
                "AI insight stream failed model=%s status=%s reason=%s question=%s",
                model,
                502,
                error_message,
                _truncate_for_log(question, 180),
                exc_info=True,
            )
            yield _format_sse_event('error', {
                'code': 502,
                'message': error_message,
                'model': model,
                'source': AI_PROVIDER_SOURCE,
            })
        except Exception as exc:
            error_message = f'内部处理异常: {exc}'
            total_elapsed = time.monotonic() - started_at
            trace.append({
                'phase': 'ai_error',
                'reason': error_message,
                'status_code': 500,
                'build_ctx_seconds': round(build_ctx_elapsed, 3),
                'total_seconds': round(total_elapsed, 3),
            })
            logger.warning(
                "AI insight stream failed model=%s status=%s reason=%s question=%s",
                model,
                500,
                error_message,
                _truncate_for_log(question, 180),
                exc_info=True,
            )
            yield _format_sse_event('error', {
                'code': 500,
                'message': error_message,
                'model': model,
                'source': AI_PROVIDER_SOURCE,
            })
        finally:
            total_elapsed = time.monotonic() - started_at
            if state.get('reasoning'):
                logger.info(
                    "AI insight provider reasoning=%s",
                    _truncate_for_log(state.get('reasoning'), 300),
                )
            if not error_message and state.get('answer'):
                logger.info(
                    "AI insight stream ok model=%s build_ctx=%.3fs total=%.3fs first_chunk=%ss question=%s answer=%s",
                    model,
                    build_ctx_elapsed,
                    total_elapsed,
                    state.get('first_chunk_seconds'),
                    _truncate_for_log(question, 180),
                    _truncate_for_log(state.get('answer'), 300),
                )
            _safe_create_ai_log(
                question=question,
                answer=state.get('answer'),
                model=model,
                success=bool(state.get('answer')) and not error_message,
                error_message=error_message,
                request_payload={'question': question, 'context': _build_ai_log_payload(merged_context)},
                response_meta={
                    'source': AI_PROVIDER_SOURCE,
                    'stream': True,
                    'trace': trace,
                    'usage': state.get('usage'),
                    'finish_reason': state.get('finish_reason'),
                    'attempts': state.get('attempts'),
                    'token_budget': state.get('token_budget'),
                    'thinking_type': state.get('thinking_type'),
                    'log_id': state.get('log_id'),
                    'context_stats': state.get('context_stats'),
                    'request_plan': state.get('request_plan'),
                    'reasoning': state.get('reasoning'),
                    'stream_chunk_count': state.get('stream_chunk_count'),
                    'first_chunk_seconds': state.get('first_chunk_seconds'),
                    'answer_preview': _truncate_for_log(state.get('answer'), 300),
                    'truncated': state.get('truncated'),
                },
                request=request,
                duration_ms=int(total_elapsed * 1000),
            )

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream; charset=utf-8')
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'
    return response


def _stream_bigmodel_events(api_key, model, question, context, state: dict[str, Any]):
    messages, context_stats, request_plan = _build_bigmodel_messages(question, context)
    token_budget = request_plan['max_tokens']
    timeout_seconds = request_plan['timeout_seconds']
    thinking_type = request_plan['thinking_type']
    max_attempts = request_plan['max_attempts']
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    state.update({
        'attempts': 1,
        'token_budget': token_budget,
        'thinking_type': thinking_type,
        'context_stats': context_stats,
        'request_plan': request_plan,
    })

    logger.info(
        "ModelScope stream plan model=%s thinking=%s max_tokens=%s timeout=%ss attempts=%s sensors=%s/%s province_sensors=%s/%s question=%s",
        model,
        thinking_type,
        token_budget,
        timeout_seconds,
        max_attempts,
        context_stats.get('sensor_count'),
        context_stats.get('sensor_limit'),
        context_stats.get('province_sensor_count'),
        context_stats.get('province_sensor_limit'),
        _truncate_for_log(question, 180),
    )

    try:
        with requests.post(
            BIGMODEL_API_URL,
            json=_build_bigmodel_request_payload(
                model,
                messages,
                token_budget=token_budget,
                thinking_type=thinking_type,
                stream=True,
            ),
            headers=headers,
            timeout=(10, timeout_seconds),
            stream=True,
        ) as response:
            log_id = response.headers.get("x-log-id") or response.headers.get("X-Log-Id") or "-"
            state['log_id'] = log_id
            logger.info(
                "ModelScope stream status=%s log_id=%s token_budget=%s thinking=%s question=%s",
                response.status_code,
                log_id,
                token_budget,
                thinking_type,
                _truncate_for_log(question, 180),
            )

            if response.status_code == 429:
                raise RuntimeError('AI服务触发限流(HTTP 429)，请稍后再试')
            if response.status_code != 200:
                raise RuntimeError(f'AI服务响应异常(HTTP {response.status_code})')

            answer_parts = []
            reasoning_parts = []
            finish_reason = None
            usage = None
            chunk_count = 0
            first_chunk_seconds = None
            call_started = time.monotonic()

            for _event, data_text in _iter_sse_payloads(response.iter_lines(decode_unicode=False)):
                if not data_text:
                    continue
                if data_text == '[DONE]':
                    break
                try:
                    data = json.loads(data_text)
                except ValueError as exc:
                    raise RuntimeError(f'AI服务返回非JSON流片段: {data_text[:300]}') from exc

                choices = data.get('choices') or []
                if not choices:
                    if isinstance(data.get('usage'), dict):
                        usage = data.get('usage')
                    continue

                choice0 = choices[0] if isinstance(choices[0], dict) else {}
                delta = choice0.get('delta') if isinstance(choice0, dict) else {}
                if not isinstance(delta, dict):
                    delta = {}

                reasoning_delta = _extract_stream_text(delta.get('reasoning_content'))
                content_delta = _extract_stream_text(delta.get('content'))
                if reasoning_delta:
                    reasoning_parts.append(reasoning_delta)
                if content_delta:
                    answer_parts.append(content_delta)
                    chunk_count += 1
                    if first_chunk_seconds is None:
                        first_chunk_seconds = round(time.monotonic() - call_started, 3)
                    yield _format_sse_event('chunk', {'delta': content_delta})

                finish_reason = choice0.get('finish_reason') or finish_reason
                if isinstance(data.get('usage'), dict):
                    usage = data.get('usage')

            answer_raw = ''.join(answer_parts)
            reasoning_raw = ''.join(reasoning_parts)
            answer, answer_clean_meta = _clean_ai_output(answer_raw)
            reasoning, reasoning_clean_meta = _clean_ai_output(reasoning_raw)
            truncated = _looks_truncated(answer, finish_reason)

            state.update({
                'answer': answer,
                'reasoning': reasoning,
                'answer_raw': answer_raw,
                'reasoning_raw': reasoning_raw,
                'finish_reason': finish_reason,
                'usage': usage,
                'answer_clean_meta': answer_clean_meta,
                'reasoning_clean_meta': reasoning_clean_meta,
                'stream_chunk_count': chunk_count,
                'first_chunk_seconds': first_chunk_seconds,
                'truncated': truncated,
            })

            logger.info(
                "ModelScope stream parsed answer_len=%s reasoning_len=%s finish_reason=%s truncated=%s cached_tokens=%s answer=%s",
                len(answer or ''),
                len(reasoning or ''),
                finish_reason,
                truncated,
                (((usage or {}).get('prompt_tokens_details') or {}).get('cached_tokens')),
                _truncate_for_log(answer or answer_raw, 300),
            )

            if not answer:
                raise RuntimeError('AI服务未返回可用的最终回答')
            if truncated:
                logger.warning(
                    "ModelScope stream answer looks truncated; attempting repair question=%s answer=%s",
                    _truncate_for_log(question, 180),
                    _truncate_for_log(answer or answer_raw, 220),
                )
                try:
                    repaired_result = _call_bigmodel(api_key, model, question, context)
                except RuntimeError as repair_exc:
                    logger.warning(
                        "ModelScope truncated stream repair failed question=%s reason=%s",
                        _truncate_for_log(question, 180),
                        repair_exc,
                    )
                else:
                    repaired_answer = repaired_result.get('answer')
                    if repaired_answer:
                        answer = repaired_answer
                        reasoning = repaired_result.get('reasoning') or reasoning
                        finish_reason = repaired_result.get('finish_reason') or finish_reason
                        usage = repaired_result.get('usage') or usage
                        truncated = bool(repaired_result.get('truncated'))
                        state.update({
                            'answer': answer,
                            'reasoning': reasoning,
                            'finish_reason': finish_reason,
                            'usage': usage,
                            'answer_clean_meta': repaired_result.get('answer_clean_meta'),
                            'reasoning_clean_meta': repaired_result.get('reasoning_clean_meta'),
                            'truncated': truncated,
                        })
                        logger.info(
                            "ModelScope truncated stream repaired question=%s repaired_truncated=%s answer=%s",
                            _truncate_for_log(question, 180),
                            truncated,
                            _truncate_for_log(answer, 220),
                        )
                    else:
                        logger.warning(
                            "ModelScope truncated stream repair returned no answer question=%s",
                            _truncate_for_log(question, 180),
                        )

            yield _format_sse_event('done', {
                'answer': answer,
                'model': model,
                'source': AI_PROVIDER_SOURCE,
                'degraded': truncated,
                'truncated': truncated,
                'finish_reason': finish_reason,
                'usage': usage,
            })
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f'AI服务连接失败: {exc}') from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(f'AI服务响应超时({timeout_seconds}s)') from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f'AI服务请求失败: {exc}') from exc


def _call_bigmodel(api_key, model, question, context):
    messages, context_stats, request_plan = _build_bigmodel_messages(question, context)

    max_tokens = request_plan['max_tokens']
    timeout_seconds = request_plan['timeout_seconds']
    max_attempts = request_plan['max_attempts']
    thinking_type = request_plan['thinking_type']
    retry_budget = request_plan['retry_budget']

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    logger.info(
        "ModelScope request plan model=%s thinking=%s max_tokens=%s retry_budget=%s timeout=%ss attempts=%s sensors=%s/%s province_sensors=%s/%s question=%s",
        model,
        thinking_type,
        max_tokens,
        retry_budget,
        timeout_seconds,
        max_attempts,
        context_stats.get('sensor_count'),
        context_stats.get('sensor_limit'),
        context_stats.get('province_sensor_count'),
        context_stats.get('province_sensor_limit'),
        _truncate_for_log(question, 180),
    )

    max_token_budgets = [max_tokens]
    if retry_budget > max_tokens:
        max_token_budgets.append(retry_budget)

    last_result = None
    for token_budget in max_token_budgets:
        for attempt in range(max_attempts):
            payload = _build_bigmodel_request_payload(
                model,
                messages,
                token_budget=token_budget,
                thinking_type=thinking_type,
                stream=False,
            )
            try:
                response = requests.post(
                    BIGMODEL_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=(10, timeout_seconds),
                )
                log_id = response.headers.get("x-log-id") or response.headers.get("X-Log-Id") or "-"
                logger.info(
                    "ModelScope API status=%s log_id=%s token_budget=%s attempt=%s thinking=%s question=%s",
                    response.status_code,
                    log_id,
                    token_budget,
                    attempt + 1,
                    thinking_type,
                    _truncate_for_log(question, 180),
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

                try:
                    data = response.json()
                except ValueError as exc:
                    raise RuntimeError(f'AI服务返回非JSON响应: {response.text[:300]}') from exc

                result = _extract_bigmodel_result(
                    data,
                    finish_reason=(data.get('finish_reason') if isinstance(data, dict) else None),
                    log_id=log_id,
                    attempts=attempt + 1,
                    token_budget=token_budget,
                )
                result['thinking_type'] = thinking_type
                result['context_stats'] = context_stats
                result['request_plan'] = request_plan
                logger.info(
                    "ModelScope parsed answer_len=%s reasoning_len=%s finish_reason=%s truncated=%s cached_tokens=%s answer=%s",
                    len(result.get('answer') or ''),
                    len(result.get('reasoning') or ''),
                    result.get('finish_reason'),
                    result.get('truncated'),
                    (((result.get('usage') or {}).get('prompt_tokens_details') or {}).get('cached_tokens')),
                    _truncate_for_log(result.get('answer') or result.get('answer_raw'), 300),
                )
                if result.get('answer') and not result.get('truncated'):
                    return result

                last_result = result
                if result.get('truncated') and token_budget < max_token_budgets[-1]:
                    logger.warning(
                        "ModelScope answer looks truncated; retrying with higher token budget. question=%s answer=%s",
                        _truncate_for_log(question, 180),
                        _truncate_for_log(result.get('answer') or result.get('answer_raw'), 220),
                    )
                    break
                if result.get('answer'):
                    return result
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

    if last_result:
        return last_result
    raise RuntimeError(f'AI服务响应超时({timeout_seconds}s)')


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
        avg_permanganate=Avg('permanganate'),
        avg_ammonia_nitrogen=Avg('ammonia_nitrogen'),
        avg_total_phosphorus=Avg('total_phosphorus'),
        avg_total_nitrogen=Avg('total_nitrogen'),
        avg_chlorophyll_a=Avg('chlorophyll_a'),
        avg_algae_density=Avg('algae_density'),
    )

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
        'permanganate',
        'ammonia_nitrogen',
        'total_phosphorus',
        'total_nitrogen',
        'chlorophyll_a',
        'algae_density',
        'recorded_at',
    ))
    rows = _normalize_snapshot_rows(rows)
    risk_signal_summary = _summarize_ai_signals(rows[:20])

    return {
        'source_table': 'sensor_data_latest',
        'timestamp': (latest_time or now).isoformat(),
        'data_source': 'database',
        'summary': {
            'total_devices': total_devices,
            'online_devices': online_devices,
            'offline_devices': offline_devices,
            'alert_count': alert_count,
            'avg_temperature': _round_float(avg_agg.get('avg_temperature'), 2),
            'avg_ph': _round_float(avg_agg.get('avg_ph'), 2),
            'avg_dissolved_oxygen': _round_float(avg_agg.get('avg_dissolved_oxygen'), 2),
            'avg_conductivity': _round_float(avg_agg.get('avg_conductivity'), 2),
            'avg_turbidity': _round_float(avg_agg.get('avg_turbidity'), 2),
            'avg_permanganate': _round_float(avg_agg.get('avg_permanganate'), 3),
            'avg_ammonia_nitrogen': _round_float(avg_agg.get('avg_ammonia_nitrogen'), 3),
            'avg_total_phosphorus': _round_float(avg_agg.get('avg_total_phosphorus'), 3),
            'avg_total_nitrogen': _round_float(avg_agg.get('avg_total_nitrogen'), 3),
            'avg_chlorophyll_a': _round_float(avg_agg.get('avg_chlorophyll_a'), 3),
            'avg_algae_density': _round_float(avg_agg.get('avg_algae_density'), 2),
        },
        'water_quality_distribution': water_quality_dist,
        'province_distribution': province_dist,
        'risk_signal_summary': risk_signal_summary,
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
        'permanganate',
        'ammonia_nitrogen',
        'total_phosphorus',
        'total_nitrogen',
        'chlorophyll_a',
        'algae_density',
        'recorded_at',
    ))
    return _normalize_snapshot_rows(rows)


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
