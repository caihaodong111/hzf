"""
国家水质自动综合监管平台数据服务
数据来源：https://szzdjc.cnemc.cn:8070
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)


# 区域代码映射
AREA_CODES = {
    "全国": "",
    "北京市": "110000", "天津市": "120000", "河北省": "130000",
    "山西省": "140000", "内蒙古自治区": "150000", "辽宁省": "210000",
    "吉林省": "220000", "黑龙江省": "230000", "上海市": "310000",
    "江苏省": "320000", "浙江省": "330000", "安徽省": "340000",
    "福建省": "350000", "江西省": "360000", "山东省": "370000",
    "河南省": "410000", "湖北省": "420000", "湖南省": "430000",
    "广东省": "440000", "广西壮族自治区": "450000", "海南省": "460000",
    "重庆市": "500000", "四川省": "510000", "贵州省": "520000",
    "云南省": "530000", "西藏自治区": "540000", "陕西省": "610000",
    "甘肃省": "620000", "青海省": "630000", "宁夏回族自治区": "640000",
    "新疆维吾尔自治区": "650000",
}

# 流域代码映射
RIVER_CODES = {
    "所有流域": "",
    "长江流域": "1100000000",
    "黄河流域": "0900000000",
    "珠江流域": "1500000000",
    "松花江流域": "0200000000",
    "淮河流域": "1000000000",
    "海河流域": "6010000000",
    "辽河流域": "0500000000",
    "浙闽片河流": "ZMP",
    "西南诸河": "6040000000",
    "西北诸河": "0800000000",
    "太湖流域": "1200000000",
    "巢湖流域": "1300000000",
    "滇池流域": "1700000000"
}


@dataclass
class WaterQualityRecord:
    """水质数据记录"""
    device_id: str
    device_name: str
    location: str
    province: str
    river_basin: str
    water_quality: str  # 水质类别 Ⅰ-劣Ⅴ类
    timestamp: datetime
    temperature: Optional[float]  # 水温
    ph: Optional[float]
    dissolved_oxygen: Optional[float]  # 溶解氧
    conductivity: Optional[float]  # 电导率 μS/cm
    turbidity: Optional[float]  # 浊度 NTU
    permanganate: Optional[float]  # 高锰酸盐指数 mg/L
    ammonia_nitrogen: Optional[float]  # 氨氮 mg/L
    total_phosphorus: Optional[float]  # 总磷 mg/L
    total_nitrogen: Optional[float]  # 总氮 mg/L


class NationalWaterDataAPI:
    """国家水质数据API客户端"""

    BASE_URL = "https://szzdjc.cnemc.cn:8070"
    API_URL = f"{BASE_URL}/GJZ/Ajax/Publish.ashx"

    # 表头索引（基于API返回的thead）
    HEADERS = [
        "省份", "流域", "断面名称", "监测时间", "水质类别",
        "水温", "pH", "溶解氧", "电导率", "浊度",
        "高锰酸盐指数", "氨氮", "总磷", "总氮"
    ]

    def __init__(self):
        self._cache: Dict[str, Any] = {"records": None, "fetched_at": None}
        self._cache_minutes = getattr(settings, "NATIONAL_WATER_DATA_CACHE_MINUTES", 20)

    def _cache_valid(self) -> bool:
        """检查缓存是否有效"""
        fetched_at = self._cache.get("fetched_at")
        if not fetched_at:
            return False
        return dj_timezone.now() - fetched_at < dj_timezone.timedelta(minutes=self._cache_minutes)

    def _fetch_data(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """发送请求获取数据"""
        try:
            # 构建POST数据
            post_data = urllib.parse.urlencode(params).encode('utf-8')

            # 创建请求
            req = urllib.request.Request(
                self.API_URL,
                data=post_data,
                method='POST',
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )

            # 忽略SSL证书验证
            import ssl
            context = ssl._create_unverified_context()

            with urllib.request.urlopen(req, timeout=30, context=context) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data

        except Exception as e:
            logger.warning(f"国家水质数据获取失败: {e}")
            return None

    def _clean_value(self, value: Any, col_index: int = None) -> Any:
        """清理数据值"""
        if not value or value == "--":
            return None

        if isinstance(value, str):
            # 处理监测时间（第4列，索引3）- 添加年份
            if col_index == 3 and re.match(r'^\d{2}-\d{2}\s+\d{2}:\d{2}$', value):
                current_year = datetime.now().year
                return f"{current_year}-{value}"

            # 提取span标签中的值
            span_match = re.search(r"<span[^>]*title='([^']*)'[^>]*>(.*?)</span>", value)
            if span_match:
                return span_match.group(2).strip()

            # 去除HTML标签
            value = re.sub(r'<br/>.*', '', value)
            value = re.sub(r'<[^>]+>', '', value)
            value = value.strip()

            if not value or value == "--":
                return None

        return value

    def _parse_float(self, value: Any) -> Optional[float]:
        """解析浮点数"""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """解析日期时间"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value

        text = str(value).strip()
        if not text:
            return None

        # 尝试多种格式
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%m-%d %H:%M",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(text, fmt)
                # 如果没有年份，添加当前年份
                if fmt == "%m-%d %H:%M":
                    parsed = parsed.replace(year=datetime.now().year)
                # 添加时区
                return dj_timezone.make_aware(parsed)
            except ValueError:
                continue

        return None

    def _make_device_id(self, section_name: str, province: str) -> str:
        """生成设备ID"""
        seed = f"{province}_{section_name}"
        digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]
        return f"NW_{digest}"

    def _parse_record(self, row: List[Any]) -> Optional[WaterQualityRecord]:
        """解析单条记录"""
        if len(row) < 5:
            return None

        province = self._clean_value(row[0]) or "未知"
        river_basin = self._clean_value(row[1]) or "未知"
        section_name = self._clean_value(row[2])
        monitor_time = self._clean_value(row[3], col_index=3)
        water_quality = self._clean_value(row[4]) or ""

        if not section_name:
            return None

        timestamp = self._parse_datetime(monitor_time)
        if not timestamp:
            timestamp = dj_timezone.now()

        device_id = self._make_device_id(section_name, province)
        location = f"{province} - {river_basin}"

        # 解析监测数据（索引从5开始）
        temperature = self._parse_float(self._clean_value(row[5] if len(row) > 5 else None))
        ph = self._parse_float(self._clean_value(row[6] if len(row) > 6 else None))
        dissolved_oxygen = self._parse_float(self._clean_value(row[7] if len(row) > 7 else None))
        conductivity = self._parse_float(self._clean_value(row[8] if len(row) > 8 else None))
        turbidity = self._parse_float(self._clean_value(row[9] if len(row) > 9 else None))
        permanganate = self._parse_float(self._clean_value(row[10] if len(row) > 10 else None))
        ammonia_nitrogen = self._parse_float(self._clean_value(row[11] if len(row) > 11 else None))
        total_phosphorus = self._parse_float(self._clean_value(row[12] if len(row) > 12 else None))
        total_nitrogen = self._parse_float(self._clean_value(row[13] if len(row) > 13 else None))

        return WaterQualityRecord(
            device_id=device_id,
            device_name=section_name,
            location=location,
            province=province,
            river_basin=river_basin,
            water_quality=water_quality,
            timestamp=timestamp,
            temperature=temperature,
            ph=ph,
            dissolved_oxygen=dissolved_oxygen,
            conductivity=conductivity,
            turbidity=turbidity,
            permanganate=permanganate,
            ammonia_nitrogen=ammonia_nitrogen,
            total_phosphorus=total_phosphorus,
            total_nitrogen=total_nitrogen,
        )

    def fetch_records(
        self,
        area_id: str = "",
        river_id: str = "",
        search_name: str = "",
        force_refresh: bool = False,
        max_pages: int = 5
    ) -> List[WaterQualityRecord]:
        """获取水质数据记录"""
        # 有筛选条件时禁用缓存
        has_filters = bool(area_id or river_id or search_name)

        # 检查缓存
        if not has_filters and not force_refresh and self._cache_valid():
            return self._cache.get("records", [])

        all_records = []

        for page in range(1, max_pages + 1):
            params = {
                "action": "getRealDatas",
                "AreaID": area_id,
                "RiverID": river_id,
                "MNName": search_name,
                "PageIndex": page,
                "PageSize": 60
            }

            data = self._fetch_data(params)
            if not data or not data.get("result"):
                break

            tbody = data.get("tbody", [])
            if not tbody:
                break

            for row in tbody:
                record = self._parse_record(row)
                if record:
                    all_records.append(record)

            total = data.get("total", 1)
            if page >= total:
                break

        # 只在无筛选条件时更新缓存
        if not has_filters:
            self._cache["records"] = all_records
            self._cache["fetched_at"] = dj_timezone.now()

        logger.info(f"获取国家水质数据成功，共 {len(all_records)} 条记录")
        return all_records


# 全局实例
_api_instance = NationalWaterDataAPI()


class NationalWaterDataService:
    """国家水质数据服务"""

    @staticmethod
    def api() -> NationalWaterDataAPI:
        """获取API实例"""
        return _api_instance

    @staticmethod
    def enabled() -> bool:
        """检查服务是否启用"""
        return getattr(settings, "NATIONAL_WATER_DATA_ENABLED", True)

    @staticmethod
    def get_devices(
        area_id: str = "",
        river_id: str = "",
        search_name: str = ""
    ) -> List[Dict[str, Any]]:
        """获取设备（断面）列表"""
        if not NationalWaterDataService.enabled():
            return []

        records = _api_instance.fetch_records(
            area_id=area_id,
            river_id=river_id,
            search_name=search_name,
            max_pages=3
        )

        devices: Dict[str, Dict[str, Any]] = {}
        for record in records:
            if record.device_id not in devices:
                devices[record.device_id] = {
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "device_type": "sensor",
                    "status": "online",
                    "location": record.location,
                    "province": record.province,
                    "river_basin": record.river_basin,
                }

        return list(devices.values())

    @staticmethod
    def get_realtime(count: int = 10, **filters) -> Dict[str, Any]:
        """获取实时数据"""
        if not NationalWaterDataService.enabled():
            return {"timestamp": dj_timezone.now().isoformat(), "sensors": []}

        area_id = filters.get("area_id", "")
        river_id = filters.get("river_id", "")
        search_name = filters.get("search_name", "")
        force_refresh = bool(filters.get("force_refresh", False))

        # 有筛选条件时获取更多页数
        has_filters = bool(area_id or river_id or search_name)
        max_pages = 10 if has_filters else 3

        records = _api_instance.fetch_records(
            area_id=area_id,
            river_id=river_id,
            search_name=search_name,
            force_refresh=force_refresh,
            max_pages=max_pages
        )

        if not records:
            return {"timestamp": dj_timezone.now().isoformat(), "sensors": []}

        # 按设备分组，取最新数据
        latest_by_device: Dict[str, WaterQualityRecord] = {}
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
                "river_basin": record.river_basin,
                "water_quality": record.water_quality,
                "temperature": record.temperature,
                "ph": record.ph,
                "dissolved_oxygen": record.dissolved_oxygen,
                "conductivity": record.conductivity,
                "turbidity": record.turbidity,
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
        if not NationalWaterDataService.enabled():
            return []

        records = _api_instance.fetch_records(max_pages=10)

        # 筛选指定设备的数据
        filtered = []
        for record in records:
            if record.device_id != device_id:
                continue

            # 时间筛选
            threshold = dj_timezone.now() - dj_timezone.timedelta(hours=hours)
            if record.timestamp and record.timestamp < threshold:
                continue

            filtered.append(record)

        filtered.sort(key=lambda r: r.timestamp)

        # 格式化时间标签
        def _format_time_label(ts: datetime) -> str:
            if hours >= 24:
                return ts.strftime("%m-%d")
            return ts.strftime("%H:%M")

        return [
            {
                "time": _format_time_label(record.timestamp),
                "timestamp": record.timestamp.isoformat(),
                "temperature": record.temperature,
                "ph": record.ph,
                "dissolved_oxygen": record.dissolved_oxygen,
                "conductivity": record.conductivity,
                "turbidity": record.turbidity,
            }
            for record in filtered
        ]

    @staticmethod
    def get_alerts(count: int = 10) -> List[Dict[str, Any]]:
        """获取告警数据"""
        if not NationalWaterDataService.enabled():
            return []

        records = _api_instance.fetch_records(max_pages=5)
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

    @staticmethod
    def get_areas() -> List[Dict[str, Any]]:
        """获取区域列表"""
        return [
            {"code": code, "name": name}
            for name, code in AREA_CODES.items()
        ]

    @staticmethod
    def get_rivers() -> List[Dict[str, Any]]:
        """获取流域列表"""
        return [
            {"code": code, "name": name}
            for name, code in RIVER_CODES.items()
        ]
