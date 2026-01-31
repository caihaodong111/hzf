"""
传感器数据模型
"""
from django.db import models


class Device(models.Model):
    """设备模型"""
    DEVICE_TYPE_CHOICES = [
        ('sensor', '传感器'),
        ('controller', '控制器'),
    ]

    STATUS_CHOICES = [
        ('online', '在线'),
        ('offline', '离线'),
        ('error', '故障'),
    ]

    device_id = models.CharField(max_length=50, unique=True, verbose_name='设备ID')
    device_name = models.CharField(max_length=100, verbose_name='设备名称')
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPE_CHOICES, verbose_name='设备类型')
    location = models.CharField(max_length=200, blank=True, null=True, verbose_name='设备位置')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='online', verbose_name='设备状态')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'devices'
        verbose_name = '设备'
        verbose_name_plural = '设备'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.device_name} ({self.device_id})"


class SensorData(models.Model):
    """传感器数据模型"""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, to_field='device_id',
                              db_column='device_id', verbose_name='设备')
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                      verbose_name='水温(℃)')
    salinity = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                   verbose_name='盐度(‰)')
    dissolved_oxygen = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                          verbose_name='溶解氧(mg/L)')
    ph = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, verbose_name='pH值')
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='记录时间')

    class Meta:
        db_table = 'sensor_data'
        verbose_name = '传感器数据'
        verbose_name_plural = '传感器数据'
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.device_id} - {self.recorded_at}"
