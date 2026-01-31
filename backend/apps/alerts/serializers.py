"""
告警序列化器
"""
from rest_framework import serializers
from .models import Alert


class AlertSerializer(serializers.ModelSerializer):
    """告警序列化器"""

    class Meta:
        model = Alert
        fields = ['id', 'device_id', 'alert_type', 'alert_level', 'message',
                  'value', 'resolved', 'resolved_at', 'created_at']
        read_only_fields = ['created_at']
