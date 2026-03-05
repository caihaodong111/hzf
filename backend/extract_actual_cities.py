"""
通过获取全国数据提取实际有数据的城市列表
"""
import os
import sys
import django
from collections import defaultdict

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture.settings')
django.setup()

from core.national_water_data import NationalWaterDataService
from core.data_transformer import DataTransformer

print("=" * 80)
print("获取全国数据并提取有数据的城市")
print("=" * 80)

service = NationalWaterDataService()

# 获取全国数据，设置较大的count以获取更多数据
print("正在获取全国数据...")
result = service.get_realtime(count=1000, force_refresh=True)

sensors = result.get("sensors", [])
print(f"共获取到 {len(sensors)} 条监测数据\n")

# 按省份分组统计
province_cities = defaultdict(set)
province_city_count = defaultdict(lambda: defaultdict(int))

for sensor in sensors:
    province = sensor.get('province')
    city = sensor.get('city')

    if province:
        province_cities[province].add(city)
        if city:
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

# 城市代码映射（完整）
from core.national_water_data import CITY_CODES

# 生成新的CITY_CODES
new_city_codes = {}
new_frontend_cities = {}

for province in sorted(province_cities.keys()):
    cities = sorted([c for c in province_cities[province] if c])
    print(f"\n{province} ({len(cities)}个城市):")
    for city in cities:
        count = province_city_count[province][city]
        code = CITY_CODES.get(city, "")
        print(f"  - {city}: {count}条 (代码: {code})")
        if code:
            new_city_codes[city] = code
    new_frontend_cities[province] = cities

# 生成更新后的CITY_CODES代码
print("\n" + "=" * 80)
print("生成更新后的CITY_CODES")
print("=" * 80)

code_lines = ["CITY_CODES = {"]
for province in sorted(new_city_codes.values()):
    # 按省份分组需要反向映射
    pass

# 按省份分组输出
province_order = [
    "北京市", "天津市", "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省",
    "上海市", "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省",
    "重庆市", "四川省", "贵州省", "云南省", "西藏自治区",
    "陕西省", "甘肃省", "青海省", "宁夏回族自治区", "新疆维吾尔自治区"
]

# 按省份分组
province_to_cities_new = defaultdict(list)
for city in new_city_codes.keys():
    code = new_city_codes[city]
    # 从代码推断省份
    province_code = code[:2] + "0000"
    for province, pcode in PROVINCE_CODES.items():
        if pcode == province_code:
            province_to_cities_new[province].append((city, code))
            break

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
    if province in new_frontend_cities:
        code = PROVINCE_CODES.get(province, "")
        cities = sorted(new_frontend_cities[province])
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
print(f"发现 {len(new_city_codes)} 个有数据的城市")
print(f"覆盖 {len(province_to_cities_new)} 个省份")
