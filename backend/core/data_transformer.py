"""
数据转换层 - 统一多数据源输出格式
负责将不同数据源的数据转换为统一格式
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from decimal import Decimal
import re


class DataTransformer:
    """数据转换器 - 统一多数据源数据格式"""

    # 水质类别映射
    WATER_QUALITY_MAP = {
        '1': 'Ⅰ', 'Ⅰ': 'Ⅰ', 'I': 'Ⅰ',
        '2': 'Ⅱ', 'Ⅱ': 'Ⅱ', 'II': 'Ⅱ',
        '3': 'Ⅲ', 'Ⅲ': 'Ⅲ', 'III': 'Ⅲ',
        '4': 'Ⅳ', 'Ⅳ': 'Ⅳ', 'IV': 'Ⅳ',
        '5': 'Ⅴ', 'Ⅴ': 'Ⅴ', 'V': 'Ⅴ',
        '6': '劣Ⅴ', '劣Ⅴ': '劣Ⅴ', '劣V': '劣Ⅴ', '>5': '劣Ⅴ'
    }

    # 常见城市后缀
    _CITY_SUFFIXES = ('自治州', '地区', '盟', '州', '市', '县', '区')
    _COMMON_CITIES: Set[str] = set()

    @classmethod
    def _load_common_cities(cls) -> None:
        """加载常见城市列表（从provinceCascadeOptions）"""
        if cls._COMMON_CITIES:
            return

        # 主要城市列表（来自前端的provinceCascadeOptions）
        cities = [
            # 直辖市
            '东城区', '西城区', '朝阳区', '海淀区', '丰台区', '石景山区',
            '黄浦区', '徐汇区', '浦东新区', '静安区', '长宁区',
            '和平区', '河东区', '河西区', '南开区', '河北区', '红桥区',
            # 省会城市
            '石家庄市', '唐山市', '保定市', '廊坊市', '邯郸市', '秦皇岛市',
            '太原市', '大同市', '长治市', '临汾市', '运城市', '晋中市',
            '呼和浩特市', '包头市', '鄂尔多斯市', '赤峰市', '呼伦贝尔市',
            '沈阳市', '大连市', '长春市', '吉林市', '哈尔滨市', '齐齐哈尔市',
            '南京市', '苏州市', '无锡市', '常州市', '南通市',
            '杭州市', '宁波市', '温州市', '嘉兴市', '绍兴市',
            '合肥市', '芜湖市', '马鞍山市', '蚌埠市', '滁州市',
            '福州市', '厦门市', '南昌市', '济南市', '青岛市',
            '郑州市', '洛阳市', '开封市', '安阳市', '许昌市',
            '武汉市', '宜昌市', '襄阳市', '黄石市', '荆州市',
            '长沙市', '株洲市', '湘潭市', '衡阳市', '岳阳市',
            '广州市', '深圳市', '佛山市', '东莞市', '珠海市',
            '南宁市', '桂林市', '柳州市', '北海市', '玉林市',
            '海口市', '三亚市',
            '成都市', '绵阳市', '德阳市', '乐山市', '泸州市',
            '贵阳市', '遵义市', '六盘水市', '安顺市', '毕节市',
            '昆明市', '曲靖市', '大理州', '玉溪市', '昭通市',
            '拉萨市', '西安市', '咸阳市', '宝鸡市', '渭南市', '延安市',
            '兰州市', '天水市', '酒泉市', '张掖市', '武威市',
            '西宁市', '银川市', '乌鲁木齐市', '克拉玛依市',
        ]
        cls._COMMON_CITIES = set(cities)

    @classmethod
    def extract_city_from_name(cls, device_name: str, province: str = None) -> Optional[str]:
        """从断面名称中提取城市信息

        Args:
            device_name: 断面名称
            province: 省份（可选，用于缩小匹配范围）

        Returns:
            提取的城市名称，如果没有匹配则返回None
        """
        cls._load_common_cities()

        if not device_name:
            return None

        device_name_clean = device_name.strip()

        # 直接匹配完整城市名
        for city in cls._COMMON_CITIES:
            if city in device_name_clean:
                return city

        # 尝试匹配不带后缀的城市名
        for city in cls._COMMON_CITIES:
            for suffix in cls._CITY_SUFFIXES:
                if city.endswith(suffix) and len(city) > len(suffix):
                    city_without_suffix = city[:-len(suffix)]
                    if city_without_suffix in device_name_clean:
                        return city

        return None

    # 告警类型映射
    ALERT_TYPE_MAP = {
        'temperature': 'temperature',
        'temp': 'temperature',
        '水温': 'temperature',
        'dissolved_oxygen': 'dissolved_oxygen',
        'do': 'dissolved_oxygen',
        '溶解氧': 'dissolved_oxygen',
        'ph': 'ph',
        'pH': 'ph',
        'water_quality': 'water_quality',
        '水质': 'water_quality',
        'conductivity': 'conductivity',
        '电导率': 'conductivity',
        'turbidity': 'turbidity',
        '浊度': 'turbidity',
    }

    # 告警级别映射
    ALERT_LEVEL_MAP = {
        'info': 'info',
        'warning': 'warning',
        'warn': 'warning',
        'critical': 'critical',
        'error': 'critical',
        'danger': 'critical',
    }

    @classmethod
    def normalize_water_quality(cls, quality: Any) -> Optional[str]:
        """标准化水质类别"""
        if not quality:
            return None
        quality_str = str(quality).strip()
        return cls.WATER_QUALITY_MAP.get(quality_str, quality_str)

    @classmethod
    def normalize_alert_type(cls, alert_type: Any) -> str:
        """标准化告警类型"""
        if not alert_type:
            return 'other'
        type_str = str(alert_type).lower().strip()
        return cls.ALERT_TYPE_MAP.get(type_str, type_str)

    @classmethod
    def normalize_alert_level(cls, alert_level: Any) -> str:
        """标准化告警级别"""
        if not alert_level:
            return 'warning'
        level_str = str(alert_level).lower().strip()
        return cls.ALERT_LEVEL_MAP.get(level_str, level_str)

    @classmethod
    def transform_realtime_data(cls, data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """转换实时数据为统一格式

        Args:
            data: 原始数据
            source: 数据来源标识 ('national', 'open', 'database')

        Returns:
            统一格式的数据
        """
        device_name = data.get('device_name')
        province = data.get('province')
        city = data.get('city')

        transformed = {
            'data_source': source,
            'device_id': data.get('device_id'),
            'device_name': device_name,
            'location': data.get('location'),
            'timestamp': data.get('timestamp') or data.get('recorded_at'),
            'city': city,
            # 经纬度坐标
            'longitude': cls._to_float(data.get('longitude')),
            'latitude': cls._to_float(data.get('latitude')),
        }

        # 根据数据来源提取字段
        if source == 'national':
            # 国家水质数据
            transformed.update({
                'province': province,
                'river_basin': data.get('river_basin'),
                'water_quality': cls.normalize_water_quality(data.get('water_quality')),
                'temperature': cls._to_float(data.get('temperature')),
                'ph': cls._to_float(data.get('ph')),
                'dissolved_oxygen': cls._to_float(data.get('dissolved_oxygen')),
                'conductivity': cls._to_float(data.get('conductivity')),
                'turbidity': cls._to_float(data.get('turbidity')),
                'permanganate': cls._to_float(data.get('permanganate')),
                'permanganate_index': cls._to_float(data.get('permanganate')),
                'ammonia_nitrogen': cls._to_float(data.get('ammonia_nitrogen')),
                'total_phosphorus': cls._to_float(data.get('total_phosphorus')),
                'total_nitrogen': cls._to_float(data.get('total_nitrogen')),
                'chlorophyll_a': cls._to_float(data.get('chlorophyll_a')),
                'algae_density': cls._to_float(data.get('algae_density')),
            })

        elif source == 'huawei':
            # 华为水数据
            transformed.update({
                'province': province,
                'river_basin': data.get('river_basin'),
                'water_quality': cls.normalize_water_quality(data.get('water_quality')),
                'temperature': cls._to_float(data.get('temperature')),
                'ph': cls._to_float(data.get('ph')),
                'dissolved_oxygen': cls._to_float(data.get('dissolved_oxygen')),
                'conductivity': cls._to_float(data.get('conductivity')),
                'turbidity': cls._to_float(data.get('turbidity')),
                'permanganate': cls._to_float(data.get('permanganate')),
                'permanganate_index': cls._to_float(data.get('permanganate')),
                'ammonia_nitrogen': cls._to_float(data.get('ammonia_nitrogen')),
                'total_phosphorus': cls._to_float(data.get('total_phosphorus')),
                'total_nitrogen': cls._to_float(data.get('total_nitrogen')),
            })

        elif source == 'open':
            # 开放数据
            transformed.update({
                'temperature': cls._to_float(data.get('temperature')),
                'ph': cls._to_float(data.get('ph')),
                'dissolved_oxygen': cls._to_float(data.get('dissolved_oxygen')),
                'salinity': cls._to_float(data.get('salinity')),
                'permanganate': cls._to_float(data.get('permanganate')),
                'permanganate_index': cls._to_float(data.get('permanganate')),
                'ammonia_nitrogen': cls._to_float(data.get('ammonia_nitrogen')),
                'total_phosphorus': cls._to_float(data.get('total_phosphorus')),
                'total_nitrogen': cls._to_float(data.get('total_nitrogen')),
                'chlorophyll_a': cls._to_float(data.get('chlorophyll_a')),
                'algae_density': cls._to_float(data.get('algae_density')),
                # 开放数据通常没有省份流域信息
                'province': None,
                'river_basin': None,
                'water_quality': None,
            })

        elif source == 'database':
            # 数据库数据
            transformed.update({
                'province': data.get('device__province') or data.get('province'),
                'city': data.get('device__city') or data.get('city'),
                'river_basin': data.get('device__river_basin') or data.get('river_basin'),
                'water_quality': cls.normalize_water_quality(data.get('water_quality')),
                'temperature': cls._to_float(data.get('temperature')),
                'ph': cls._to_float(data.get('ph')),
                'dissolved_oxygen': cls._to_float(data.get('dissolved_oxygen')),
                'conductivity': cls._to_float(data.get('conductivity')),
                'turbidity': cls._to_float(data.get('turbidity')),
                'salinity': cls._to_float(data.get('salinity')),
                'permanganate': cls._to_float(data.get('permanganate')),
                'permanganate_index': cls._to_float(data.get('permanganate')),
                'ammonia_nitrogen': cls._to_float(data.get('ammonia_nitrogen')),
                'total_phosphorus': cls._to_float(data.get('total_phosphorus')),
                'total_nitrogen': cls._to_float(data.get('total_nitrogen')),
                'chlorophyll_a': cls._to_float(data.get('chlorophyll_a')),
                'algae_density': cls._to_float(data.get('algae_density')),
            })

        # 尝试从断面名称中提取城市信息（仅当原始数据中没有城市时）
        if not transformed.get('city'):
            city = cls.extract_city_from_name(device_name, province)
            if city:
                transformed['city'] = city

        return transformed

    @classmethod
    def transform_alert(cls, data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """转换告警数据为统一格式

        Args:
            data: 原始告警数据
            source: 数据来源标识

        Returns:
            统一格式的告警数据
        """
        # 字段映射
        alert_type = data.get('alert_type') or data.get('type')
        alert_level = data.get('alert_level') or data.get('level')
        created_at = data.get('created_at') or data.get('timestamp')

        return {
            'device_id': data.get('device_id'),
            'device_name': data.get('device_name'),
            'alert_type': cls.normalize_alert_type(alert_type),
            'alert_level': cls.normalize_alert_level(alert_level),
            'message': data.get('message', '数据异常'),
            'value': cls._to_decimal(data.get('value')),
            'value_unit': data.get('value_unit'),
            'resolved': data.get('resolved', False),
            'created_at': created_at,
            'data_source': source,
        }

    @classmethod
    def transform_device(cls, data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """转换设备数据为统一格式"""
        return {
            'device_id': data.get('device_id'),
            'device_name': data.get('device_name', data.get('device_id')),
            'device_type': data.get('device_type', 'sensor'),
            'location': data.get('location'),
            'province': data.get('province'),
            'province_code': data.get('province_code'),
            'river_basin': data.get('river_basin'),
            'river_basin_code': data.get('river_basin_code'),
            'status': data.get('status', 'online'),
            'data_source': source,
        }

    @classmethod
    def transform_historical(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """转换历史数据为统一格式"""
        timestamp = data.get('timestamp') or data.get('recorded_at')
        time = data.get('time')

        # 格式化时间标签
        if timestamp:
            dt = cls._parse_datetime(timestamp)
            if dt:
                if not time:
                    time = dt.strftime('%H:%M') if dt.hour >= 6 else dt.strftime('%m-%d')
        elif time:
            dt = cls._parse_datetime(time)

        return {
            'time': time or '--:--',
            'timestamp': timestamp,
            'temperature': cls._to_float(data.get('temperature')),
            'ph': cls._to_float(data.get('ph')),
            'dissolved_oxygen': cls._to_float(data.get('dissolved_oxygen')),
            'conductivity': cls._to_float(data.get('conductivity')),
            'turbidity': cls._to_float(data.get('turbidity')),
            'salinity': cls._to_float(data.get('salinity')),
        }

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        """安全转换为浮点数"""
        if value is None or value == '' or value == '--':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_decimal(value: Any) -> Optional[Decimal]:
        """安全转换为Decimal"""
        if value is None or value == '' or value == '--':
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """解析日期时间"""
        from datetime import datetime
        from django.utils import timezone

        if not value:
            return None
        if isinstance(value, datetime):
            return value

        # 尝试常见格式
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%m-%d %H:%M',
            '%Y-%m-%d',
        ]

        value_str = str(value).strip()
        for fmt in formats:
            try:
                parsed = datetime.strptime(value_str, fmt)
                # 如果没有年份，使用当前年份
                if parsed.year == 1900:
                    parsed = parsed.replace(year=datetime.now().year)
                return parsed
            except ValueError:
                continue

        return None


class DatabaseSync:
    """数据库同步器 - 将外部数据同步到数据库"""

    @staticmethod
    def sync_sensor_data(data: Dict[str, Any], source: str) -> Any:
        """同步传感器数据到数据库"""
        from datetime import datetime
        from django.utils import timezone
        from apps.sensors.models import SensorData

        device_id = data.get('device_id')
        if not device_id:
            return None

        # 解析时间
        recorded_at = DataTransformer._parse_datetime(data.get('timestamp'))
        if not recorded_at:
            recorded_at = timezone.now()

        # 准备数据
        sensor_data = {
            'device_id': device_id,
            'device_name': data.get('device_name', device_id),
            'temperature': DataTransformer._to_float(data.get('temperature')),
            'ph': DataTransformer._to_float(data.get('ph')),
            'dissolved_oxygen': DataTransformer._to_float(data.get('dissolved_oxygen')),
            'conductivity': DataTransformer._to_float(data.get('conductivity')),
            'turbidity': DataTransformer._to_float(data.get('turbidity')),
            'salinity': DataTransformer._to_float(data.get('salinity')),
            'water_quality': DataTransformer.normalize_water_quality(data.get('water_quality')),
            'permanganate': DataTransformer._to_float(data.get('permanganate')),
            'ammonia_nitrogen': DataTransformer._to_float(data.get('ammonia_nitrogen')),
            'total_phosphorus': DataTransformer._to_float(data.get('total_phosphorus')),
            'total_nitrogen': DataTransformer._to_float(data.get('total_nitrogen')),
            'chlorophyll_a': DataTransformer._to_float(data.get('chlorophyll_a')),
            'algae_density': DataTransformer._to_float(data.get('algae_density')),
            'data_source': source,
            'recorded_at': recorded_at,
        }

        # 创建记录
        return SensorData.objects.create(**sensor_data)

    @staticmethod
    def sync_alert(alert_data: Dict[str, Any], source: str) -> Any:
        """同步告警到数据库"""
        from datetime import datetime
        from apps.sensors.models import Alert

        device_id = alert_data.get('device_id')
        if not device_id:
            return None

        # 解析时间
        created_at = DataTransformer._parse_datetime(alert_data.get('created_at') or alert_data.get('timestamp'))
        if not created_at:
            created_at = datetime.now()

        # 准备数据
        alert = {
            'device_id': device_id,
            'device_name': alert_data.get('device_name', device_id),
            'alert_type': DataTransformer.normalize_alert_type(alert_data.get('alert_type') or alert_data.get('type')),
            'alert_level': DataTransformer.normalize_alert_level(alert_data.get('alert_level') or alert_data.get('level')),
            'message': alert_data.get('message', '数据异常'),
            'value': DataTransformer._to_decimal(alert_data.get('value')),
            'value_unit': alert_data.get('value_unit'),
            'resolved': alert_data.get('resolved', False),
            'data_source': source,
            'created_at': created_at,
        }

        return Alert.objects.create(**alert)
