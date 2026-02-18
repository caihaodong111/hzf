"""
定期抓取传感器数据快照的管理命令

用法:
    python manage.py snapshot_sensor_data          # 手动执行一次快照
    python manage.py snapshot_sensor_data --force  # 强制执行快照

可以配合 crontab 或 celery beat 定时执行:
    # 每小时执行一次
    0 * * * * cd /path/to/project && python manage.py snapshot_sensor_data
"""
import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.national_water_data import NationalWaterDataService
from core.open_data_provider import OpenWaterDataService
from core.data_generator import SensorDataGenerator
from core.data_transformer import DataTransformer
from core.city_resolver import infer_city_name

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '抓取所有传感器数据的快照并存储到数据库'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            help='强制执行快照，忽略时间间隔限制',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            dest='interval',
            help='快照时间间隔（分钟），默认60分钟',
        )

    def handle(self, *args, **options):
        """执行快照任务"""
        from apps.sensors.models import SensorDataSnapshot

        force = options.get('force', False)
        interval = options.get('interval', 60)

        self.stdout.write(f'[{timezone.now()}] 开始执行数据快照任务...')

        # 检查是否需要执行快照（避免频繁执行）
        if not force:
            last_snapshot = SensorDataSnapshot.objects.order_by('-snapshot_time').first()
            if last_snapshot:
                time_since_last = (timezone.now() - last_snapshot.snapshot_time).total_seconds()
                if time_since_last < interval * 60:
                    self.stdout.write(
                        self.style.WARNING(
                            f'距离上次快照仅 {int(time_since_last/60)} 分钟，'
                            f'未达到配置的间隔时间 ({interval} 分钟)，跳过本次执行。'
                        )
                    )
                    return

        # 获取实时数据
        sensors_data = []
        source = None

        # 优先使用国家水质数据
        if NationalWaterDataService.enabled():
            result = NationalWaterDataService.get_realtime(count=1000, force_refresh=True)
            sensors_data = result.get('sensors', [])
            if sensors_data:
                source = 'national'
                self.stdout.write(f'从国家水质数据获取到 {len(sensors_data)} 条记录')

        # 其次使用外部数据源
        if not sensors_data and OpenWaterDataService.enabled():
            result = OpenWaterDataService.get_realtime(count=1000)
            sensors_data = result.get('sensors', [])
            if sensors_data:
                source = 'open'
                self.stdout.write(f'从开放数据源获取到 {len(sensors_data)} 条记录')

        # 最后使用模拟数据
        if not sensors_data:
            result = SensorDataGenerator.generate_multi_sensors_realtime(count=100)
            sensors_data = result.get('sensors', [])
            source = 'simulator'
            self.stdout.write(f'使用模拟数据生成 {len(sensors_data)} 条记录')

        if not sensors_data:
            self.stdout.write(self.style.ERROR('没有获取到任何数据'))
            return

        # 当前快照时间（使用整点时间，方便查询）
        now = timezone.now()
        snapshot_time = now.replace(minute=0, second=0, microsecond=0)

        # 批量创建快照记录
        snapshots_created = 0
        snapshots_updated = 0
        errors = []

        for sensor in sensors_data:
            try:
                # 转换数据格式
                transformed = DataTransformer.transform_realtime_data(sensor, source)

                # 准备快照数据
                city_name = infer_city_name(
                    (transformed.get('device_name'), transformed.get('location')),
                    transformed.get('province') or '',
                    transformed.get('device_id') or ''
                )
                snapshot_data = {
                    'device_id': transformed.get('device_id'),
                    'device_name': transformed.get('device_name'),
                    'location': transformed.get('location'),
                    'province': transformed.get('province'),
                    'city': city_name,
                    'river_basin': transformed.get('river_basin'),
                    'temperature': self._to_decimal(transformed.get('temperature')),
                    'ph': self._to_decimal(transformed.get('ph')),
                    'dissolved_oxygen': self._to_decimal(transformed.get('dissolved_oxygen')),
                    'conductivity': self._to_decimal(transformed.get('conductivity')),
                    'turbidity': self._to_decimal(transformed.get('turbidity')),
                    'salinity': self._to_decimal(transformed.get('salinity')),
                    'water_quality': transformed.get('water_quality'),
                    'permanganate': self._to_decimal(transformed.get('permanganate')),
                    'ammonia_nitrogen': self._to_decimal(transformed.get('ammonia_nitrogen')),
                    'total_phosphorus': self._to_decimal(transformed.get('total_phosphorus')),
                    'total_nitrogen': self._to_decimal(transformed.get('total_nitrogen')),
                    'chlorophyll_a': self._to_decimal(transformed.get('chlorophyll_a')),
                    'algae_density': self._to_decimal(transformed.get('algae_density')),
                    'data_source': source,
                    'snapshot_time': snapshot_time,
                }

                # 使用 update_or_create 避免重复
                snapshot, created = SensorDataSnapshot.objects.update_or_create(
                    device_id=snapshot_data['device_id'],
                    snapshot_time=snapshot_time,
                    defaults=snapshot_data
                )

                if created:
                    snapshots_created += 1
                else:
                    snapshots_updated += 1

            except Exception as e:
                device_id = sensor.get('device_id', 'unknown')
                errors.append(f'{device_id}: {str(e)}')
                logger.error(f'保存快照失败 [{device_id}]: {e}')

        # 清理旧数据（保留最近30天的数据）
        deleted_count = SensorDataSnapshot.objects.filter(
            snapshot_time__lt=now - timezone.timedelta(days=30)
        ).delete()[0]

        # 输出结果
        self.stdout.write(self.style.SUCCESS(f'快照完成！'))
        self.stdout.write(f'  创建: {snapshots_created} 条')
        self.stdout.write(f'  更新: {snapshots_updated} 条')
        self.stdout.write(f'  清理: {deleted_count} 条旧数据')
        self.stdout.write(f'  快照时间: {snapshot_time.strftime("%Y-%m-%d %H:%M:%S")}')

        if errors:
            self.stdout.write(self.style.ERROR(f'错误: {len(errors)} 条'))
            for error in errors[:5]:  # 只显示前5个错误
                self.stdout.write(f'  - {error}')

    def _to_decimal(self, value):
        """转换为 Decimal 类型"""
        if value is None:
            return None
        try:
            from decimal import Decimal
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None
