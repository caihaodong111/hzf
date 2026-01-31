"""
告警模型
"""
from django.db import models


class Alert(models.Model):
    """告警模型"""
    ALERT_LEVEL_CHOICES = [
        ('info', '信息'),
        ('warning', '警告'),
        ('critical', '严重'),
    ]

    device_id = models.CharField(max_length=50, verbose_name='设备ID')
    alert_type = models.CharField(max_length=50, verbose_name='告警类型')
    alert_level = models.CharField(max_length=20, choices=ALERT_LEVEL_CHOICES, verbose_name='告警级别')
    message = models.TextField(verbose_name='告警消息')
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='触发值')
    resolved = models.BooleanField(default=False, verbose_name='是否已解决')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='创建时间')

    class Meta:
        db_table = 'alerts'
        verbose_name = '告警记录'
        verbose_name_plural = '告警记录'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.device_id} - {self.message[:20]}"
