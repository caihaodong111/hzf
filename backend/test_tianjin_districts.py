"""
测试天津市各区API数据支持情况
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture.settings')
django.setup()

from core.national_water_data import NationalWaterDataService
import json

# 天津各区代码
tianjin_districts = {
    "和平区": "120101",
    "河东区": "120102",
    "河西区": "120103",
    "南开区": "120104",
    "河北区": "120105",
    "红桥区": "120106",
    "东丽区": "120110",
    "西青区": "120111",
    "津南区": "120112",
    "北辰区": "120113",
    "武清区": "120114",
    "宝坻区": "120115",
    "滨海新区": "120116",
    "宁河区": "120117",
    "静海区": "120118",
    "蓟州区": "120119",
}

print("=" * 60)
print("测试天津市各区API数据支持情况")
print("=" * 60)

# 获取服务实例
service = NationalWaterDataService()

supported_districts = {}
unsupported_districts = {}

for district_name, area_id in tianjin_districts.items():
    print(f"\n测试 {district_name} (AreaID: {area_id})...")
    print("-" * 40)

    try:
        # 使用城市代码作为AreaID获取数据
        result = service.get_realtime(
            count=10,
            area_id=area_id,  # 使用区代码作为AreaID
            force_refresh=True
        )

        sensors = result.get("sensors", [])
        total = result.get("total", 0)

        print(f"  返回数据条数: {len(sensors)}")
        print(f"  总数据条数: {total}")

        if len(sensors) > 0:
            # 显示前几条数据的断面名称
            print(f"  样本断面:")
            for sensor in sensors[:3]:
                device_name = sensor.get('device_name', 'N/A')
                location = sensor.get('location', 'N/A')
                print(f"    - {device_name} ({location})")
            supported_districts[district_name] = {
                'area_id': area_id,
                'count': total,
                'sample': [s.get('device_name') for s in sensors[:3]]
            }
        else:
            print(f"  ❌ 无数据")
            unsupported_districts[district_name] = area_id

    except Exception as e:
        print(f"  ❌ 错误: {e}")
        unsupported_districts[district_name] = area_id

# 输出总结
print("\n" + "=" * 60)
print("测试结果总结")
print("=" * 60)

print(f"\n✅ 有数据的区 ({len(supported_districts)}个):")
for district, info in sorted(supported_districts.items()):
    print(f"  - {district} (AreaID: {info['area_id']}, 数据条数: {info['count']})")

print(f"\n❌ 无数据的区 ({len(unsupported_districts)}个):")
for district, area_id in sorted(unsupported_districts.items()):
    print(f"  - {district} (AreaID: {area_id})")

# 生成更新后的代码片段
print("\n" + "=" * 60)
print("更新后的CITY_CODES（天津市部分）:")
print("=" * 60)
print("\n    # 天津市")
for district, info in sorted(supported_districts.items()):
    print(f'    "{district}": "{info["area_id"]}",')

# 生成前端更新后的代码
print("\n" + "=" * 60)
print("更新后的provinceCascadeOptions（天津市部分）:")
print("=" * 60)
print("\n  { code: '120000', name: '天津市', children: [")
children = [f'    "{d}"' for d in sorted(supported_districts.keys())]
print(",\n".join(children))
print("  ] },")
