"""
传感器数据模型 - 统一数据模型
支持国家水质自动综合监管平台和开放数据
"""
from django.db import models


class SensorData(models.Model):
    """传感器数据模型 - 统一多数据源的水质监测数据"""
    station_id = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name='站点ID',
        blank=True,
        null=True,
    )
    station_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='站点名称/断面名称',
    )
    location = models.CharField(max_length=200, blank=True, null=True, verbose_name='位置')
    province = models.CharField(max_length=50, blank=True, null=True, verbose_name='省份')
    city = models.CharField(max_length=50, blank=True, null=True, verbose_name='城市')
    river_basin = models.CharField(max_length=50, blank=True, null=True, verbose_name='流域')

    # 地理坐标（用于地图显示）
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True,
                                     verbose_name='经度', help_text='东经为正，西经为负')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True,
                                    verbose_name='纬度', help_text='北纬为正，南纬为负')

    # 基础水质参数
    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                      verbose_name='水温(℃)')
    ph = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, verbose_name='pH值')

    # 溶解氧
    dissolved_oxygen = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                          verbose_name='溶解氧(mg/L)')

    # 电导率 (μS/cm) - 国家水质数据使用
    conductivity = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                      verbose_name='电导率(μS/cm)')

    # 浊度 (NTU) - 国家水质数据使用
    turbidity = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                   verbose_name='浊度(NTU)')

    # 盐度 (‰) - 开放数据使用
    # 注意：电导率和盐度是不同的物理量，不能混用
    salinity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                  verbose_name='盐度(‰)')

    # 综合水质评价
    water_quality = models.CharField(max_length=10, blank=True, null=True,
                                    verbose_name='水质类别',
                                    help_text='Ⅰ类、Ⅱ类、Ⅲ类、Ⅳ类、Ⅴ类、劣Ⅴ类')

    # 扩展水质参数 (国家水质数据)
    permanganate = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True,
                                      verbose_name='高锰酸盐指数(mg/L)')
    ammonia_nitrogen = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True,
                                         verbose_name='氨氮(mg/L)')
    total_phosphorus = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True,
                                         verbose_name='总磷(mg/L)')
    total_nitrogen = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True,
                                       verbose_name='总氮(mg/L)')
    chlorophyll_a = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True,
                                      verbose_name='叶绿素a(mg/L)')
    algae_density = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                      verbose_name='藻密度(cells/L)')

    # 数据来源标识
    data_source = models.CharField(max_length=50, blank=True, null=True,
                                  verbose_name='数据来源',
                                  help_text='national/open/database')

    # 时间戳
    recorded_at = models.DateTimeField(db_index=True, verbose_name='监测时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='入库时间')

    class Meta:
        db_table = 'sensor_data'
        verbose_name = '传感器数据'
        verbose_name_plural = '传感器数据'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['station_id', '-recorded_at'], name='sensor_data_station_time_idx'),
            models.Index(fields=['recorded_at']),
            models.Index(fields=['data_source']),
            models.Index(fields=['water_quality']),
            models.Index(fields=['province'], name='sensor_data_province_idx'),
            models.Index(fields=['city'], name='sensor_data_city_idx'),
            models.Index(fields=['river_basin'], name='sensor_data_river_idx'),
        ]

    def __str__(self):
        return f"{self.station_id} - {self.recorded_at}"

    def get_water_quality_level(self):
        """获取水质等级数值"""
        quality_map = {
            'Ⅰ': 1, 'Ⅱ': 2, 'Ⅲ': 3, 'Ⅳ': 4, 'Ⅴ': 5, '劣Ⅴ': 6
        }
        return quality_map.get(self.water_quality, 0)

    def is_excellent(self):
        """是否优良水质(Ⅰ-Ⅱ类)"""
        return self.water_quality in ['Ⅰ', 'Ⅱ']

    def is_polluted(self):
        """是否污染水质(Ⅳ-劣Ⅴ类)"""
        return self.water_quality in ['Ⅳ', 'Ⅴ', '劣Ⅴ']


class SensorSnapshot(models.Model):
    """最新快照表 - 每个站点保留一条最新记录"""
    station_id = models.CharField(max_length=50, db_index=True, verbose_name='站点ID', blank=True, null=True)
    station_name = models.CharField(max_length=100, blank=True, null=True, verbose_name='站点名称/断面名称')
    location = models.CharField(max_length=200, blank=True, null=True, verbose_name='位置')
    province = models.CharField(max_length=50, blank=True, null=True, verbose_name='省份')
    city = models.CharField(max_length=50, blank=True, null=True, verbose_name='城市')
    river_basin = models.CharField(max_length=50, blank=True, null=True, verbose_name='流域')

    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True,
                                     verbose_name='经度', help_text='东经为正，西经为负')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True,
                                    verbose_name='纬度', help_text='北纬为正，南纬为负')

    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                      verbose_name='水温(℃)')
    ph = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, verbose_name='pH值')
    dissolved_oxygen = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                           verbose_name='溶解氧(mg/L)')
    conductivity = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                        verbose_name='电导率(μS/cm)')
    turbidity = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                     verbose_name='浊度(NTU)')
    salinity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                    verbose_name='盐度(‰)')
    water_quality = models.CharField(max_length=10, blank=True, null=True,
                                     verbose_name='水质类别')
    permanganate = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True,
                                        verbose_name='高锰酸盐指数(mg/L)')
    ammonia_nitrogen = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True,
                                           verbose_name='氨氮(mg/L)')
    total_phosphorus = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True,
                                           verbose_name='总磷(mg/L)')
    total_nitrogen = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True,
                                         verbose_name='总氮(mg/L)')
    chlorophyll_a = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True,
                                        verbose_name='叶绿素a(mg/L)')
    algae_density = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        verbose_name='藻密度(cells/L)')

    data_source = models.CharField(max_length=50, blank=True, null=True,
                                   verbose_name='数据来源',
                                   help_text='national/open/manual')

    recorded_at = models.DateTimeField(db_index=True, verbose_name='监测时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='快照更新时间')

    class Meta:
        db_table = 'sensor_data_latest'
        verbose_name = '传感器最新快照'
        verbose_name_plural = '传感器最新快照'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['station_id'], name='snapshot_station_idx'),
            models.Index(fields=['recorded_at'], name='snapshot_time_idx'),
            models.Index(fields=['province'], name='snapshot_province_idx'),
            models.Index(fields=['city'], name='snapshot_city_idx'),
            models.Index(fields=['river_basin'], name='snapshot_river_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['station_id'],
                name='snapshot_station_uniq',
            )
        ]

    def __str__(self):
        return f"{self.station_id} - {self.recorded_at}"


class Alert(models.Model):
    """告警模型 - 统一告警数据结构"""
    ALERT_LEVEL_CHOICES = [
        ('info', '信息'),
        ('warning', '警告'),
        ('critical', '严重'),
    ]

    ALERT_TYPE_CHOICES = [
        ('temperature', '水温异常'),
        ('dissolved_oxygen', '溶解氧异常'),
        ('ph', 'pH异常'),
        ('water_quality', '水质异常'),
        ('conductivity', '电导率异常'),
        ('turbidity', '浊度异常'),
        ('device_offline', '设备离线'),
        ('other', '其他'),
    ]

    # 设备标识
    station_id = models.CharField(max_length=50, db_index=True, verbose_name='站点ID')
    station_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='站点名称/断面名称',
    )

    # 告警内容 (统一字段命名)
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPE_CHOICES, verbose_name='告警类型')
    alert_level = models.CharField(max_length=20, choices=ALERT_LEVEL_CHOICES, verbose_name='告警级别')
    message = models.TextField(verbose_name='告警消息')

    # 告警值
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                               verbose_name='告警值')
    value_unit = models.CharField(max_length=20, blank=True, null=True, verbose_name='值单位')

    # 状态
    resolved = models.BooleanField(default=False, verbose_name='已解决')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')

    # 时间戳 (统一字段命名)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='告警时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    # 数据来源
    data_source = models.CharField(max_length=50, blank=True, null=True, verbose_name='数据来源')

    class Meta:
        db_table = 'alerts'
        verbose_name = '告警'
        verbose_name_plural = '告警'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['station_id', '-created_at'], name='alerts_station_time_idx'),
            models.Index(fields=['alert_type']),
            models.Index(fields=['alert_level']),
            models.Index(fields=['resolved']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"[{self.alert_level}] {self.station_id} - {self.message}"

    def resolve(self):
        """标记告警为已解决"""
        from django.utils import timezone
        self.resolved = True
        self.resolved_at = timezone.now()
        self.save()
