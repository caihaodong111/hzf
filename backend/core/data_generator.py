"""
传感器数据生成器
用于生成模拟的传感器数据用于展示
"""
import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker('zh_CN')


class SensorDataGenerator:
    """传感器数据生成器"""

    # 数据范围配置
    TEMP_MIN = 18.0  # 最低温度
    TEMP_MAX = 32.0  # 最高温度
    TEMP_BASE = 26.0  # 基础温度

    SALINITY_MIN = 30.0  # 最低盐度
    SALINITY_MAX = 40.0  # 最高盐度
    SALINITY_BASE = 35.0  # 基础盐度

    DO_MIN = 5.0  # 最低溶解氧
    DO_MAX = 10.0  # 最高溶解氧
    DO_BASE = 7.0  # 基础溶解氧

    PH_MIN = 6.5  # 最低pH
    PH_MAX = 8.5  # 最高pH
    PH_BASE = 7.5  # 基础pH

    PERMANGANATE_MIN = 1.0  # 高锰酸盐指数最低值
    PERMANGANATE_MAX = 8.0  # 高锰酸盐指数最高值
    AMMONIA_MIN = 0.01  # 氨氮最低值
    AMMONIA_MAX = 1.5  # 氨氮最高值
    TOTAL_P_MIN = 0.01  # 总磷最低值
    TOTAL_P_MAX = 0.5  # 总磷最高值
    TOTAL_N_MIN = 0.2  # 总氮最低值
    TOTAL_N_MAX = 2.5  # 总氮最高值
    CHLOROPHYLL_A_MIN = 0.5  # 叶绿素a最低值
    CHLOROPHYLL_A_MAX = 40.0  # 叶绿素a最高值
    ALGAE_DENSITY_MIN = 1_000  # 藻密度最低值
    ALGAE_DENSITY_MAX = 800_000  # 藻密度最高值

    @classmethod
    def generate_temperature(cls, base_value=None):
        """
        生成温度数据 (18-35℃)

        Args:
            base_value: 基础值，用于生成波动较小的数据

        Returns:
            float: 温度值
        """
        if base_value is None:
            base_value = cls.TEMP_BASE
        variation = random.uniform(-3, 5)
        value = base_value + variation
        # 限制在合理范围内
        return round(max(cls.TEMP_MIN, min(cls.TEMP_MAX, value)), 1)

    @classmethod
    def generate_salinity(cls, base_value=None):
        """
        生成盐度数据 (30-40‰)

        Args:
            base_value: 基础值

        Returns:
            float: 盐度值
        """
        if base_value is None:
            base_value = cls.SALINITY_BASE
        variation = random.uniform(-2, 3)
        value = base_value + variation
        return round(max(cls.SALINITY_MIN, min(cls.SALINITY_MAX, value)), 1)

    @classmethod
    def generate_dissolved_oxygen(cls, base_value=None):
        """
        生成溶解氧数据 (5-10 mg/L)

        Args:
            base_value: 基础值

        Returns:
            float: 溶解氧值
        """
        if base_value is None:
            base_value = cls.DO_BASE
        variation = random.uniform(-1.5, 2)
        value = base_value + variation
        return round(max(cls.DO_MIN, min(cls.DO_MAX, value)), 1)

    @classmethod
    def generate_ph(cls, base_value=None):
        """
        生成pH值数据 (6.5-8.5)

        Args:
            base_value: 基础值

        Returns:
            float: pH值
        """
        if base_value is None:
            base_value = cls.PH_BASE
        variation = random.uniform(-0.8, 0.8)
        value = base_value + variation
        return round(max(cls.PH_MIN, min(cls.PH_MAX, value)), 1)

    @classmethod
    def generate_permanganate_index(cls):
        """生成高锰酸盐指数 (mg/L)"""
        value = random.uniform(cls.PERMANGANATE_MIN, cls.PERMANGANATE_MAX)
        return round(value, 2)

    @classmethod
    def generate_ammonia_nitrogen(cls):
        """生成氨氮 (mg/L)"""
        value = random.uniform(cls.AMMONIA_MIN, cls.AMMONIA_MAX)
        return round(value, 3)

    @classmethod
    def generate_total_phosphorus(cls):
        """生成总磷 (mg/L)"""
        value = random.uniform(cls.TOTAL_P_MIN, cls.TOTAL_P_MAX)
        return round(value, 3)

    @classmethod
    def generate_total_nitrogen(cls):
        """生成总氮 (mg/L)"""
        value = random.uniform(cls.TOTAL_N_MIN, cls.TOTAL_N_MAX)
        return round(value, 3)

    @classmethod
    def generate_chlorophyll_a(cls):
        """生成叶绿素a (mg/L)"""
        value = random.uniform(cls.CHLOROPHYLL_A_MIN, cls.CHLOROPHYLL_A_MAX)
        return round(value, 2)

    @classmethod
    def generate_algae_density(cls):
        """生成藻密度 (cells/L)"""
        return round(random.uniform(cls.ALGAE_DENSITY_MIN, cls.ALGAE_DENSITY_MAX), 0)

    @classmethod
    def generate_sensor_data(cls, device_id=None, device_name=None, province=None, river_basin=None):
        """
        生成完整的传感器数据

        Args:
            device_id: 设备ID，如果不指定则随机生成
            device_name: 设备名称（断面名称）
            province: 省份
            river_basin: 流域

        Returns:
            dict: 包含所有传感器参数的字典
        """
        if device_id is None:
            device_id = f'sensor_{random.randint(1, 10):03d}'

        if device_name is None:
            device_name = f'监测断面{random.randint(1, 100)}'

        # 水质类别
        quality_choices = ['Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', '劣Ⅴ']
        weights = [0.15, 0.30, 0.30, 0.15, 0.07, 0.03]  # Ⅲ类和Ⅱ类概率最高

        # 生成带有一定相关性的数据
        temp = cls.generate_temperature()
        # 温度较高时，溶解氧通常较低
        do_base = cls.DO_BASE - (temp - cls.TEMP_BASE) * 0.3
        do = cls.generate_dissolved_oxygen(do_base)

        return {
            'device_id': device_id,
            'device_name': device_name,
            'location': f'{province or "未知"} - {river_basin or "未知流域"}' if province or river_basin else f'{random.randint(1, 5)}号监测点',
            'province': province,
            'river_basin': river_basin,
            'water_quality': random.choices(quality_choices, weights=weights)[0],
            'temperature': temp,
            'ph': cls.generate_ph(),
            'dissolved_oxygen': do,
            'conductivity': random.uniform(200, 800),  # 电导率 μS/cm
            'turbidity': random.uniform(5, 100),  # 浊度 NTU
            'permanganate': cls.generate_permanganate_index(),
            'ammonia_nitrogen': cls.generate_ammonia_nitrogen(),
            'total_phosphorus': cls.generate_total_phosphorus(),
            'total_nitrogen': cls.generate_total_nitrogen(),
            'chlorophyll_a': cls.generate_chlorophyll_a(),
            'algae_density': cls.generate_algae_density(),
            'timestamp': datetime.now().isoformat()
        }

    @classmethod
    def generate_historical_data(cls, hours=24, device_id='sensor_001'):
        """
        生成历史数据

        Args:
            hours: 生成多少小时的数据
            device_id: 设备ID

        Returns:
            list: 历史数据列表
        """
        data = []
        now = datetime.now()

        # 初始基础值
        temp_base = cls.TEMP_BASE
        do_base = cls.DO_BASE
        ph_base = cls.PH_BASE

        for i in range(hours):
            # 时间从hours小时前到现在，每小时一个点
            timestamp = now - timedelta(hours=hours - i)

            # 模拟日温度变化（中午高，早晚低）
            hour = timestamp.hour
            temp_variation = 2 * (1 - (hour - 14) ** 2 / 100)  # 下午2点最高
            temp = cls.generate_temperature(temp_base + temp_variation)

            # 温度影响溶解氧
            do = cls.generate_dissolved_oxygen(do_base - (temp - cls.TEMP_BASE) * 0.3)

            data.append({
                'time': f'{hour:02d}:00',
                'timestamp': timestamp.isoformat(),
                'temperature': temp,
                'dissolved_oxygen': do,
                'ph': cls.generate_ph(ph_base)
            })

        return data

    @classmethod
    def generate_multi_sensors_realtime(cls, count=5):
        """
        生成多个传感器的实时数据

        Args:
            count: 传感器数量

        Returns:
            dict: 包含时间戳和传感器列表的字典
        """
        # 省份和流域列表
        provinces = ['北京市', '上海市', '广东省', '江苏省', '浙江省', '湖北省', '四川省']
        basins = ['长江流域', '黄河流域', '珠江流域', '淮河流域', '海河流域']

        sensors = []
        for i in range(1, count + 1):
            device_id = f'sensor_{i:03d}'
            device_name = f'监测断面{i}'
            province = random.choice(provinces)
            river_basin = random.choice(basins)
            sensors.append(cls.generate_sensor_data(device_id, device_name, province, river_basin))

        return {
            'timestamp': datetime.now().isoformat(),
            'sensors': sensors,
            'total': len(sensors)
        }

    @classmethod
    def generate_alert(cls, device_id=None):
        """
        生成告警数据

        Args:
            device_id: 设备ID

        Returns:
            dict: 告警数据
        """
        if device_id is None:
            device_id = f'sensor_{random.randint(1, 10):03d}'

        alert_types = [
            {
                'type': 'temperature',
                'level': 'critical',
                'message': '水温过高',
                'condition': lambda x: x > 32,
                'value_high': 33.5,
                'value_low': None
            },
            {
                'type': 'temperature',
                'level': 'warning',
                'message': '水温过低',
                'condition': lambda x: x < 18,
                'value_high': None,
                'value_low': 15.5
            },
            {
                'type': 'dissolved_oxygen',
                'level': 'critical',
                'message': '溶解氧严重不足',
                'condition': lambda x: x < 3,
                'value_high': None,
                'value_low': 2.5
            },
            {
                'type': 'dissolved_oxygen',
                'level': 'warning',
                'message': '溶解氧偏低',
                'condition': lambda x: x < 5,
                'value_high': None,
                'value_low': 4.8
            },
            {
                'type': 'ph',
                'level': 'warning',
                'message': 'pH值偏高',
                'condition': lambda x: x > 8.5,
                'value_high': 8.6,
                'value_low': None
            },
            {
                'type': 'ph',
                'level': 'warning',
                'message': 'pH值偏低',
                'condition': lambda x: x < 6.5,
                'value_high': None,
                'value_low': 6.2
            },
        ]

        alert_type = random.choice(alert_types)
        value = alert_type['value_high'] if alert_type['value_high'] else alert_type['value_low']

        return {
            'device_id': device_id,
            'alert_type': alert_type['type'],
            'alert_level': alert_type['level'],
            'message': f"{alert_type['message']}：{value} {cls._get_unit(alert_type['type'])}",
            'value': value,
            'created_at': datetime.now().isoformat(),
            'resolved': False
        }

    @staticmethod
    def _get_unit(alert_type):
        """获取单位"""
        units = {
            'temperature': '℃',
            'dissolved_oxygen': 'mg/L',
            'ph': '',
            'salinity': '‰'
        }
        return units.get(alert_type, '')

    @classmethod
    def generate_device_list(cls, count=10):
        """
        生成设备列表

        Args:
            count: 设备数量

        Returns:
            list: 设备列表
        """
        devices = []
        locations = ['1号池', '2号池', '3号池', '4号池', '5号池']

        # 传感器
        for i in range(1, count // 2 + 1):
            devices.append({
                'device_id': f'sensor_{i:03d}',
                'device_name': f'{random.choice(locations)}传感器',
                'device_type': 'sensor',
                'location': random.choice(locations),
                'status': random.choice(['online', 'online', 'online', 'offline'])
            })

        # 控制器
        for i in range(1, count // 2 + 1):
            devices.append({
                'device_id': f'controller_{i:03d}',
                'device_name': f'{random.choice(locations)}增氧机',
                'device_type': 'controller',
                'location': random.choice(locations),
                'status': random.choice(['online', 'online', 'offline'])
            })

        return devices


# 便捷函数
def generate_realtime_data():
    """生成实时数据"""
    return SensorDataGenerator.generate_multi_sensors_realtime()


def generate_historical_data(hours=24, device_id='sensor_001'):
    """生成历史数据"""
    return SensorDataGenerator.generate_historical_data(hours, device_id)


def generate_alerts(count=5):
    """生成告警列表"""
    alerts = []
    for _ in range(count):
        alerts.append(SensorDataGenerator.generate_alert())
    return alerts


def generate_devices():
    """生成设备列表"""
    return SensorDataGenerator.generate_device_list()
