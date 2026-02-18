"""
测试所有省份城市的API数据支持情况
"""
import os
import sys
import django
import time

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture.settings')
django.setup()

from core.national_water_data import CITY_CODES, NationalWaterDataService

print("=" * 80)
print("测试所有城市API数据支持情况")
print("=" * 80)
print(f"总共需要测试 {len(CITY_CODES)} 个城市/区\n")

# 获取服务实例
service = NationalWaterDataService()

supported_cities = {}
unsupported_cities = {}
error_cities = {}

# 按省份分组显示进度
province_order = [
    ("北京市", ["东城区", "西城区", "朝阳区", "海淀区", "丰台区", "石景山区"]),
    ("天津市", ["河北区", "红桥区", "西青区", "津南区", "武清区", "宝坻区", "滨海新区", "蓟州区"]),
    ("河北省", ["石家庄市", "唐山市", "秦皇岛市", "邯郸市", "邢台市", "保定市", "张家口市", "承德市", "沧州市", "廊坊市", "衡水市"]),
    ("山西省", ["太原市", "大同市", "阳泉市", "长治市", "晋城市", "朔州市", "晋中市", "运城市", "忻州市", "临汾市", "吕梁市"]),
    ("内蒙古自治区", ["呼和浩特市", "包头市", "乌海市", "赤峰市", "通辽市", "鄂尔多斯市", "呼伦贝尔市", "巴彦淖尔市", "乌兰察布市"]),
    ("辽宁省", ["沈阳市", "大连市", "鞍山市", "抚顺市", "本溪市", "丹东市", "锦州市", "营口市", "阜新市", "辽阳市", "盘锦市", "铁岭市", "朝阳市", "葫芦岛市"]),
    ("吉林省", ["长春市", "吉林市", "四平市", "辽源市", "通化市", "白山市", "松原市", "白城市"]),
    ("黑龙江省", ["哈尔滨市", "齐齐哈尔市", "鸡西市", "鹤岗市", "双鸭山市", "大庆市", "伊春市", "佳木斯市", "七台河市", "牡丹江市", "黑河市", "绥化市"]),
    ("上海市", ["黄浦区", "徐汇区", "长宁区", "静安区", "普陀区", "虹口区", "杨浦区", "闵行区", "宝山区", "嘉定区", "浦东新区", "金山区", "松江区", "青浦区", "奉贤区", "崇明区"]),
    ("江苏省", ["南京市", "无锡市", "徐州市", "常州市", "苏州市", "南通市", "连云港市", "淮安市", "盐城市", "扬州市", "镇江市", "泰州市", "宿迁市"]),
    ("浙江省", ["杭州市", "宁波市", "温州市", "嘉兴市", "湖州市", "绍兴市", "金华市", "衢州市", "舟山市", "台州市", "丽水市"]),
    ("安徽省", ["合肥市", "芜湖市", "蚌埠市", "淮南市", "马鞍山市", "淮北市", "铜陵市", "安庆市", "黄山市", "滁州市", "阜阳市", "宿州市", "六安市", "亳州市", "池州市", "宣城市"]),
    ("福建省", ["福州市", "厦门市", "莆田市", "三明市", "泉州市", "漳州市", "南平市", "龙岩市", "宁德市"]),
    ("江西省", ["南昌市", "景德镇市", "萍乡市", "九江市", "新余市", "鹰潭市", "赣州市", "吉安市", "宜春市", "抚州市", "上饶市"]),
    ("山东省", ["济南市", "青岛市", "淄博市", "枣庄市", "东营市", "烟台市", "潍坊市", "济宁市", "泰安市", "威海市", "日照市", "临沂市", "德州市", "聊城市", "滨州市", "菏泽市"]),
    ("河南省", ["郑州市", "开封市", "洛阳市", "平顶山市", "安阳市", "鹤壁市", "新乡市", "焦作市", "濮阳市", "许昌市", "漯河市", "三门峡市", "南阳市", "商丘市", "信阳市", "周口市", "驻马店市", "济源市"]),
    ("湖北省", ["武汉市", "黄石市", "十堰市", "宜昌市", "襄阳市", "鄂州市", "荆门市", "孝感市", "荆州市", "黄冈市", "咸宁市", "随州市"]),
    ("湖南省", ["长沙市", "株洲市", "湘潭市", "衡阳市", "邵阳市", "岳阳市", "常德市", "张家界市", "益阳市", "郴州市", "永州市", "怀化市", "娄底市"]),
    ("广东省", ["广州市", "韶关市", "深圳市", "珠海市", "汕头市", "佛山市", "江门市", "湛江市", "茂名市", "肇庆市", "惠州市", "梅州市", "汕尾市", "河源市", "阳江市", "清远市", "东莞市", "中山市", "潮州市", "揭阳市", "云浮市"]),
    ("广西壮族自治区", ["南宁市", "柳州市", "桂林市", "梧州市", "北海市", "防城港市", "钦州市", "贵港市", "玉林市", "百色市", "贺州市", "河池市", "来宾市", "崇左市"]),
    ("海南省", ["海口市", "三亚市", "三沙市", "儋州市"]),
    ("重庆市", ["万州区", "涪陵区", "渝中区", "大渡口区", "江北区", "沙坪坝区", "九龙坡区", "南岸区"]),
    ("四川省", ["成都市", "自贡市", "攀枝花市", "泸州市", "德阳市", "绵阳市", "广元市", "遂宁市", "内江市", "乐山市", "南充市", "眉山市", "宜宾市", "广安市", "达州市", "雅安市", "巴中市", "资阳市"]),
    ("贵州省", ["贵阳市", "六盘水市", "遵义市", "安顺市", "毕节市", "铜仁市"]),
    ("云南省", ["昆明市", "曲靖市", "玉溪市", "保山市", "昭通市", "丽江市", "普洱市", "临沧市"]),
    ("西藏自治区", ["拉萨市"]),
    ("陕西省", ["西安市", "铜川市", "宝鸡市", "咸阳市", "渭南市", "延安市", "汉中市", "榆林市", "安康市", "商洛市"]),
    ("甘肃省", ["兰州市", "嘉峪关市", "金昌市", "白银市", "天水市", "武威市", "张掖市", "平凉市", "酒泉市", "庆阳市", "定西市", "陇南市"]),
    ("青海省", ["西宁市", "海东市"]),
    ("宁夏回族自治区", ["银川市", "石嘴山市", "吴忠市", "固原市", "中卫市"]),
    ("新疆维吾尔自治区", ["乌鲁木齐市", "克拉玛依市", "吐鲁番市", "哈密市"]),
]

# 创建省份到城市的映射
province_to_cities = {province: cities for province, cities in province_order}

test_count = 0
start_time = time.time()

for province_name, city_list in province_order:
    print(f"\n{'=' * 80}")
    print(f"测试 {province_name} ({len(city_list)}个城市)")
    print('=' * 80)

    province_supported = {}
    province_unsupported = []

    for city_name in city_list:
        test_count += 1
        area_id = CITY_CODES.get(city_name)

        if not area_id:
            print(f"  ⚠️  {city_name}: 代码未找到")
            continue

        print(f"  [{test_count}/{len(CITY_CODES)}] 测试 {city_name} (AreaID: {area_id})...", end=" ")

        try:
            result = service.get_realtime(
                count=5,
                area_id=area_id,
                force_refresh=False  # 使用缓存加速
            )

            sensors = result.get("sensors", [])
            total = result.get("total", 0)

            if len(sensors) > 0:
                province_supported[city_name] = {
                    'area_id': area_id,
                    'count': total
                }
                print(f"✅ {total}条")
                supported_cities[city_name] = area_id
            else:
                province_unsupported.append(city_name)
                print(f"❌ 无数据")
                unsupported_cities[city_name] = area_id

            # 添加延迟避免请求过快
            time.sleep(0.1)

        except Exception as e:
            print(f"⚠️  错误: {e}")
            error_cities[city_name] = area_id

    # 输出该省结果
    print(f"\n{province_name}结果: ✅{len(province_supported)}个有数据, ❌{len(province_unsupported)}个无数据")

# 计算总时间
elapsed_time = time.time() - start_time

# 输出总结
print("\n" + "=" * 80)
print("测试完成！总结")
print("=" * 80)
print(f"测试城市数: {test_count}")
print(f"耗时: {elapsed_time:.1f}秒")
print(f"\n✅ 有数据的城市: {len(supported_cities)}个")
print(f"❌ 无数据的城市: {len(unsupported_cities)}个")
print(f"⚠️  错误的城市: {len(error_cities)}个")

# 生成更新后的代码
print("\n" + "=" * 80)
print("生成更新后的CITY_CODES代码")
print("=" * 80)

code_output = ["CITY_CODES = {"]
for province_name, city_list in province_order:
    # 找出该省有数据的城市
    province_supported = [city for city in city_list if city in supported_cities]
    if province_supported:
        # 找出省份代码（取第一个城市的代码前2位+0000）
        first_city_code = CITY_CODES[province_supported[0]]
        province_code = first_city_code[:2] + "0000"

        # 添加注释
        province_comment = f"    # {province_name}"
        code_output.append(province_comment)

        # 添加城市
        city_lines = []
        for city in province_supported:
            city_lines.append(f'    "{city}": "{CITY_CODES[city]}"')

        # 将城市按行排列，每行最多4个城市
        for i in range(0, len(city_lines), 4):
            code_output.append(", ".join(city_lines[i:i+4]) + ("," if i + 4 < len(city_lines) else ""))
        code_output.append("")  # 空行分隔省份

code_output.append("}")

# 写入文件
with open('/Users/caihd/Desktop/hzf/backend/updated_city_codes.py', 'w', encoding='utf-8') as f:
    f.write("\n".join(code_output))

print("\n更新后的代码已保存到: /Users/caihd/Desktop/hzf/backend/updated_city_codes.py")

# 输出无数据城市列表
if unsupported_cities:
    print("\n" + "=" * 80)
    print("无数据城市列表（需要从CITY_CODES中移除）:")
    print("=" * 80)
    for city in sorted(unsupported_cities.keys()):
        print(f'  "{city}": "{unsupported_cities[city]}",')
