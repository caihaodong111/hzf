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


class AiInsightLog(models.Model):
    """AI 问答记录（用于审计、回溯与优化提示词/模型表现）。"""

    question = models.TextField(verbose_name='问题')
    answer = models.TextField(blank=True, null=True, verbose_name='回答')
    model = models.CharField(max_length=100, blank=True, null=True, verbose_name='模型')

    success = models.BooleanField(default=False, verbose_name='是否成功')
    error_message = models.TextField(blank=True, null=True, verbose_name='错误信息')

    request_payload = models.JSONField(blank=True, null=True, verbose_name='请求上下文')
    response_meta = models.JSONField(blank=True, null=True, verbose_name='响应元信息')

    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name='IP地址')
    user_agent = models.TextField(blank=True, null=True, verbose_name='User-Agent')
    duration_ms = models.IntegerField(blank=True, null=True, verbose_name='耗时(ms)')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'ai_insight_logs'
        verbose_name = 'AI问答记录'
        verbose_name_plural = 'AI问答记录'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='ai_log_created_idx'),
            models.Index(fields=['success', '-created_at'], name='ai_log_success_idx'),
            models.Index(fields=['model', '-created_at'], name='ai_log_model_idx'),
        ]

    def __str__(self) -> str:
        model = self.model or '-'
        status = 'ok' if self.success else 'fail'
        return f"[{status}] {model} {self.created_at:%Y-%m-%d %H:%M:%S}"
