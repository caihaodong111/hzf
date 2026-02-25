"""
数据看板相关模型
"""
from django.db import models


class DataSourcePreference(models.Model):
    MODE_AUTO = 'auto'
    MODE_MANUAL = 'manual'
    MODE_CHOICES = [
        (MODE_AUTO, '自动'),
        (MODE_MANUAL, '手动'),
    ]

    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default=MODE_AUTO,
        verbose_name='数据源模式',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '数据源偏好'
        verbose_name_plural = '数据源偏好'

    def __str__(self) -> str:
        return f"{self.get_mode_display()} ({self.mode})"
