"""
传感器数据序列化器
"""
from rest_framework import serializers
from .models import Device, SensorData


class DeviceSerializer(serializers.ModelSerializer):
    """设备序列化器"""

    class Meta:
        model = Device
        fields = ['id', 'device_id', 'device_name', 'device_type', 'location', 'status',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class SensorDataSerializer(serializers.ModelSerializer):
    """传感器数据序列化器"""
    device_id = serializers.CharField(source='device.device_id', read_only=True)

    class Meta:
        model = SensorData
        fields = ['id', 'device_id', 'temperature', 'salinity', 'dissolved_oxygen',
                  'ph', 'recorded_at']
        read_only_fields = ['recorded_at']


class RealtimeDataSerializer(serializers.Serializer):
    """实时数据序列化器"""
    device_id = serializers.CharField()
    location = serializers.CharField()
    temperature = serializers.FloatField()
    salinity = serializers.FloatField()
    dissolved_oxygen = serializers.FloatField()
    ph = serializers.FloatField()
    timestamp = serializers.CharField()


class HistoricalDataSerializer(serializers.Serializer):
    """历史数据序列化器"""
    time = serializers.CharField()
    timestamp = serializers.CharField()
    temperature = serializers.FloatField()
    salinity = serializers.FloatField()
    dissolved_oxygen = serializers.FloatField()
    ph = serializers.FloatField()
