"""
通过获取全国数据提取实际有数据的城市
使用DataTransformer的逻辑从device_name提取城市
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
from core.data_transformer import DataTransformer

print("=" * 80)
print("获取全国数据并提取有数据的城市")
print("=" * 80)

service = NationalWaterDataService()

# 获取全国数据，多次获取以覆盖更多数据
print("正在获取全国数据...")
all_sensors = []

# 分批获取，每次100条
for page in range(1, 20):  # 最多20页
    result = service.get_realtime(count=100, force_refresh=(page==1))
    sensors = result.get("sensors", [])
    if not sensors:
        break
    all_sensors.extend(sensors)
    print(f"  第{page}批: 获取到 {len(sensors)} 条数据")
    if len(sensors) < 100:  # 数据不足100条说明已经获取完
        break

print(f"\n共获取到 {len(all_sensors)} 条监测数据\n")

# 提取城市信息
province_cities = defaultdict(set)
province_city_count = defaultdict(lambda: defaultdict(int))

for sensor in all_sensors:
    province = sensor.get('province')
    device_name = sensor.get('device_name', '')

    if not province:
        continue

    # 使用DataTransformer的逻辑提取城市
    city = DataTransformer.extract_city_from_name(device_name, province)

    if city:
        province_cities[province].add(city)
        province_city_count[province][city] += 1

# 输出结果
print("=" * 80)
print("按省份统计有数据的城市")
print("=" * 80)

# 省份代码映射
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

# 按省份分组输出
province_order = [
    "北京市", "天津市", "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省",
    "上海市", "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省",
    "重庆市", "四川省", "贵州省", "云南省", "西藏自治区",
    "陕西省", "甘肃省", "青海省", "宁夏回族自治区", "新疆维吾尔自治区"
]

for province in province_order:
    if province in province_cities:
        cities = sorted(province_cities[province])
        print(f"\n{province} ({len(cities)}个城市):")
        for city in cities:
            count = province_city_count[province][city]
            code = CITY_CODES.get(city, "未知")
            print(f"  - {city}: {count}条 (代码: {code})")

# 生成更新后的CITY_CODES
print("\n" + "=" * 80)
print("生成更新后的CITY_CODES")
print("=" * 80)

# 按省份分组
province_to_cities_new = defaultdict(list)
for province in province_cities.keys():
    for city in province_cities[province]:
        code = CITY_CODES.get(city)
        if code:
            province_to_cities_new[province].append((city, code))

code_lines = ["CITY_CODES = {"]
for province in province_order:
    if province in province_to_cities_new:
        code_lines.append(f"    # {province}")
        cities = sorted(province_to_cities_new[province], key=lambda x: x[1])
        city_lines = [f'    "{city}": "{code}"' for city, code in cities]
        for i in range(0, len(city_lines), 4):
            line = ", ".join(city_lines[i:i+4])
            if i + 4 < len(city_lines):
                line += ","
            code_lines.append(line)
        code_lines.append("")
code_lines.append("}")

# 写入文件
with open('/Users/caihd/Desktop/hzf/backend/city_codes_from_api.py', 'w', encoding='utf-8') as f:
    f.write("\n".join(code_lines))

print("\n更新后的CITY_CODES已保存到: /Users/caihd/Desktop/hzf/backend/city_codes_from_api.py")

# 生成前端更新代码
print("\n" + "=" * 80)
print("生成更新后的前端provinceCascadeOptions")
print("=" * 80)

frontend_lines = ["const provinceCascadeOptions = ["]
for province in province_order:
    if province in province_cities:
        code = PROVINCE_CODES.get(province, "")
        cities = sorted(province_cities[province])
        cities_str = repr(cities).replace("'", '"')
        frontend_lines.append(f"  {{ code: '{code}', name: '{province}', children: {cities_str} }},")
frontend_lines.append("]")

# 写入文件
with open('/Users/caihd/Desktop/hzf/frontend_cities_from_api.js', 'w', encoding='utf-8') as f:
    f.write("\n".join(frontend_lines))

print("更新后的前端城市列表已保存到: /Users/caihd/Desktop/hzf/frontend_cities_from_api.js")

print("\n" + "=" * 80)
print("统计")
print("=" * 80)
print(f"发现 {sum(len(cities) for cities in province_cities.values())} 个有数据的城市")
print(f"覆盖 {len(province_cities)} 个省份")

# 列出没有匹配到城市代码的城市
print("\n" + "=" * 80)
print("未匹配到城市代码的城市（需要手动添加或忽略）")
print("=" * 80)
for province in sorted(province_cities.keys()):
    for city in sorted(province_cities[province]):
        if city not in CITY_CODES:
            print(f"  {province} - {city}")
