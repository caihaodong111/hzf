"""
生成更新后的前端provinceCascadeOptions
"""
import json

# 读取测试结果
with open('/Users/caihd/Desktop/hzf/backend/city_test_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

supported_cities = cache['supported']

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

# 省份顺序
province_order = [
    "北京市", "天津市", "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省",
    "上海市", "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省",
    "重庆市", "四川省", "贵州省", "云南省", "西藏自治区",
    "陕西省", "甘肃省", "青海省", "宁夏回族自治区", "新疆维吾尔自治区"
]

# 按省份分组
province_to_cities = {}
for city, code in supported_cities.items():
    province_code = code[:2] + "0000"
    for province, p_code in PROVINCE_CODES.items():
        if p_code == province_code:
            if province not in province_to_cities:
                province_to_cities[province] = []
            province_to_cities[province].append(city)
            break

# 生成前端代码
frontend_lines = []
for province in province_order:
    if province in province_to_cities:
        code = PROVINCE_CODES[province]
        cities = sorted(province_to_cities[province])
        cities_str = str(cities).replace("'", '"')
        frontend_lines.append(f"  {{ code: '{code}', name: '{province}', children: {cities_str} }},")

# 输出结果
print("const provinceCascadeOptions = [")
print("\n".join(frontend_lines))
print("]")

# 同时生成按省份分组的列表，方便复制
print("\n\n按省份分组（用于检查）:")
for province in province_order:
    if province in province_to_cities:
        cities = sorted(province_to_cities[province])
        print(f"{province}: {', '.join(cities)}")
