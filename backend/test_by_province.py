"""
使用省级代码获取数据，分析有数据的城市
"""
import os
import sys
import django
from collections import defaultdict

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture.settings')
django.setup()

from core.national_water_data import NationalWaterDataService, CITY_CODES

# 省份列表及其代码
PROVINCES = [
    ("北京市", "110000"),
    ("天津市", "120000"),
    ("河北省", "130000"),
    ("山西省", "140000"),
    ("内蒙古自治区", "150000"),
    ("辽宁省", "210000"),
    ("吉林省", "220000"),
    ("黑龙江省", "230000"),
    ("上海市", "310000"),
    ("江苏省", "320000"),
    ("浙江省", "330000"),
    ("安徽省", "340000"),
    ("福建省", "350000"),
    ("江西省", "360000"),
    ("山东省", "370000"),
    ("河南省", "410000"),
    ("湖北省", "420000"),
    ("湖南省", "430000"),
    ("广东省", "440000"),
    ("广西壮族自治区", "450000"),
    ("海南省", "460000"),
    ("重庆市", "500000"),
    ("四川省", "510000"),
    ("贵州省", "520000"),
    ("云南省", "530000"),
    ("西藏自治区", "540000"),
    ("陕西省", "610000"),
    ("甘肃省", "620000"),
    ("青海省", "630000"),
    ("宁夏回族自治区", "640000"),
    ("新疆维吾尔自治区", "650000"),
]

service = NationalWaterDataService()

print("=" * 80)
print("使用省级代码获取数据，分析有数据的城市")
print("=" * 80)

# 存储有数据的省和城市
province_data = {}

for province_name, province_code in PROVINCES:
    print(f"\n测试 {province_name} (代码: {province_code})...")
    print("-" * 60)

    result = service.get_realtime(count=1000, area_id=province_code, force_refresh=False)
    sensors = result.get("sensors", [])
    total = result.get("total", 0)

    print(f"  获取到 {len(sensors)} 条数据，总计 {total} 条")

    if sensors:
        # 显示样本
        print(f"  样本断面:")
        for sensor in sensors[:5]:
            device_name = sensor.get('device_name', 'N/A')
            location = sensor.get('location', 'N/A')
            print(f"    - {device_name} ({location})")

        province_data[province_name] = {
            'code': province_code,
            'count': total,
            'has_data': True
        }
    else:
        print(f"  ❌ 无数据")
        province_data[province_name] = {
            'code': province_code,
            'count': 0,
            'has_data': False
        }

# 生成结果
print("\n" + "=" * 80)
print("结果汇总")
print("=" * 80)

has_data_provinces = {k: v for k, v in province_data.items() if v['has_data']}
no_data_provinces = {k: v for k, v in province_data.items() if not v['has_data']}

print(f"\n✅ 有数据的省份 ({len(has_data_provinces)}个):")
for province, info in sorted(has_data_provinces.items()):
    print(f"  - {province} ({info['count']}条)")

print(f"\n❌ 无数据的省份 ({len(no_data_provinces)}个):")
for province, info in sorted(no_data_provinces.items()):
    print(f"  - {province}")

# 对于有数据的省份，需要进一步测试哪些城市有数据
print("\n" + "=" * 80)
print("建议：对有数据的省份，需要逐个测试城市代码")
print("=" * 80)

print("\n有数据的省份需要测试的城市:")
for province in sorted(has_data_provinces.keys()):
    # 找出该省在CITY_CODES中的城市
    province_code = province_data[province]['code'][:2]
    cities_in_province = []
    for city, city_code in CITY_CODES.items():
        if city_code.startswith(province_code):
            cities_in_province.append((city, city_code))

    if cities_in_province:
        print(f"\n{province} ({len(cities_in_province)}个城市):")
        for city, code in sorted(cities_in_province):
            print(f"  - {city}: {code}")
