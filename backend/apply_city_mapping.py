"""
Apply manual city mapping to CSV caches and database snapshots.

This script:
1) Updates CSVs under ../pc/ by adding/filling the "城市" column.
2) Updates SensorDataSnapshot.city where empty and matched by
   (province, river_basin, device_name).
"""
import csv
import os
from pathlib import Path

import django


MAPPING_ROWS = [
    ("临江", "上海市", "太湖流域", "上海市"),
    ("浙江路桥", "上海市", "太湖流域", "上海市"),
    ("江津大桥", "重庆市", "长江流域", "江津区"),
    ("渠江码头", "重庆市", "长江流域", "合川区"),
    ("鸭江镇", "重庆市", "长江流域", "武隆区"),
    ("江口镇", "重庆市", "长江流域", "云阳县"),
    ("小江河口", "重庆市", "长江流域", "万州区"),
    ("汤溪河江口", "重庆市", "长江流域", "巫溪县"),
    ("郁江桥", "重庆市", "长江流域", "彭水苗族土家族自治县"),
    ("江桥", "辽宁省", "辽河流域", "铁岭市"),
    ("通江口", "辽宁省", "辽河流域", "铁岭市"),
    ("松花江村", "吉林省", "松花江流域", "吉林市"),
    ("镇江口", "吉林省", "松花江流域", "松原市"),
    ("江桥", "黑龙江省", "松花江流域", "齐齐哈尔市"),
    ("嫩江口内", "黑龙江省", "松花江流域", "黑河市"),
    ("同江", "黑龙江省", "松花江流域", "佳木斯市"),
    ("江边闸", "江苏省", "太湖流域", "扬州市"),
    ("三江营", "江苏省", "长江流域", "扬州市"),
    ("江都西闸", "江苏省", "淮河流域", "扬州市"),
    ("菁江渡", "浙江省", "浙闽片流域", "绍兴市"),
    ("曹娥江大闸", "浙江省", "浙闽片流域", "绍兴市"),
    ("南江桥", "浙江省", "浙闽片流域", "绍兴市"),
    ("永宁江口", "浙江省", "浙闽片流域", "绍兴市"),
    ("临江", "浙江省", "浙闽片流域", "绍兴市"),
    ("王江泾", "浙江省", "太湖流域", "嘉兴市"),
    ("得胜河", "安徽省", "长江流域", "池州市"),
    ("乌江", "安徽省", "长江流域", "池州市"),
    ("顺安河", "安徽省", "长江流域", "池州市"),
    ("前江口", "安徽省", "长江流域", "池州市"),
    ("华阳河", "安徽省", "长江流域", "池州市"),
    ("秋浦河入江口", "安徽省", "长江流域", "池州市"),
    ("横江大桥", "安徽省", "浙闽片流域", "黄山市"),
    ("连江荷山渡口", "福建省", "浙闽片河流", "福州市"),
    ("闽清雄江", "福建省", "浙闽片河流", "福州市"),
    ("江口桥", "福建省", "浙闽片河流", "南平市"),
    ("孔目江", "江西省", "长江流域", "吉安市"),
    ("梅江", "江西省", "长江流域", "吉安市"),
    ("平江", "江西省", "长江流域", "吉安市"),
    ("上犹江", "江西省", "长江流域", "吉安市"),
    ("桃江", "江西省", "长江流域", "吉安市"),
    ("孤江", "江西省", "长江流域", "吉安市"),
    ("遂川江", "江西省", "长江流域", "吉安市"),
    ("乌江", "江西省", "长江流域", "吉安市"),
    ("肖江江口", "江西省", "长江流域", "吉安市"),
    ("丹江口水库坝上中", "湖北省", "长江流域", "十堰市"),
    ("清江大桥", "湖北省", "长江流域", "恩施土家族苗族自治州"),
    ("江口村", "湖北省", "长江流域", "宜昌市"),
    ("潜江大桥", "湖北省", "长江流域", "潜江市"),
    ("舂陵水", "湖南省", "长江流域", "衡阳市"),
    ("耒水", "湖南省", "长江流域", "衡阳市"),
    ("洣水", "湖南省", "长江流域", "衡阳市"),
    ("蒸水入湘江口", "湖南省", "长江流域", "衡阳市"),
    ("荆江口", "湖南省", "长江流域", "岳阳市"),
    ("澧水三江口", "湖南省", "长江流域", "常德市"),
    ("江口", "湖南省", "长江流域", "怀化市"),
    ("增江口", "广东省", "珠江流域", "惠州市"),
    ("东江江口", "广东省", "珠江流域", "惠州市"),
    ("黄竹尾水闸", "广东省", "珠江流域", "阳江市"),
    ("江城", "广东省", "珠江流域", "阳江市"),
    ("江口门", "广东省", "珠江流域", "江门市"),
    ("北江石尾", "广东省", "珠江流域", "韶关市"),
    ("连江西牛", "广东省", "珠江流域", "清远市"),
    ("凤江桥", "广东省", "珠江流域", "揭阳市"),
    ("雁江", "广西壮族自治区", "珠江流域", "柳州市"),
    ("象州运江老街", "广西壮族自治区", "珠江流域", "柳州市"),
    ("西门江", "广西壮族自治区", "珠江流域", "北海市"),
    ("钦江东", "广西壮族自治区", "珠江流域", "钦州市"),
    ("棉江", "广西壮族自治区", "珠江流域", "贵港市"),
    ("龙江", "海南省", "珠江流域", "琼海市"),
    ("二江寺", "四川省", "长江流域", "成都市"),
    ("沱江大桥", "四川省", "长江流域", "成都市"),
    ("双江桥", "四川省", "长江流域", "成都市"),
    ("雅砻江口", "四川省", "长江流域", "攀枝花市"),
    ("梓江大桥", "四川省", "长江流域", "绵阳市"),
    ("彭山岷江大桥", "四川省", "长江流域", "眉山市"),
    ("江陵", "四川省", "长江流域", "达州市"),
    ("金沙江岗托桥", "四川省", "长江流域", "甘孜藏族自治州"),
    ("沿江渡", "贵州省", "长江流域", "黔东南苗族侗族自治州"),
    ("重安江大桥", "贵州省", "长江流域", "黔东南苗族侗族自治州"),
    ("南盘江三江口", "贵州省", "珠江流域", "黔西南布依族苗族自治州"),
    ("从江大桥", "贵州省", "珠江流域", "黔东南苗族侗族自治州"),
    ("榕江", "贵州省", "珠江流域", "黔东南苗族侗族自治州"),
    ("严家村桥", "云南省", "滇池流域", "昆明市"),
    ("江尾下闸", "云南省", "滇池流域", "昆明市"),
    ("牛栏江河口", "云南省", "长江流域", "曲靖市"),
    ("牛栏江大桥", "云南省", "长江流域", "曲靖市"),
]


def mapping_dict():
    data = {}
    for name, province, basin, city in MAPPING_ROWS:
        data[(name.strip(), province.strip(), basin.strip())] = city.strip()
    return data


def update_csvs(mapping):
    base_dir = Path(__file__).resolve().parent.parent
    pc_dir = base_dir / "pc"
    updated = {}
    for path in sorted(pc_dir.glob("*.csv")):
        if path.name == "test_time.csv":
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                continue
            fieldnames = list(reader.fieldnames)
            if "城市" not in fieldnames:
                fieldnames.insert(1, "城市")

            rows = []
            matched = 0
            for row in reader:
                name = (row.get("断面名称") or "").strip()
                province = (row.get("省份") or "").strip()
                basin = (row.get("流域") or "").strip()
                key = (name, province, basin)
                if key in mapping and not (row.get("城市") or "").strip():
                    row["城市"] = mapping[key]
                    matched += 1
                rows.append(row)

        target = path
        if not path.name.endswith("_with_city.csv"):
            target = path.with_name(f"{path.stem}_with_city.csv")

        with target.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        updated[target.name] = matched

    return updated


def update_database(mapping):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aquaculture.settings")
    django.setup()

    from django.db.models import Q
    from apps.sensors.models import SensorDataSnapshot

    total = 0
    for (name, province, basin), city in mapping.items():
        qs = SensorDataSnapshot.objects.filter(
            device_name=name,
            province=province,
            river_basin=basin,
        ).filter(Q(city__isnull=True) | Q(city=""))
        updated = qs.update(city=city)
        total += updated
    return total


def main():
    mapping = mapping_dict()
    csv_updates = update_csvs(mapping)
    print("CSV updates:")
    for name, count in csv_updates.items():
        print(f"  {name}: {count} rows updated")

    db_updates = update_database(mapping)
    print(f"Database updates: {db_updates} rows updated")


if __name__ == "__main__":
    main()
