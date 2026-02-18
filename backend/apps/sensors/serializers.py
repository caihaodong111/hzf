"""
传感器数据序列化器 - 统一数据序列化
支持国家水质自动综合监管平台、开放数据和模拟数据
"""
from rest_framework import serializers
from .models import Device, SensorData, Alert


class DeviceSerializer(serializers.ModelSerializer):
    """设备序列化器 - 完整字段"""
    is_online = serializers.BooleanField(read_only=True)

    class Meta:
        model = Device
        fields = ['id', 'device_id', 'device_name', 'device_type', 'location',
                  'province', 'province_code', 'river_basin', 'river_basin_code',
                  'status', 'last_data_time', 'is_online',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'is_online']


class SensorDataSerializer(serializers.ModelSerializer):
    """传感器数据序列化器 - 数据库模型序列化"""
    device_id = serializers.CharField(source='device.device_id', read_only=True)
    device_name = serializers.CharField(source='device.device_name', read_only=True)

    class Meta:
        model = SensorData
        fields = ['id', 'device_id', 'device_name', 'temperature', 'ph',
                  'dissolved_oxygen', 'conductivity', 'turbidity', 'salinity',
                  'water_quality', 'permanganate', 'ammonia_nitrogen',
                  'total_phosphorus', 'total_nitrogen', 'chlorophyll_a',
                  'algae_density', 'data_source',
                  'recorded_at', 'created_at']
        read_only_fields = ['created_at']


class RealtimeDataSerializer(serializers.Serializer):
    """实时数据序列化器 - 统一多数据源输出格式"""
    device_id = serializers.CharField()
    device_name = serializers.CharField(required=False, allow_null=True)
    location = serializers.CharField(required=False, allow_null=True)
    province = serializers.CharField(required=False, allow_null=True)
    river_basin = serializers.CharField(required=False, allow_null=True)
    water_quality = serializers.CharField(required=False, allow_null=True)

    # 水质参数
    temperature = serializers.FloatField(allow_null=True, required=False)
    ph = serializers.FloatField(allow_null=True, required=False)
    dissolved_oxygen = serializers.FloatField(allow_null=True, required=False)
    conductivity = serializers.FloatField(allow_null=True, required=False)
    turbidity = serializers.FloatField(allow_null=True, required=False)
    salinity = serializers.FloatField(allow_null=True, required=False)

    # 扩展参数
    permanganate = serializers.FloatField(allow_null=True, required=False)
    permanganate_index = serializers.FloatField(allow_null=True, required=False)
    ammonia_nitrogen = serializers.FloatField(allow_null=True, required=False)
    total_phosphorus = serializers.FloatField(allow_null=True, required=False)
    total_nitrogen = serializers.FloatField(allow_null=True, required=False)
    chlorophyll_a = serializers.FloatField(allow_null=True, required=False)
    algae_density = serializers.FloatField(allow_null=True, required=False)

    # 时间戳
    timestamp = serializers.CharField()

    # 数据来源
    data_source = serializers.CharField(required=False, allow_null=True)


class HistoricalDataSerializer(serializers.Serializer):
    """历史数据序列化器"""
    time = serializers.CharField()
    timestamp = serializers.CharField()
    temperature = serializers.FloatField(allow_null=True, required=False)
    ph = serializers.FloatField(allow_null=True, required=False)
    dissolved_oxygen = serializers.FloatField(allow_null=True, required=False)
    conductivity = serializers.FloatField(allow_null=True, required=False)
    turbidity = serializers.FloatField(allow_null=True, required=False)
    salinity = serializers.FloatField(allow_null=True, required=False)


class AlertSerializer(serializers.ModelSerializer):
    """告警序列化器 - 统一字段命名"""
    device_id = serializers.CharField(source='device.device_id', read_only=True)
    device_name = serializers.CharField(source='device.device_name', read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    alert_level_display = serializers.CharField(source='get_alert_level_display', read_only=True)

    class Meta:
        model = Alert
        fields = ['id', 'device_id', 'device_name', 'alert_type', 'alert_type_display',
                  'alert_level', 'alert_level_display', 'message', 'value', 'value_unit',
                  'resolved', 'resolved_at', 'created_at', 'updated_at', 'data_source']
        read_only_fields = ['created_at', 'updated_at']


class AlertCreateSerializer(serializers.ModelSerializer):
    """告警创建序列化器 - 支持从不同数据源转换"""
    device_id = serializers.CharField(write_only=True)

    class Meta:
        model = Alert
        fields = ['device_id', 'alert_type', 'alert_level', 'message',
                  'value', 'value_unit', 'data_source']

    def create(self, validated_data):
        """创建告警时自动关联设备"""
        from .models import Device
        device_id = validated_data.pop('device_id')
        try:
            device = Device.objects.get(device_id=device_id)
        except Device.DoesNotExist:
            # 如果设备不存在，自动创建
            device = Device.objects.create(
                device_id=device_id,
                device_name=device_id,
                device_type='sensor',
                status='online'
            )
        validated_data['device'] = device
        return Alert.objects.create(**validated_data)


class AlertInputSerializer(serializers.Serializer):
    """告警输入序列化器 - 用于接收外部数据源的数据并转换"""
    # 外部数据源可能使用的字段名
    device_id = serializers.CharField()
    device_name = serializers.CharField(required=False, allow_null=True)
    type = serializers.CharField(required=False, allow_null=True)  # 映射到 alert_type
    level = serializers.CharField(required=False, allow_null=True)  # 映射到 alert_level
    timestamp = serializers.CharField(required=False, allow_null=True)  # 映射到 created_at
    message = serializers.CharField(required=False, allow_null=True)
    value = serializers.FloatField(required=False, allow_null=True)
    resolved = serializers.BooleanField(required=False, default=False)

    def to_internal_value(self, data):
        """转换外部数据格式到内部格式"""
        ret = super().to_internal_value(data)

        # 字段映射
        if 'type' in ret and ret['type']:
            ret['alert_type'] = ret.pop('type')
        if 'level' in ret and ret['level']:
            ret['alert_level'] = ret.pop('level')
        if 'timestamp' in ret and ret['timestamp']:
            ret['created_at'] = ret.pop('timestamp')

        # 确保有必需的字段
        if 'alert_type' not in ret:
            ret['alert_type'] = 'other'
        if 'alert_level' not in ret:
            ret['alert_level'] = 'warning'
        if 'message' not in ret or not ret['message']:
            ret['message'] = '数据异常告警'

        return ret


class DashboardSummarySerializer(serializers.Serializer):
    """看板摘要序列化器"""
    total_devices = serializers.IntegerField()
    online_devices = serializers.IntegerField()
    offline_devices = serializers.IntegerField()
    alert_count = serializers.IntegerField()
    avg_temperature = serializers.FloatField(allow_null=True)
    avg_dissolved_oxygen = serializers.FloatField(allow_null=True)
    water_quality_distribution = serializers.DictField(required=False)
