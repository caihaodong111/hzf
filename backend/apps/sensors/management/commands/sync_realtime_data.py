"""
同步实时数据到数据库表 sensor_data

用法:
    python manage.py sync_realtime_data
    python manage.py sync_realtime_data --source national
    python manage.py sync_realtime_data --source all
"""
from django.core.management.base import BaseCommand

from core.realtime_store import sync_realtime_data


class Command(BaseCommand):
    help = '同步实时数据到数据库表 sensor_data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            default='',
            dest='source',
            help='指定数据源 national/huawei/all，留空按设置优先级',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=1000,
            dest='count',
            help='拉取数量上限',
        )

    def handle(self, *args, **options):
        source = (options.get('source') or '').strip() or None
        count = options.get('count') or 1000
        result = sync_realtime_data(source=source, count=count)
        self.stdout.write(self.style.SUCCESS(
            f"完成同步: source={result['source']} created={result['created']} updated={result['updated']}"
        ))
