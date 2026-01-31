"""
设备管理视图
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.data_generator import SensorDataGenerator


class DeviceViewSet(viewsets.ViewSet):
    """设备视图集（使用假数据）"""

    def list(self, request):
        """获取设备列表"""
        devices = SensorDataGenerator.generate_device_list()

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'devices': devices
            }
        })

    def retrieve(self, request, pk=None):
        """获取设备详情"""
        # 简化实现
        return Response({'code': 404, 'message': 'Not implemented'})
