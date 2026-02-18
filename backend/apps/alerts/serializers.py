"""
告警序列化器 - 重定向到sensors app
保留此文件以兼容现有代码，实际序列化器由sensors.serializers提供
"""
from apps.sensors.serializers import AlertSerializer as BaseAlertSerializer
from apps.sensors.models import Alert


class AlertSerializer(BaseAlertSerializer):
    """告警序列化器 - 继承自sensors.app"""

    class Meta(BaseAlertSerializer.Meta):
        model = Alert
