"""
告警视图 - 重定向到sensors app的AlertViewSet
保留此文件以兼容现有路由，实际功能由sensors.views.AlertViewSet提供
"""
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.sensors.models import Alert as AlertModel
from apps.sensors.serializers import AlertSerializer
from core.national_water_data import NationalWaterDataService
from core.data_transformer import DataTransformer


class AlertViewSet:
    """告警视图集 - 兼容层，重定向到sensors.app"""

    @staticmethod
    def list_fake(request):
        """获取告警数据 - 兼容旧API格式"""
        count = int(request.query_params.get('count', 10))
        alerts = []

        # 优先使用国家水质数据
        if NationalWaterDataService.enabled():
            raw_alerts = NationalWaterDataService.get_alerts(count=count)
            if raw_alerts:
                alerts = [DataTransformer.transform_alert(a, 'national') for a in raw_alerts]

        # 无可用数据源时返回空列表

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'total': len(alerts),
                'alerts': alerts
            }
        })
