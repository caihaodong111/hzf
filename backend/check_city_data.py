"""
检查前端配置的省份和城市，找出哪些没有数据
"""
import os
import sys
import json

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture.settings')
import django
django.setup()

from apps.sensors.models import SensorDataSnapshot
from django.db.models import Count

# 前端配置的省份和城市（从Dashboard.vue）
provinceCascadeOptions = [
  { 'code': '110000', 'name': '北京市', 'children': ["东城区", "丰台区", "朝阳区", "海淀区", "石景山区", "西城区"] },
  { 'code': '120000', 'name': '天津市', 'children': ["宝坻区", "武清区", "河北区", "津南区", "滨海新区", "红桥区", "蓟州区", "西青区"] },
  { 'code': '130000', 'name': '河北省', 'children': ["保定市", "唐山市", "廊坊市", "张家口市", "承德市", "沧州市", "石家庄市", "秦皇岛市", "衡水市", "邢台市", "邯郸市"] },
  { 'code': '140000', 'name': '山西省', 'children': ["临汾市", "吕梁市", "大同市", "太原市", "忻州市", "晋中市", "晋城市", "朔州市", "运城市", "长治市", "阳泉市"] },
  { 'code': '150000', 'name': '内蒙古自治区', 'children': ["包头市", "呼伦贝尔市"] },
  { 'code': '210000', 'name': '辽宁省', 'children': ["丹东市", "大连市", "抚顺市", "朝阳市", "本溪市", "沈阳市", "盘锦市", "营口市", "葫芦岛市", "辽阳市", "铁岭市", "锦州市", "鞍山市"] },
  { 'code': '220000', 'name': '吉林省', 'children': ["吉林市", "四平市", "松原市", "白城市", "白山市", "辽源市", "通化市", "长春市"] },
  { 'code': '230000', 'name': '黑龙江省', 'children': ["伊春市", "佳木斯市", "哈尔滨市", "大庆市", "牡丹江市", "鸡西市", "鹤岗市", "黑河市", "齐齐哈尔市"] },
  { 'code': '310000', 'name': '上海市', 'children': ["嘉定区", "奉贤区", "宝山区", "崇明区", "徐汇区", "松江区", "浦东新区", "闵行区", "青浦区", "静安区"] },
  { 'code': '320000', 'name': '江苏省', 'children': ["南京市", "南通市", "宿迁市", "常州市", "徐州市", "扬州市", "无锡市", "泰州市", "淮安市", "盐城市", "苏州市", "连云港市", "镇江市"] },
  { 'code': '330000', 'name': '浙江省', 'children': ["丽水市", "台州市", "嘉兴市", "宁波市", "杭州市", "温州市", "湖州市", "绍兴市", "舟山市", "衢州市", "金华市"] },
  { 'code': '340000', 'name': '安徽省', 'children': ["亳州市", "六安市", "合肥市", "安庆市", "宣城市", "宿州市", "池州市", "淮北市", "淮南市", "滁州市", "芜湖市", "蚌埠市", "铜陵市", "阜阳市", "马鞍山市", "黄山市"] },
  { 'code': '350000', 'name': '福建省', 'children': ["三明市", "南平市", "厦门市", "宁德市", "泉州市", "漳州市", "福州市", "莆田市", "龙岩市"] },
  { 'code': '360000', 'name': '江西省', 'children': ["上饶市", "九江市", "南昌市", "吉安市", "宜春市", "抚州市", "新余市", "景德镇市", "萍乡市", "赣州市", "鹰潭市"] },
  { 'code': '370000', 'name': '山东省', 'children': ["东营市", "临沂市", "威海市", "德州市", "日照市", "枣庄市", "泰安市", "济南市", "济宁市", "淄博市", "滨州市", "潍坊市", "烟台市", "聊城市", "菏泽市", "青岛市"] },
  { 'code': '410000', 'name': '河南省', 'children': ["三门峡市", "信阳市", "南阳市", "周口市", "商丘市", "安阳市", "平顶山市", "开封市", "新乡市", "洛阳市", "济源市", "漯河市", "濮阳市", "焦作市", "郑州市", "驻马店市", "鹤壁市"] },
  { 'code': '420000', 'name': '湖北省', 'children': ["十堰市", "咸宁市", "孝感市", "宜昌市", "武汉市", "荆州市", "荆门市", "襄阳市", "鄂州市", "随州市", "黄冈市", "黄石市"] },
  { 'code': '430000', 'name': '湖南省', 'children': ["娄底市", "岳阳市", "常德市", "张家界市", "怀化市", "株洲市", "永州市", "湘潭市", "益阳市", "衡阳市", "邵阳市", "郴州市", "长沙市"] },
  { 'code': '440000', 'name': '广东省', 'children': ["东莞市", "中山市", "云浮市", "佛山市", "广州市", "惠州市", "揭阳市", "梅州市", "汕头市", "汕尾市", "江门市", "河源市", "深圳市", "清远市", "湛江市", "潮州市", "珠海市", "肇庆市", "茂名市", "阳江市", "韶关市"] },
  { 'code': '450000', 'name': '广西壮族自治区', 'children': ["北海市", "南宁市", "崇左市", "来宾市", "柳州市", "桂林市", "梧州市", "河池市", "玉林市", "百色市", "贵港市", "贺州市", "钦州市", "防城港市"] },
  { 'code': '460000', 'name': '海南省', 'children': ["三亚市", "儋州市", "海口市"] },
  { 'code': '500000', 'name': '重庆市', 'children': ["万州区", "九龙坡区", "江北区", "涪陵区"] },
  { 'code': '510000', 'name': '四川省', 'children': ["乐山市", "内江市", "南充市", "宜宾市", "巴中市", "广元市", "广安市", "德阳市", "成都市", "攀枝花市", "泸州市", "眉山市", "绵阳市", "自贡市", "资阳市", "达州市", "遂宁市", "雅安市"] },
  { 'code': '520000', 'name': '贵州省', 'children': ["六盘水市", "安顺市", "毕节市", "贵阳市", "遵义市", "铜仁市"] },
  { 'code': '530000', 'name': '云南省', 'children': ["临沧市", "丽江市", "保山市", "昆明市", "昭通市", "普洱市", "曲靖市", "玉溪市"] },
  { 'code': '540000', 'name': '西藏自治区', 'children': ["拉萨市"] },
  { 'code': '610000', 'name': '陕西省', 'children': ["咸阳市", "商洛市", "安康市", "宝鸡市", "延安市", "榆林市", "汉中市", "渭南市", "西安市", "铜川市"] },
  { 'code': '620000', 'name': '甘肃省', 'children': ["兰州市", "嘉峪关市", "天水市", "平凉市", "张掖市", "武威市", "白银市", "金昌市", "陇南市"] },
  { 'code': '630000', 'name': '青海省', 'children': ["海东市", "西宁市"] },
  { 'code': '640000', 'name': '宁夏回族自治区', 'children': ["中卫市", "吴忠市", "固原市", "石嘴山市", "银川市"] },
  { 'code': '650000', 'name': '新疆维吾尔自治区', 'children': ["乌鲁木齐市"] },
]

print('=' * 80)
print('检查前端配置的省份和城市数据情况')
print('=' * 80)

# 获取数据库中实际有数据的省份和城市
all_snapshots = SensorDataSnapshot.objects.all()

# 按省份统计
province_stats = all_snapshots.values('province').annotate(
    count=Count('snapshot_id')
)

has_data_provinces = set()
province_to_cities = {}

for stat in province_stats:
    province = stat['province']
    if province:
        has_data_provinces.add(province)
        # 获取该省份下的城市
        cities = all_snapshots.filter(province=province).values_list('city', flat=True).distinct()
        province_to_cities[province] = set([c for c in cities if c])

# 检查没有数据的省份
print('\n【没有数据的省份】')
print('=' * 80)
no_data_provinces = []
for option in provinceCascadeOptions:
    province_name = option['name']
    if province_name not in has_data_provinces:
        no_data_provinces.append(province_name)
        print(f"  {province_name} ({option['code']})")

# 检查有数据省份中没有数据的城市
print(f'\n共 {len(no_data_provinces)} 个省份完全没有数据\n')

print('【有数据省份中没有数据的城市】')
print('=' * 80)

no_data_cities_by_province = {}
for option in provinceCascadeOptions:
    province_name = option['name']
    if province_name in has_data_provinces:
        configured_cities = set(option['children'])
        actual_cities = province_to_cities.get(province_name, set())

        no_data_cities = configured_cities - actual_cities
        if no_data_cities:
            no_data_cities_by_province[province_name] = sorted(list(no_data_cities))

for province, cities in no_data_cities_by_province.items():
    print(f"\n{province} ({len(cities)}个城市没有数据):")
    for city in cities:
        print(f"  - {city}")

# 统计
total_provinces = len(provinceCascadeOptions)
total_cities = sum(len(opt['children']) for opt in provinceCascadeOptions)
provinces_with_data = len(has_data_provinces)

cities_with_data = sum(len(cities) for cities in province_to_cities.values())
cities_without_data = total_cities - cities_with_data

print('\n' + '=' * 80)
print('【统计汇总】')
print('=' * 80)
print(f"前端配置省份: {total_provinces} 个")
print(f"前端配置城市: {total_cities} 个")
print(f"有数据的省份: {provinces_with_data} 个")
print(f"没有数据的省份: {len(no_data_provinces)} 个")
print(f"有数据的城市: {cities_with_data} 个")
print(f"没有数据的城市: {cities_without_data} 个")
