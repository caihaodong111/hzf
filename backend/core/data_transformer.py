"""
数据转换层 - 统一多数据源输出格式
负责将不同数据源的数据转换为统一格式
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from decimal import Decimal


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
            source: 数据来源标识 ('national', 'open', 'simulator', 'database')

        Returns:
            统一格式的数据
        """
        transformed = {
            'data_source': source,
            'device_id': data.get('device_id'),
            'device_name': data.get('device_name'),
            'location': data.get('location'),
            'timestamp': data.get('timestamp') or data.get('recorded_at'),
        }

        # 根据数据来源提取字段
        if source == 'national':
            # 国家水质数据
            transformed.update({
                'province': data.get('province'),
                'river_basin': data.get('river_basin'),
                'water_quality': cls.normalize_water_quality(data.get('water_quality')),
                'temperature': cls._to_float(data.get('temperature')),
                'ph': cls._to_float(data.get('ph')),
                'dissolved_oxygen': cls._to_float(data.get('dissolved_oxygen')),
                'conductivity': cls._to_float(data.get('conductivity')),
                'turbidity': cls._to_float(data.get('turbidity')),
                'permanganate': cls._to_float(data.get('permanganate')),
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
                # 开放数据通常没有省份流域信息
                'province': None,
                'river_basin': None,
                'water_quality': None,
            })

        elif source == 'simulator':
            # 模拟数据
            transformed.update({
                'temperature': cls._to_float(data.get('temperature')),
                'ph': cls._to_float(data.get('ph')),
                'dissolved_oxygen': cls._to_float(data.get('dissolved_oxygen')),
                'salinity': cls._to_float(data.get('salinity')),
                'province': None,
                'river_basin': None,
                'water_quality': None,
            })

        elif source == 'database':
            # 数据库数据
            transformed.update({
                'province': data.get('device__province') or data.get('province'),
                'river_basin': data.get('device__river_basin') or data.get('river_basin'),
                'water_quality': cls.normalize_water_quality(data.get('water_quality')),
                'temperature': cls._to_float(data.get('temperature')),
                'ph': cls._to_float(data.get('ph')),
                'dissolved_oxygen': cls._to_float(data.get('dissolved_oxygen')),
                'conductivity': cls._to_float(data.get('conductivity')),
                'turbidity': cls._to_float(data.get('turbidity')),
                'salinity': cls._to_float(data.get('salinity')),
            })

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
    def sync_device(device_data: Dict[str, Any]) -> Any:
        """同步设备到数据库"""
        from apps.sensors.models import Device

        device_id = device_data.get('device_id')
        if not device_id:
            return None

        defaults = {
            'device_name': device_data.get('device_name', device_id),
            'device_type': device_data.get('device_type', 'sensor'),
            'location': device_data.get('location'),
            'province': device_data.get('province'),
            'province_code': device_data.get('province_code'),
            'river_basin': device_data.get('river_basin'),
            'river_basin_code': device_data.get('river_basin_code'),
            'status': device_data.get('status', 'online'),
        }

        device, created = Device.objects.update_or_create(
            device_id=device_id,
            defaults=defaults
        )
        return device

    @staticmethod
    def sync_sensor_data(data: Dict[str, Any], source: str) -> Any:
        """同步传感器数据到数据库"""
        from datetime import datetime
        from django.utils import timezone
        from apps.sensors.models import Device, SensorData

        device_id = data.get('device_id')
        if not device_id:
            return None

        # 确保设备存在
        try:
            device = Device.objects.get(device_id=device_id)
        except Device.DoesNotExist:
            device = DatabaseSync.sync_device(data)
            if not device:
                return None

        # 解析时间
        recorded_at = DataTransformer._parse_datetime(data.get('timestamp'))
        if not recorded_at:
            recorded_at = timezone.now()

        # 准备数据
        sensor_data = {
            'device': device,
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
            'data_source': source,
            'recorded_at': recorded_at,
        }

        # 创建记录
        return SensorData.objects.create(**sensor_data)

    @staticmethod
    def sync_alert(alert_data: Dict[str, Any], source: str) -> Any:
        """同步告警到数据库"""
        from apps.sensors.models import Device, Alert

        device_id = alert_data.get('device_id')
        if not device_id:
            return None

        # 确保设备存在
        try:
            device = Device.objects.get(device_id=device_id)
        except Device.DoesNotExist:
            device = DatabaseSync.sync_device({
                'device_id': device_id,
                'device_name': alert_data.get('device_name', device_id),
                'device_type': 'sensor',
                'status': 'online',
            })
            if not device:
                return None

        # 解析时间
        created_at = DataTransformer._parse_datetime(alert_data.get('created_at') or alert_data.get('timestamp'))
        if not created_at:
            created_at = datetime.now()

        # 准备数据
        alert = {
            'device': device,
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
