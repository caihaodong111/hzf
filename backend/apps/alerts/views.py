"""
告警视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Alert
from .serializers import AlertSerializer
from core.data_generator import SensorDataGenerator


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    """告警视图集"""
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        resolved = self.request.query_params.get('resolved')

        if resolved == 'false':
            queryset = queryset.filter(resolved=False)
        elif resolved == 'true':
            queryset = queryset.filter(resolved=True)

        return queryset

    @action(detail=False, methods=['get'])
    def list_fake(self, request):
        """获取假告警数据（用于展示）"""
        count = int(request.query_params.get('count', 5))
        alerts = []

        for _ in range(count):
            alerts.append(SensorDataGenerator.generate_alert())

        return Response({
            'code': 200,
            'message': 'success',
            'data': {
                'total': len(alerts),
                'alerts': alerts
            }
        })
