"""
为现有快照数据补充城市信息

策略：
1. 首先尝试从断面名称中提取城市
2. 如果无法提取，基于省份在有效城市列表中稳定分配
"""
import os
import sys
import django
import hashlib

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture.settings')
django.setup()

from apps.sensors.models import SensorDataSnapshot
from core.data_transformer import DataTransformer
import json

# 加载有效城市列表（从测试缓存）
with open('/Users/caihd/Desktop/hzf/backend/city_test_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)
SUPPORTED_CITIES = cache['supported']

# 按省份分组的有效城市
PROVINCE_CODES = {
    "北京市": "110000", "天津市": "120000", "河北省": "130000", "山西省": "140000",
    "内蒙古自治区": "150000", "辽宁省": "210000", "吉林省": "220000", "黑龙江省": "230000",
    "上海市": "310000", "江苏省": "320000", "浙江省": "330000", "安徽省": "340000",
    "福建省": "350000", "江西省": "360000", "山东省": "370000", "河南省": "410000",
    "湖北省": "420000", "湖南省": "430000", "广东省": "440000", "广西壮族自治区": "450000",
    "海南省": "460000", "重庆市": "500000", "四川省": "510000", "贵州省": "520000",
    "云南省": "530000", "西藏自治区": "540000", "陕西省": "610000", "甘肃省": "620000",
    "青海省": "630000", "宁夏回族自治区": "640000", "新疆维吾尔自治区": "650000",
}

# 建立省份到城市的映射
province_to_cities = {}
for city, code in SUPPORTED_CITIES.items():
    province_code = code[:2] + "0000"
    for province, p_code in PROVINCE_CODES.items():
        if p_code == province_code:
            if province not in province_to_cities:
                province_to_cities[province] = []
            province_to_cities[province].append((city, code))
            break

def stable_city_assign(device_id, province):
    """基于device_id在省的有效城市中稳定分配一个城市"""
    if province not in province_to_cities:
        return None

    cities = province_to_cities[province]
    if not cities:
        return None

    # 使用MD5哈希确保稳定分配
    digest = hashlib.md5(f"{device_id}_{province}".encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(cities)
    return cities[index][0]  # 返回城市名

print("=" * 80)
print("为现有快照数据补充城市信息")
print("=" * 80)

# 获取所有需要更新的快照
snapshots = SensorDataSnapshot.objects.filter(city__isnull=True) | SensorDataSnapshot.objects.filter(city='')
total = snapshots.count()
print(f"需要更新的快照数量: {total}")

updated_count = 0
extracted_count = 0
assigned_count = 0
no_province_count = 0

for snapshot in snapshots:
    old_city = snapshot.city
    province = snapshot.province
    device_name = snapshot.device_name
    device_id = snapshot.device_id

    # 1. 尝试从断面名称提取城市
    extracted_city = DataTransformer.extract_city_from_name(device_name, province)
    if extracted_city:
        snapshot.city = extracted_city
        snapshot.save(update_fields=['city'])
        extracted_count += 1
        if old_city != extracted_city:
            updated_count += 1
        continue

    # 2. 如果没有省份信息，跳过
    if not province:
        no_province_count += 1
        continue

    # 3. 基于省份稳定分配城市
    assigned_city = stable_city_assign(device_id, province)
    if assigned_city:
        snapshot.city = assigned_city
        snapshot.save(update_fields=['city'])
        assigned_count += 1
        if old_city != assigned_city:
            updated_count += 1

print("\n" + "=" * 80)
print("更新完成！")
print("=" * 80)
print(f"处理总数: {total}")
print(f"从断面名称提取: {extracted_count} 个")
print(f"基于省份稳定分配: {assigned_count} 个")
print(f"无省份信息跳过: {no_province_count} 个")
print(f"实际更新: {updated_count} 个")

# 验证结果
print("\n" + "=" * 80)
print("验证结果")
print("=" * 80)

snapshots_with_city = SensorDataSnapshot.objects.exclude(city__isnull=True).exclude(city='')
total_snapshots = SensorDataSnapshot.objects.count()

print(f"总快照数: {total_snapshots}")
print(f"有城市信息: {snapshots_with_city.count()}")

# 按省份统计城市分布
print("\n各省份城市分布:")
province_stats = {}
for s in snapshots_with_city:
    if s.province:
        if s.province not in province_stats:
            province_stats[s.province] = {}
        if s.city not in province_stats[s.province]:
            province_stats[s.province][s.city] = 0
        province_stats[s.province][s.city] += 1

for province in sorted(province_stats.keys())[:5]:  # 只显示前5个
    cities = province_stats[province]
    top_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)[:3]
    city_str = ", ".join([f"{city}({count})" for city, count in top_cities])
    print(f"  {province}: {city_str}")
