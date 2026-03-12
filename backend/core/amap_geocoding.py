"""
高德地图地理编码服务
使用高德地图API将地址转换为经纬度坐标
API文档: https://lbs.amap.com/api/webservice/guide/api/georegeo
"""
from __future__ import annotations

import logging
import re
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


# 高德地图API配置
AMAP_API_BASE = "https://restapi.amap.com/v3"


class AmapGeocodingService:
    """高德地图地理编码服务"""

    def __init__(self, api_key: str = None):
        """
        初始化服务

        Args:
            api_key: 高德地图API Key，如果不提供则从配置中读取
        """
        # 高德 Web 服务 API 需要“Web服务 Key”，不能用 JS API Key，否则会报 10009 USERKEY_PLAT_NOMATCH
        settings_key = (
            getattr(settings, "AMAP_WEB_SERVICE_KEY", None)
            or getattr(settings, "AMAP_API_KEY", None)
        )
        self.api_key = (api_key or settings_key or "").strip()
        self._request_count = 0
        self._last_request_time = 0

    def _normalize_place_query(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        # 统一括号字符，减少搜索噪音
        text = text.replace("（", "(").replace("）", ")")
        # 去掉常见泛化后缀
        text = re.sub(r"(监测)?断面$", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _check_rate_limit(self) -> None:
        """检查并处理API请求频率限制
        高德地图个人开发者配额：每秒最多5次请求
        """
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time

        # 如果距离上次请求不足0.2秒（200ms），则等待
        if time_since_last_request < 0.2:
            time.sleep(0.2 - time_since_last_request)

        self._last_request_time = time.time()
        self._request_count += 1

    def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """发送请求到高德地图API

        Args:
            endpoint: API端点路径
            params: 请求参数

        Returns:
            API响应数据，失败返回None
        """
        if not self.api_key:
            logger.warning("未配置高德 Web 服务 Key（AMAP_WEB_SERVICE_KEY / AMAP_API_KEY），跳过地理编码请求。")
            return None
        url = f"{AMAP_API_BASE}/{endpoint}"
        params["key"] = self.api_key

        # 一些错误（如 30001 ENGINE_RESPONSE_DATA_ERROR）是高德侧引擎抖动，短暂重试通常可恢复。
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            self._check_rate_limit()
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "1" or data.get("status") == 1:
                    return data

                error_code = str(data.get("infocode", "unknown"))
                error_info = data.get("info", "unknown error")
                logger.warning(f"高德地图API返回错误: code={error_code}, info={error_info}")

                if error_code in {"30001"} and attempt < max_attempts:
                    time.sleep(0.4 * attempt)
                    continue
                return None

            except requests.exceptions.RequestException as e:
                if attempt < max_attempts:
                    time.sleep(0.4 * attempt)
                    continue
                logger.error(f"高德地图API请求失败: {e}")
                return None
            except Exception as e:
                logger.error(f"高德地图API处理失败: {e}")
                return None

    def geocode(self, address: str, city: str = None) -> Optional[Tuple[float, float]]:
        """地理编码：将地址转换为经纬度坐标

        Args:
            address: 待解析的地址（如断面名称）
            city: 指定查询的城市，可提高准确度

        Returns:
            (经度, 纬度) 元组，失败返回None
        """
        if not address:
            return None

        # 构建缓存键
        cache_key = f"amap_geocode:{address}:{city or ''}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        params = {
            'address': address,
        }

        if city:
            params['city'] = city

        result = self._make_request('geocode/geo', params)

        if result and result.get('geocodes'):
            geocodes = result['geocodes']
            if geocodes and len(geocodes) > 0:
                # 获取第一个结果的坐标
                location = geocodes[0].get('location', '')
                if location:
                    # 位置格式: "经度,纬度"
                    parts = location.split(',')
                    if len(parts) == 2:
                        try:
                            lon = float(parts[0])
                            lat = float(parts[1])
                            result_tuple = (lon, lat)
                            # 缓存结果1天
                            cache.set(cache_key, result_tuple, 86400)
                            logger.info(f"地理编码成功: {address} ({city}) -> ({lon:.6f}, {lat:.6f})")
                            return result_tuple
                        except ValueError:
                            logger.warning(f"坐标格式错误: {location}")
                            return None

        logger.warning(f"地理编码失败: {address} ({city})")
        return None

    def place_text(
        self,
        keywords: str,
        city: str = None,
        citylimit: bool = True,
        offset: int = 10,
    ) -> Optional[Tuple[float, float]]:
        """
        POI 关键字搜索（对“桥/闸/水库/大桥”等站点名更友好，优先于 geocode/geo）。

        文档: https://lbs.amap.com/api/webservice/guide/api/search
        """
        query = self._normalize_place_query(keywords)
        if not query:
            return None

        cache_key = f"amap_place_text:{query}:{city or ''}:{int(citylimit)}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        params: Dict[str, object] = {
            "keywords": query,
            "offset": int(offset),
            "page": 1,
            "extensions": "base",
        }
        if city:
            params["city"] = city
            params["citylimit"] = "true" if citylimit else "false"

        result = self._make_request("place/text", params)
        pois = (result or {}).get("pois") or []
        if not pois:
            return None

        def parse_location(loc: str) -> Optional[Tuple[float, float]]:
            if not loc:
                return None
            parts = loc.split(",")
            if len(parts) != 2:
                return None
            try:
                return (float(parts[0]), float(parts[1]))
            except ValueError:
                return None

        def is_gov_poi(poi: Dict) -> bool:
            name = str(poi.get("name") or "")
            return any(token in name for token in ("人民政府", "市政府", "区政府", "县政府"))

        picked = None
        for poi in pois:
            if is_gov_poi(poi):
                continue
            picked = poi
            break
        if picked is None:
            picked = pois[0]

        coords = parse_location(picked.get("location", ""))
        if coords:
            cache.set(cache_key, coords, 86400)
            return coords
        return None

    def geocode_section(self, section_name: str, province: str = None, city: str = None) -> Optional[Tuple[float, float]]:
        """地理编码：专门用于水质断面

        Args:
            section_name: 断面名称
            province: 省份
            city: 城市

        Returns:
            (经度, 纬度) 元组，失败返回None
        """
        section_name = self._normalize_place_query(section_name)
        if not section_name:
            return None

        # 构建搜索地址，尝试多种组合
        search_addresses = []

        # 0. 优先用 POI 搜索（对桥/闸/水库等更准确）
        scope = city or province
        poi_coords = self.place_text(section_name, city=scope, citylimit=True)
        if poi_coords:
            return poi_coords

        # 1. 断面名称 + 城市（最准确）
        if city:
            search_addresses.append(f"{section_name} {city}")

        # 2. 断面名称 + 省份
        if province:
            search_addresses.append(f"{section_name} {province}")

        # 3. 断面名称 + 城市 + 省份
        if city and province:
            search_addresses.append(f"{section_name} {city} {province}")

        # 4. 只用断面名称
        search_addresses.append(section_name)

        # 5. 断面名称 + "断面"
        search_addresses.append(f"{section_name}断面")

        # 6. 断面名称 + "监测断面"
        search_addresses.append(f"{section_name}监测断面")

        # 尝试各种地址组合
        for address in search_addresses:
            # 使用城市或省份作为查询范围
            search_city = city or province
            # POI 搜索一次（带上组合地址）
            poi_coords = self.place_text(address, city=search_city, citylimit=True)
            if poi_coords:
                return poi_coords
            result = self.geocode(address, search_city)
            if result:
                return result

        logger.warning(f"断面地理编码失败: {section_name} (省份:{province}, 城市:{city})")
        return None

    def batch_geocode_sections(self, sections: list, city: str = None, province: str = None) -> Dict[str, Tuple[float, float]]:
        """批量地理编码：为多个断面获取经纬度

        Args:
            sections: 断面列表，支持字符串名称或包含 name/city/province/key 的字典
            city: 默认城市
            province: 默认省份

        Returns:
            字典，键为断面标识，值为(经度, 纬度)元组
        """
        results = {}

        for section_name in sections:
            if isinstance(section_name, dict):
                name = section_name.get("name") or section_name.get("station_name") or section_name.get("device_name")
                query = section_name.get("query") or section_name.get("location") or name
                key = (
                    section_name.get("key")
                    or section_name.get("station_id")
                    or section_name.get("device_id")
                    or name
                )
                section_city = section_name.get("city") or city
                section_province = section_name.get("province") or province
            else:
                name = section_name
                query = name
                key = section_name
                section_city = city
                section_province = province

            if not query:
                continue

            coords = self.geocode_section(query, section_province, section_city)
            if coords:
                results[key] = coords
            # 避免请求过快
            time.sleep(0.3)

        logger.info(f"批量地理编码完成: {len(results)}/{len(sections)} 成功")
        return results

    def get_static_map_url(
        self,
        center: Tuple[float, float],
        zoom: int = 10,
        size: str = "1000*620",
        markers: list = None
    ) -> str:
        """生成静态地图URL

        Args:
            center: 地图中心点 (经度, 纬度)
            zoom: 缩放级别 (3-18)
            size: 地图尺寸 "宽*高"
            markers: 标记点列表，每个元素为 (经度, 纬度) 元组

        Returns:
            静态地图URL
        """
        params = {
            'location': f"{center[0]:.6f},{center[1]:.6f}",
            'zoom': zoom,
            'size': size,
            'key': self.api_key
        }

        # 添加标记点
        if markers:
            # 高德地图标记点格式: 经度,纬度;经度,纬度;...
            marker_locations = ';'.join([f"{lon:.6f},{lat:.6f}" for lon, lat in markers])
            params['markers'] = f"mid,,A:{marker_locations}"

        url = f"{AMAP_API_BASE}/staticmap?{urlencode(params)}"
        return url

    def calculate_bounds(self, coordinates: list) -> Tuple[Tuple[float, float], Tuple[float, float], int]:
        """计算多个坐标点的边界和合适的缩放级别

        Args:
            coordinates: 坐标列表，每个元素为 (经度, 纬度) 元组

        Returns:
            (中心点(经度,纬度), 西南角(经度,纬度), 缩放级别)
        """
        if not coordinates:
            return ((116.397428, 39.90923), (116.397428, 39.90923), 10)

        min_lon = min(coord[0] for coord in coordinates)
        max_lon = max(coord[0] for coord in coordinates)
        min_lat = min(coord[1] for coord in coordinates)
        max_lat = max(coord[1] for coord in coordinates)

        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2

        # 根据经纬度范围计算缩放级别
        lon_diff = max_lon - min_lon
        lat_diff = max_lat - min_lat
        max_diff = max(lon_diff, lat_diff)

        # 简单的缩放级别估算
        if max_diff < 0.01:
            zoom = 15
        elif max_diff < 0.05:
            zoom = 13
        elif max_diff < 0.1:
            zoom = 11
        elif max_diff < 0.5:
            zoom = 9
        elif max_diff < 1:
            zoom = 7
        elif max_diff < 2:
            zoom = 6
        elif max_diff < 5:
            zoom = 5
        else:
            zoom = 4

        return ((center_lon, center_lat), (min_lon, min_lat), zoom)


# 全局服务实例
_service_instance = None


def get_amap_service() -> AmapGeocodingService:
    """获取高德地图服务实例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = AmapGeocodingService()
    return _service_instance
