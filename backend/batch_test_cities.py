"""
批量测试所有城市代码的API数据支持情况
可以中断和继续
"""
import os
import sys
import django
import json
import time
from datetime import datetime

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture.settings')
django.setup()

from core.national_water_data import CITY_CODES, NationalWaterDataService

# 结果缓存文件
CACHE_FILE = '/Users/caihd/Desktop/hzf/backend/city_test_cache.json'

# 加载之前的测试结果
def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {
        'supported': {},
        'unsupported': {},
        'error': {},
        'last_tested': None
    }

# 保存测试结果
def save_cache(cache):
    cache['last_tested'] = datetime.now().isoformat()
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

print("=" * 80)
print("批量测试所有城市代码的API数据支持情况")
print("=" * 80)

cache = load_cache()

# 显示之前测试的结果
if cache['supported']:
    print(f"\n已测试 {len(cache['supported'])} 个有数据的城市")
if cache['unsupported']:
    print(f"已测试 {len(cache['unsupported'])} 个无数据的城市")
if cache['error']:
    print(f"已测试 {len(cache['error'])} 个错误的城市")

# 找出需要测试的城市
remaining_cities = {}
for city, code in CITY_CODES.items():
    if city not in cache['supported'] and city not in cache['unsupported'] and city not in cache['error']:
        remaining_cities[city] = code

print(f"\n还需要测试 {len(remaining_cities)} 个城市")
print(f"总共 {len(CITY_CODES)} 个城市")

if not remaining_cities:
    print("\n✅ 所有城市已测试完成！")
    print("\n生成更新后的代码...")

    # 生成更新后的CITY_CODES
    code_lines = ["CITY_CODES = {"]
    province_order = [
        ("北京市", "11"), ("天津市", "12"), ("河北省", "13"), ("山西省", "14"),
        ("内蒙古自治区", "15"), ("辽宁省", "21"), ("吉林省", "22"), ("黑龙江省", "23"),
        ("上海市", "31"), ("江苏省", "32"), ("浙江省", "33"), ("安徽省", "34"),
        ("福建省", "35"), ("江西省", "36"), ("山东省", "37"), ("河南省", "41"),
        ("湖北省", "42"), ("湖南省", "43"), ("广东省", "44"), ("广西壮族自治区", "45"),
        ("海南省", "46"), ("重庆市", "50"), ("四川省", "51"), ("贵州省", "52"),
        ("云南省", "53"), ("西藏自治区", "54"), ("陕西省", "61"), ("甘肃省", "62"),
        ("青海省", "63"), ("宁夏回族自治区", "64"), ("新疆维吾尔自治区", "65"),
    ]

    # 按省份分组
    province_to_cities = {}
    for city in cache['supported'].keys():
        code = cache['supported'][city]
        prefix = code[:2]
        for province, p in province_order:
            if prefix == p:
                if province not in province_to_cities:
                    province_to_cities[province] = []
                province_to_cities[province].append((city, code))
                break

    for province, p in province_order:
        if province in province_to_cities:
            code_lines.append(f"    # {province}")
            cities = sorted(province_to_cities[province], key=lambda x: x[1])
            city_lines = [f'    "{city}": "{code}"' for city, code in cities]
            for i in range(0, len(city_lines), 4):
                line = ", ".join(city_lines[i:i+4])
                if i + 4 < len(city_lines):
                    line += ","
                code_lines.append(line)
            code_lines.append("")

    code_lines.append("}")

    with open('/Users/caihd/Desktop/hzf/backend/updated_city_codes.py', 'w', encoding='utf-8') as f:
        f.write("\n".join(code_lines))

    print("\n更新后的CITY_CODES已保存到: /Users/caihd/Desktop/hzf/backend/updated_city_codes.py")
    print(f"\n有数据的城市: {len(cache['supported'])} 个")
    print(f"无数据的城市: {len(cache['unsupported'])} 个")
    sys.exit(0)

# 开始测试
service = NationalWaterDataService()
print("\n开始测试...")
print("=" * 80)

test_count = 0
start_time = time.time()

for city, code in sorted(remaining_cities.items()):
    test_count += 1
    print(f"[{test_count}/{len(remaining_cities)}] 测试 {city} (代码: {code})...", end=" ")

    try:
        result = service.get_realtime(count=5, area_id=code, force_refresh=False)
        sensors = result.get("sensors", [])
        total = result.get("total", 0)

        if len(sensors) > 0:
            cache['supported'][city] = code
            print(f"✅ {total}条")
        else:
            cache['unsupported'][city] = code
            print(f"❌ 无数据")

    except Exception as e:
        cache['error'][city] = {'code': code, 'error': str(e)}
        print(f"⚠️  错误: {e}")

    # 每50个城市保存一次缓存
    if test_count % 50 == 0:
        save_cache(cache)
        elapsed = time.time() - start_time
        avg_time = elapsed / test_count
        remaining = (len(remaining_cities) - test_count) * avg_time
        print(f"\n--- 进度: {test_count}/{len(remaining_cities)} ({test_count*100//len(remaining_cities)}%) ---")
        print(f"--- 已用时: {elapsed:.0f}秒, 预计剩余: {remaining:.0f}秒 ---")
        print("=" * 80)

    # 添加延迟避免请求过快
    time.sleep(0.15)

# 保存最终结果
save_cache(cache)

print("\n" + "=" * 80)
print("测试完成！")
print("=" * 80)
print(f"有数据的城市: {len(cache['supported'])} 个")
print(f"无数据的城市: {len(cache['unsupported'])} 个")
print(f"错误的城市: {len(cache['error'])} 个")

print("\n请再次运行此脚本生成更新后的代码")
