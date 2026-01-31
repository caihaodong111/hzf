"""
传感器数据视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from .models import Device, SensorData
from .serializers import DeviceSerializer, SensorDataSerializer, RealtimeDataSerializer, HistoricalDataSerializer
from core.data_generator import SensorDataGenerator


class DeviceViewSet(viewsets.ReadOnlyModelViewSet):
    """设备视图集"""
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    lookup_field = 'device_id'

    def get_queryset(self):
        queryset = super().get_queryset()
        device_type = self.request.query_params.get('device_type')
        status_param = self.request.query_params.get('status')

        if device_type:
            queryset = queryset.filter(device_type=device_type)
        if status_param:
            queryset = queryset.filter(status=status_param)

        return queryset

    def list(self, request, *args, **kwargs):
        """重写list方法以返回前端期望的格式"""
        queryset = self.get_queryset()

        # 如果数据库为空，使用模拟数据
        if queryset.count() == 0:
            devices = SensorDataGenerator.generate_device_list(count=10)
            return Response({
                'code': 200,
                'message': 'success',
                'data': {
                    'devices': devices
                }
            })

        # 序列化真实数据
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'devices': serializer.data
            }
        })


class SensorDataViewSet(viewsets.ReadOnlyModelViewSet):
    """传感器数据视图集"""
    queryset = SensorData.objects.select_related('device').all()
    serializer_class = SensorDataSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        device_id = self.request.query_params.get('device_id')

        if device_id:
            queryset = queryset.filter(device_id=device_id)

        # 默认返回最近24小时的数据
        hours = int(self.request.query_params.get('hours', 24))
        time_threshold = timezone.now() - timedelta(hours=hours)
        queryset = queryset.filter(recorded_at__gte=time_threshold)

        return queryset

    @action(detail=False, methods=['get'])
    def realtime(self, request):
        """获取实时数据（使用假数据生成器）"""
        # 使用假数据生成器生成实时数据
        data = SensorDataGenerator.generate_multi_sensors_realtime(count=5)

        return Response({
            'code': 200,
            'message': 'success',
            'data': data
        })

    @action(detail=False, methods=['get'])
    def history(self, request):
        """获取历史数据（使用假数据生成器）"""
        device_id = request.query_params.get('device_id', 'sensor_001')
        hours = int(request.query_params.get('hours', 24))

        # 使用假数据生成器生成历史数据
        data = SensorDataGenerator.generate_historical_data(hours=hours, device_id=device_id)

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'device_id': device_id,
                'date_range': (timezone.now() - timedelta(hours=hours)).strftime('%Y-%m-%d'),
                'interval': '1hour',
                'data': data
            }
        })
