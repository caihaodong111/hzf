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
        parser.add_argument(
            '--with-city',
            action='store_true',
            dest='with_city',
            help='国家水质按城市抓取（写入 city 字段）',
        )
        parser.add_argument(
            '--force-refresh',
            action='store_true',
            dest='force_refresh',
            help='忽略缓存，强制刷新拉取',
        )
        parser.add_argument(
            '--max-cities',
            type=int,
            default=0,
            dest='max_cities',
            help='最多抓取城市数（0=不限制）',
        )
        parser.add_argument(
            '--sleep-ms',
            type=int,
            default=None,
            dest='sleep_ms',
            help='每次城市请求间隔(ms)，不传则使用默认配置',
        )
        parser.add_argument(
            '--timeout-s',
            type=int,
            default=None,
            dest='timeout_s',
            help='城市请求超时(s)，不传则使用默认配置',
        )
        parser.add_argument(
            '--workers',
            type=int,
            default=None,
            dest='workers',
            help='按城市抓取并发数，不传则使用默认配置',
        )

    def handle(self, *args, **options):
        source = (options.get('source') or '').strip() or None
        count = options.get('count') or 1000
        with_city = bool(options.get("with_city"))
        force_refresh = bool(options.get("force_refresh"))
        result = sync_realtime_data(
            source=source,
            count=count,
            with_city=with_city,
            force_refresh=force_refresh,
            max_cities=int(options.get("max_cities") or 0),
            sleep_ms=options.get("sleep_ms"),
            timeout_s=options.get("timeout_s"),
            workers=options.get("workers"),
        )
        self.stdout.write(self.style.SUCCESS(
            f"完成同步: source={result['source']} created={result['created']} updated={result['updated']}"
        ))
