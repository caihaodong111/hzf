"""
检查API返回的数据格式
"""
import os
import sys
import django
import json

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture.settings')
django.setup()

from core.national_water_data import NationalWaterDataService

service = NationalWaterDataService()

print("获取前10条数据检查格式...")
result = service.get_realtime(count=10, force_refresh=True)

sensors = result.get("sensors", [])
print(f"共获取 {len(sensors)} 条数据\n")

for i, sensor in enumerate(sensors[:5]):
    print(f"=== 数据 {i+1} ===")
    for key, value in sensor.items():
        print(f"  {key}: {value}")
    print()
