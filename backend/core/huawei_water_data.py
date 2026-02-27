"""
Huawei Water Data Service
华为云API市场 - 地表水监测数据服务
API文档: https://www.apistore.cn/kv/kvcenter?id=XXXX
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from django.conf import settings
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)

# Import Huawei SDK - 使用本地SDK
HUAWEI_SDK_AVAILABLE = False

def _get_huawei_sdk():
    """动态导入华为SDK，优先使用本地SDK"""
    global HUAWEI_SDK_AVAILABLE
    try:
        # 优先使用本地SDK
        from apig_sdk.signer import Signer, HttpRequest
        HUAWEI_SDK_AVAILABLE = True
        logger.info("华为SDK导入成功(本地SDK)")
        return Signer, HttpRequest
    except ImportError:
        try:
            # 备选：使用pip安装的SDK
            from apigateway_sdk_python.signer import Signer, HttpRequest
            HUAWEI_SDK_AVAILABLE = True
            logger.info("华为SDK导入成功(pip SDK)")
            return Signer, HttpRequest
        except ImportError as e:
            HUAWEI_SDK_AVAILABLE = False
            logger.warning(f"华为SDK导入失败: {e}")
            import sys
            logger.warning(f"Python路径: {sys.path[:3]}")
            return None, None
    except Exception as e:
        HUAWEI_SDK_AVAILABLE = False
        logger.warning(f"华为SDK导入异常: {e}")
        return None, None

# 尝试在模块加载时导入
_get_huawei_sdk()

# Fallback HttpRequest class
class _FallbackHttpRequest:
        def __init__(self, method="", url="", headers=None, body=""):
            from urllib.parse import urlparse, unquote
            spl = url.split("://", 1)
            scheme = 'http'
            if len(spl) > 1:
                scheme = spl[0]
                url = spl[1]
            query = {}
            spl = url.split('?', 1)
            url = spl[0]
            if len(spl) > 1:
                for kv in spl[1].split("&"):
                    spl2 = kv.split("=", 1)
                    key = spl2[0]
                    value = ""
                    if len(spl2) > 1:
                        value = spl2[1]
                    if key != '':
                        key = unquote(key)
                        value = unquote(value)
                        if key in query:
                            query[key].append(value)
                        else:
                            query[key] = [value]
            spl = url.split('/', 1)
            host = spl[0]
            if len(spl) > 1:
                url = '/' + spl[1]
            else:
                url = '/'
            self.scheme = scheme
            self.host = host
            self.uri = url
            self.query = query
            self.headers = headers or {}
            self.body = body.encode("utf-8") if isinstance(body, str) else body


@dataclass(frozen=True)
class HuaweiWaterRecord:
    device_id: str
    device_name: str
    location: str
    timestamp: datetime
    temperature: Optional[float]
    ph: Optional[float]
    dissolved_oxygen: Optional[float]
    conductivity: Optional[float] = None
    turbidity: Optional[float] = None
    permanganate: Optional[float] = None
    ammonia_nitrogen: Optional[float] = None
    total_phosphorus: Optional[float] = None
    total_nitrogen: Optional[float] = None
    water_quality: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    river_basin: Optional[str] = None


_cache: Dict[str, Any] = {"records": None, "fetched_at": None}


def _get_config() -> Dict[str, Any]:
    return getattr(settings, "HUAWEI_WATER_DATA", {})


def _is_enabled(config: Dict[str, Any]) -> bool:
    return bool(config.get("enabled") and config.get("app_key") and config.get("app_secret"))


def _cache_valid(config: Dict[str, Any]) -> bool:
    fetched_at = _cache.get("fetched_at")
    if not fetched_at:
        return False
    cache_minutes = int(config.get("cache_minutes", 10))
    return dj_timezone.now() - fetched_at < timedelta(minutes=cache_minutes)


def _build_sdk_hmac_sha256_signature(
    app_key: str,
    app_secret: str,
    method: str,
    url: str,
    query_params: Dict[str, Any],
    stage: str = "RELEASE"
) -> str:
    """构建华为云SDK-HMAC-SHA256签名

    根据华为云API网关签名算法实现:
    https://support.huaweicloud.com/intl/zh-cn/devg-apisign/api-sign-algorithm-005.html

    步骤：
    1. 构造规范请求 (CanonicalRequest)
    2. 创建待签名字符串 (StringToSign)
    3. 计算签名 (Signature)

    Args:
        stage: 环境名称 (RELEASE 或 TEST)
    """
    from datetime import datetime, timezone
    import urllib.parse

    # 解析URL获取path和host
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    host = parsed_url.netloc
    canonical_uri = parsed_url.path or "/"

    # 规范查询字符串
    if query_params:
        # 按参数名升序排列
        sorted_params = sorted(query_params.items())
        # URI编码并拼接
        encoded_params = []
        for k, v in sorted_params:
            if v is not None:
                encoded_k = urllib.parse.quote(str(k), safe='')
                encoded_v = urllib.parse.quote(str(v), safe='')
                encoded_params.append(f"{encoded_k}={encoded_v}")
        canonical_querystring = "&".join(encoded_params)
    else:
        canonical_querystring = ""

    # 时间戳
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    date_stamp = datetime.now(timezone.utc).strftime('%Y%m%d')

    # 规范headers（包含X-Stage，按字母序排序）
    canonical_headers = (
        f"host:{host}\n" +
        f"x-sdk-date:{timestamp}\n" +
        f"x-stage:{stage}\n"
    )

    # 签名的headers列表（小写，按字母序）
    signed_headers = "host;x-sdk-date;x-stage"

    # 请求payload哈希（GET请求为空）
    payload_hash = hashlib.sha256("".encode("utf-8")).hexdigest()

    # 构造规范请求
    canonical_request = (
        f"{method}\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    # 创建待签名字符串
    # 注意：对于API市场，不使用region，直接用"apigw"
    credential_scope = f"{date_stamp}/apigw/sdk-hmac-sha256"

    string_to_sign = (
        "SDK-HMAC-SHA256\n" +
        f"{timestamp}\n" +
        f"{credential_scope}\n" +
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    )

    # 计算签名密钥
    k_date = hmac.new(
        f"HMAC-SHA256{app_secret}".encode("utf-8"),
        date_stamp.encode("utf-8"),
        hashlib.sha256
    ).digest()

    # 对于API市场，service使用"apigw"
    k_service = hmac.new(
        k_date,
        "apigw".encode("utf-8"),
        hashlib.sha256
    ).digest()

    k_signing = hmac.new(
        k_service,
        "sdk-hmac-sha256".encode("utf-8"),
        hashlib.sha256
    ).digest()

    # 计算签名
    signature = hmac.new(
        k_signing,
        string_to_sign.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # 构造Authorization header
    authorization = (
        f"SDK-HMAC-SHA256 "
        f"Credential={app_key},"
        f"SignedHeaders={signed_headers},"
        f"Signature={signature}"
    )

    return authorization, timestamp


def _build_signature(app_key: str, app_secret: str, params: Dict[str, Any]) -> str:
    """构建华为API签名（旧方法，保留用于兼容）

    华为API市场使用 HMAC-SHA256 签名算法:
    1. 将所有参数按字母顺序排序
    2. 拼接成 key1=value1&key2=value2 格式
    3. 使用 app_secret 作为 key 进行 HMAC-SHA256 签名
    4. 签名结果转为十六进制字符串
    """
    # 按字母顺序排序参数
    sorted_params = sorted(params.items())

    # 拼接参数字符串
    param_str = "&".join([f"{k}={v}" for k, v in sorted_params if v is not None])

    # 使用 HMAC-SHA256 签名
    signature = hmac.new(
        app_secret.encode("utf-8"),
        param_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return signature


def _make_request(
    url: str,
    app_key: str,
    app_secret: str,
    params: Dict[str, Any],
    timeout: int,
    stanames: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """发送请求到华为API

    使用华为官方SDK (apigateway-sdk-python) 进行签名认证

    Args:
        stanames: 站点名称列表，API必需参数。如果为None则尝试获取所有数据。
    """
    # 构建查询字符串
    if params:
        query_string = urllib.parse.urlencode(params)
    else:
        query_string = ""

    # staname是必需参数，尝试不同的值
    if stanames:
        # 使用提供的站点名称
        for staname in stanames:
            full_url = f"{url}?{query_string}&staname={urllib.parse.quote(staname)}"
            result = _try_sdk_request(full_url, app_key, app_secret, timeout)
            if result:
                return result
        logger.warning(f"所有提供的站点名称都未找到数据: {stanames}")
    else:
        # 尝试不指定staname（可能返回所有数据）
        full_url = f"{url}?{query_string}" if query_string else url
        result = _try_sdk_request(full_url, app_key, app_secret, timeout)
        if result:
            return result

        # 如果上述失败，这是正常的 - API需要staname参数
        logger.info("API需要staname参数，请在配置中提供有效的站点名称")

    return None


def _try_sdk_request(url: str, app_key: str, app_secret: str, timeout: int) -> Optional[Dict[str, Any]]:
    """使用华为SDK尝试请求"""
    # 每次调用时都尝试导入SDK，解决StatReloader问题
    Signer, HttpRequest = _get_huawei_sdk()

    try:
        if not HUAWEI_SDK_AVAILABLE or Signer is None:
            logger.warning("华为SDK不可用，使用备用方法")
            return _try_fallback_request(url, app_key, app_secret, timeout)

        logger.info(f"华为SDK请求: {url}")

        # 创建签名器
        sig = Signer()
        sig.Key = app_key
        sig.Secret = app_secret

        # 创建请求
        r = HttpRequest("GET", url, {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }, "")

        # 签名
        sig.Sign(r)

        # 使用requests发送请求（按照SDK demo的方式）
        response = requests.request("GET", url, headers=r.headers, timeout=timeout)

        if response.status_code == 200:
            data = response.text
            logger.info(f"华为SDK请求成功，响应: {data[:200]}")
            return json.loads(data)
        else:
            logger.warning(f"华为SDK请求失败: {response.status_code} - {response.text[:200]}")
            return None

    except requests.exceptions.RequestException as e:
        logger.warning(f"华为SDK请求异常: {e}")
        return None
    except Exception as e:
        logger.warning(f"华为SDK请求异常: {e}")
        return None


def _try_fallback_request(url: str, app_key: str, app_secret: str, timeout: int) -> Optional[Dict[str, Any]]:
    """备用请求方法（当SDK不可用时）"""
    # 实现备用签名方法
    try:
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        from urllib.parse import urlparse
        parsed = urlparse(url)

        canonical_uri = parsed.path
        if not canonical_uri.endswith('/'):
            canonical_uri += '/'

        canonical_headers = f"host:{parsed.netloc}\nx-sdk-date:{timestamp}\n"
        signed_headers = "host;x-sdk-date"
        payload_hash = hashlib.sha256(b'').hexdigest()

        canonical_query = ""
        if parsed.query:
            params = parsed.query.split('&')
            params.sort()
            encoded_params = []
            for p in params:
                encoded_params.append(p)
            canonical_query = '&'.join(encoded_params)

        canonical_request = f"GET\n{canonical_uri}\n{canonical_query}\n{canonical_headers}{signed_headers}\n{payload_hash}"

        credential_scope = f"{timestamp[:8]}/apigw/sdk-hmac-sha256"
        string_to_sign = f"SDK-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}"

        signing_key = hmac.new(f"HMAC-SHA256{app_secret}".encode(), timestamp[:8].encode(), hashlib.sha256).digest()
        signing_key = hmac.new(signing_key, b"apigw", hashlib.sha256).digest()
        signing_key = hmac.new(signing_key, b"sdk-hmac-sha256", hashlib.sha256).digest()
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()

        authorization = f"SDK-HMAC-SHA256 Access={app_key},SignedHeaders={signed_headers},Signature={signature}"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Authorization": authorization,
            "X-Sdk-Date": timestamp,
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        logger.warning(f"备用请求方法失败: {e}")
        return None


# 保留原有的_make_request函数作为备用，但现在使用新的实现
_make_request_old = _make_request


def _parse_float(value: Any) -> Optional[float]:
    """解析浮点数"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text in ("", "--", "-", "—", "N/A", "NA", "null"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    """解析日期时间"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return dj_timezone.make_aware(value) if dj_timezone.is_naive(value) else value

    text = str(value).strip()
    if not text:
        return None

    # 尝试多种格式
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return dj_timezone.make_aware(parsed)
        except ValueError:
            continue

    # 尝试 ISO 格式
    try:
        parsed = datetime.fromisoformat(text)
        return dj_timezone.make_aware(parsed) if dj_timezone.is_naive(parsed) else parsed
    except ValueError:
        pass

    return None


def _parse_water_quality(value: Any) -> Optional[str]:
    """解析水质类别"""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in ("", "--", "N/A", "null"):
        return None

    # 标准化水质类别
    quality_map = {
        "I": "Ⅰ", "1": "Ⅰ", "一": "Ⅰ",
        "II": "Ⅱ", "2": "Ⅱ", "二": "Ⅱ",
        "III": "Ⅲ", "3": "Ⅲ", "三": "Ⅲ",
        "IV": "Ⅳ", "4": "Ⅳ", "四": "Ⅳ",
        "V": "Ⅴ", "5": "Ⅴ", "五": "Ⅴ",
        "V+": "劣Ⅴ", "劣V": "劣Ⅴ", "劣5": "劣Ⅴ", "劣五": "劣Ⅴ",
    }
    return quality_map.get(text.upper(), text)


def _make_device_id(station_id: str, station_name: str) -> str:
    """生成设备ID"""
    if station_id:
        return f"HW_{station_id}"
    seed = station_name or "unknown"
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]
    return f"HW_{digest}"


def _normalize_record(raw: Dict[str, Any]) -> Optional[HuaweiWaterRecord]:
    """标准化单条记录

    华为API返回的数据格式 (实际响应):
    {
        "province": "贵州省",
        "city": "遵义市",
        "river": "",
        "valley": "长江流域",
        "staname": "沿江渡",
        "sta_time": "2026-02-27 10:00:00",
        "water_l": "2",
        "water_temp": "14.68",
        "sta_ph_v": "8.09",
        "sta_do_v": "9.761",
        "sta_pp_v": "1",
        "sta_an_v": "0.006",
        "sta_tp_v": "0.036",
        "sta_tn_v": "3.273",
        "conductivity": "439.45",
        "turbidity": "21.55"
    }
    """
    # 华为API使用staname作为站点名称
    station_id = raw.get("stationId") or raw.get("station_id") or raw.get("id") or raw.get("staname") or ""
    station_name = raw.get("staname") or raw.get("section") or raw.get("stationName") or raw.get("station_name") or raw.get("name") or ""

    # 构建位置信息：省份-城市-流域
    province = raw.get("province", "")
    city = raw.get("city", "")
    # 华为API使用valley表示流域
    basin = raw.get("valley") or raw.get("basin") or raw.get("river_basin") or ""
    river = raw.get("river", "")
    location_parts = [province, city, basin, river]
    location = " ".join(filter(None, location_parts)) or "未知"

    # 监测时间 - 华为API使用sta_time
    monitor_time = (raw.get("sta_time") or raw.get("monitor_time") or
                    raw.get("monitorTime") or raw.get("time") or raw.get("timestamp"))
    timestamp = _parse_datetime(monitor_time)
    if not timestamp:
        timestamp = dj_timezone.now()

    # 水质类别 - 华为API使用water_l或water_l
    quality = (raw.get("water_l") or raw.get("waterQuality") or
               raw.get("qulity") or raw.get("quality") or raw.get("water_quality"))
    water_quality = _parse_water_quality(quality)

    return HuaweiWaterRecord(
        device_id=_make_device_id(str(station_id), str(station_name)),
        device_name=str(station_name) or f"站点{station_id}",
        location=str(location),
        timestamp=timestamp,
        temperature=_parse_float(raw.get("water_temp") or raw.get("waterTemp") or raw.get("temperature")),
        ph=_parse_float(raw.get("sta_ph_v") or raw.get("ph")),
        dissolved_oxygen=_parse_float(raw.get("sta_do_v") or raw.get("dissolvedoxygen") or
                                     raw.get("dissolvedOxygen") or raw.get("dissolved_oxygen") or raw.get("do")),
        conductivity=_parse_float(raw.get("conductivity")),
        turbidity=_parse_float(raw.get("turbidity")),
        permanganate=_parse_float(raw.get("sta_pp_v") or raw.get("codmn") or
                                  raw.get("permanganate") or raw.get("permanganateIndex")),
        ammonia_nitrogen=_parse_float(raw.get("sta_an_v") or raw.get("nh3-n") or
                                     raw.get("nh3_n") or raw.get("ammoniaNitrogen") or
                                     raw.get("ammonia_nitrogen")),
        total_phosphorus=_parse_float(raw.get("sta_tp_v") or raw.get("tp") or
                                     raw.get("totalPhosphorus") or raw.get("total_phosphorus")),
        total_nitrogen=_parse_float(raw.get("sta_tn_v") or raw.get("tn") or
                                    raw.get("totalNitrogen") or raw.get("total_nitrogen")),
        water_quality=water_quality,
        province=province or None,
        city=city or None,
        river_basin=basin or None,
    )


def fetch_records(force_refresh: bool = False) -> List[HuaweiWaterRecord]:
    """获取华为水数据记录

    Args:
        force_refresh: 是否强制刷新缓存
    """
    config = _get_config()
    if not _is_enabled(config):
        return []

    # 只有在非强制刷新时才使用缓存
    if not force_refresh and _cache_valid(config):
        logger.info(f"使用缓存数据，缓存时间: {_cache.get('fetched_at')}")
        return _cache["records"] or []

    url = config["url"]
    app_key = config["app_key"]
    app_secret = config["app_secret"]
    timeout = config.get("timeout", 15)
    default_params = config.get("default_params", {}).copy()
    stanames = config.get("stanames", [])

    # 强制刷新时，可以添加 pageSize 参数获取更多数据
    if force_refresh and "pageSize" not in default_params:
        default_params["pageSize"] = 100
        logger.info(f"强制刷新模式，设置 pageSize=100")

    try:
        logger.info(f"开始请求华为API: {url}, 参数: {default_params}, 站点数量: {len(stanames)}")
        response = _make_request(url, app_key, app_secret, default_params, timeout, stanames)
        if not response:
            logger.warning("华为API请求失败，响应为空")
            return []

        # 打印原始响应结构（仅打印键和类型，避免日志过大）
        logger.info(f"华为API响应结构: {list(response.keys()) if isinstance(response, dict) else type(response)}")

        # 提取数据列表
        json_path = config.get("json_path", "data")
        data = response
        if json_path:
            for key in json_path.split("."):
                data = data.get(key) if isinstance(data, dict) else None
                if data is None:
                    logger.warning(f"无法按路径 {json_path} 提取数据，当前路径: {key}")
                    break

        if not isinstance(data, list):
            logger.warning(f"华为API返回数据格式错误，期望列表，实际: {type(data)}, 数据: {data}")
            return []

        logger.info(f"华为API返回 {len(data)} 条原始数据")

        records = []
        for i, item in enumerate(data):
            if isinstance(item, dict):
                # 打印第一条数据的结构用于调试
                if i == 0:
                    logger.info(f"第一条数据字段: {list(item.keys())}")
                record = _normalize_record(item)
                if record:
                    records.append(record)

        _cache["records"] = records
        _cache["fetched_at"] = dj_timezone.now()
        logger.info(f"华为水数据获取成功，共 {len(records)} 条有效记录")
        return records

    except Exception as e:
        logger.error(f"华为水数据获取失败: {e}", exc_info=True)
        return []


class HuaweiWaterDataService:
    """华为水数据服务"""

    @staticmethod
    def enabled() -> bool:
        """检查服务是否启用"""
        return _is_enabled(_get_config())

    @staticmethod
    def get_devices() -> List[Dict[str, Any]]:
        """获取设备列表"""
        records = fetch_records()
        devices: Dict[str, Dict[str, Any]] = {}
        for record in records:
            if record.device_id not in devices:
                devices[record.device_id] = {
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "device_type": "sensor",
                    "status": "online",
                    "location": record.location,
                }
        return list(devices.values())

    @staticmethod
    def get_realtime(count: int = 100, force_refresh: bool = False) -> Dict[str, Any]:
        """获取实时数据

        Args:
            count: 返回数量
            force_refresh: 是否强制刷新缓存
        """
        records = fetch_records(force_refresh=force_refresh)
        if not records:
            return {"timestamp": dj_timezone.now().isoformat(), "sensors": []}

        # 按设备分组，取最新数据
        latest_by_device: Dict[str, HuaweiWaterRecord] = {}
        for record in records:
            current = latest_by_device.get(record.device_id)
            if not current or record.timestamp > current.timestamp:
                latest_by_device[record.device_id] = record

        latest_records = sorted(
            latest_by_device.values(),
            key=lambda r: r.timestamp,
            reverse=True
        )[:count]

        sensors = []
        for record in latest_records:
            sensors.append({
                "device_id": record.device_id,
                "device_name": record.device_name,
                "location": record.location,
                "province": record.province,
                "city": record.city,
                "river_basin": record.river_basin,
                "temperature": record.temperature,
                "ph": record.ph,
                "dissolved_oxygen": record.dissolved_oxygen,
                "conductivity": record.conductivity,
                "turbidity": record.turbidity,
                "permanganate": record.permanganate,
                "ammonia_nitrogen": record.ammonia_nitrogen,
                "total_phosphorus": record.total_phosphorus,
                "total_nitrogen": record.total_nitrogen,
                "water_quality": record.water_quality,
                "timestamp": record.timestamp.isoformat(),
            })

        return {
            "timestamp": dj_timezone.now().isoformat(),
            "sensors": sensors,
            "total": len(latest_by_device)
        }

    @staticmethod
    def get_history(device_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """获取历史数据"""
        records = fetch_records()
        if not records:
            return []

        threshold = dj_timezone.now() - timedelta(hours=hours)
        filtered = []
        for record in records:
            if record.device_id != device_id:
                continue
            if record.timestamp and record.timestamp < threshold:
                continue
            filtered.append(record)

        filtered.sort(key=lambda r: r.timestamp)

        def _format_time_label(ts: datetime) -> str:
            if hours <= 24:
                return ts.strftime("%H:%M")
            return ts.strftime("%m-%d")

        return [
            {
                "time": _format_time_label(record.timestamp),
                "timestamp": record.timestamp.isoformat(),
                "temperature": record.temperature,
                "ph": record.ph,
                "dissolved_oxygen": record.dissolved_oxygen,
                "conductivity": record.conductivity,
                "turbidity": record.turbidity,
                "permanganate": record.permanganate,
                "ammonia_nitrogen": record.ammonia_nitrogen,
                "total_phosphorus": record.total_phosphorus,
                "total_nitrogen": record.total_nitrogen,
            }
            for record in filtered
        ]

    @staticmethod
    def get_alerts(count: int = 10) -> List[Dict[str, Any]]:
        """获取告警数据"""
        records = fetch_records()
        alerts = []

        for record in records:
            # 水质类别告警
            if record.water_quality in ["Ⅳ", "Ⅴ", "劣Ⅴ"]:
                alerts.append({
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "type": "water_quality",
                    "level": "warning" if record.water_quality in ["Ⅳ", "Ⅴ"] else "critical",
                    "message": f"水质{record.water_quality}类",
                    "value": record.water_quality,
                    "timestamp": record.timestamp.isoformat(),
                })

            # 温度告警
            if record.temperature is not None and record.temperature > 30:
                alerts.append({
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "type": "temperature",
                    "level": "warning",
                    "message": "水温偏高",
                    "value": record.temperature,
                    "timestamp": record.timestamp.isoformat(),
                })

            # 溶解氧告警
            if record.dissolved_oxygen is not None and record.dissolved_oxygen < 5:
                alerts.append({
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "type": "dissolved_oxygen",
                    "level": "warning",
                    "message": "溶解氧偏低",
                    "value": record.dissolved_oxygen,
                    "timestamp": record.timestamp.isoformat(),
                })

            # pH告警
            if record.ph is not None and (record.ph < 6.5 or record.ph > 8.5):
                alerts.append({
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "type": "ph",
                    "level": "warning",
                    "message": "pH异常",
                    "value": record.ph,
                    "timestamp": record.timestamp.isoformat(),
                })

            if len(alerts) >= count:
                break

        return alerts[:count]
