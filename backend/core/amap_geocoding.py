"""
高德地图地理编码服务
使用高德地图API将地址转换为经纬度坐标
API文档: https://lbs.amap.com/api/webservice/guide/api/georegeo
"""
from __future__ import annotations

import logging
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
        self.api_key = api_key or getattr(settings, "AMAP_API_KEY", "e447cc4ddd22a3be365c4207f6bc3e07")
        self._request_count = 0
        self._last_request_time = 0

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
        self._check_rate_limit()

        url = f"{AMAP_API_BASE}/{endpoint}"
        params['key'] = self.api_key

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # 检查API返回状态
            if data.get('status') == '1' or data.get('status') == 1:
                return data
            else:
                error_code = data.get('infocode', 'unknown')
                error_info = data.get('info', 'unknown error')
                logger.warning(f"高德地图API返回错误: code={error_code}, info={error_info}")
                return None

        except requests.exceptions.RequestException as e:
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

    def geocode_section(self, section_name: str, province: str = None, city: str = None) -> Optional[Tuple[float, float]]:
        """地理编码：专门用于水质断面

        Args:
            section_name: 断面名称
            province: 省份
            city: 城市

        Returns:
            (经度, 纬度) 元组，失败返回None
        """
        # 构建搜索地址，尝试多种组合
        search_addresses = []

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
            result = self.geocode(address, search_city)
            if result:
                return result

        logger.warning(f"断面地理编码失败: {section_name} (省份:{province}, 城市:{city})")
        return None

    def batch_geocode_sections(self, sections: list, city: str = None, province: str = None) -> Dict[str, Tuple[float, float]]:
        """批量地理编码：为多个断面获取经纬度

        Args:
            sections: 断面名称列表
            city: 城市
            province: 省份

        Returns:
            字典，键为断面名称，值为(经度, 纬度)元组
        """
        results = {}

        for section_name in sections:
            coords = self.geocode_section(section_name, province, city)
            if coords:
                results[section_name] = coords
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
