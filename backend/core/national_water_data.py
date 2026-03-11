"""
国家水质自动综合监管平台数据服务
数据来源：https://szzdjc.cnemc.cn:8070
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone as dj_timezone

from core.city_matcher import matches_city
from core.data_transformer import DataTransformer

logger = logging.getLogger(__name__)


# 区域代码映射
AREA_CODES = {
    "全国": "",
    "北京市": "110000", "天津市": "120000", "河北省": "130000",
    "山西省": "140000", "内蒙古自治区": "150000", "辽宁省": "210000",
    "吉林省": "220000", "黑龙江省": "230000", "上海市": "310000",
    "江苏省": "320000", "浙江省": "330000", "安徽省": "340000",
    "福建省": "350000", "江西省": "360000", "山东省": "370000",
    "河南省": "410000", "湖北省": "420000", "湖南省": "430000",
    "广东省": "440000", "广西壮族自治区": "450000", "海南省": "460000",
    "重庆市": "500000", "四川省": "510000", "贵州省": "520000",
    "云南省": "530000", "西藏自治区": "540000", "陕西省": "610000",
    "甘肃省": "620000", "青海省": "630000", "宁夏回族自治区": "640000",
    "新疆维吾尔自治区": "650000",
}

# 流域代码映射
RIVER_CODES = {
    "所有流域": "",
    "长江流域": "1100000000",
    "黄河流域": "0900000000",
    "珠江流域": "1500000000",
    "松花江流域": "0200000000",
    "淮河流域": "1000000000",
    "海河流域": "6010000000",
    "辽河流域": "0500000000",
    "浙闽片河流": "ZMP",
    "西南诸河": "6040000000",
    "西北诸河": "0800000000",
    "太湖流域": "1200000000",
    "巢湖流域": "1300000000",
    "滇池流域": "1700000000"
}

# 城市代码映射（基于6位行政区划代码）- 仅包含API实际支持的城市
CITY_CODES = {
    # 北京市
    "东城区": "110101", "西城区": "110102", "朝阳区": "110105", "丰台区": "110106",
    "石景山区": "110107", "海淀区": "110108",
    # 天津市
    "河北区": "120105", "红桥区": "120106", "西青区": "120111", "津南区": "120112",
    "武清区": "120114", "宝坻区": "120115", "滨海新区": "120116", "蓟州区": "120119",
    # 河北省
    "石家庄市": "130100", "唐山市": "130200", "秦皇岛市": "130300", "邯郸市": "130400",
    "邢台市": "130500", "保定市": "130600", "张家口市": "130700", "承德市": "130800",
    "沧州市": "130900", "廊坊市": "131000", "衡水市": "131100",
    # 山西省
    "太原市": "140100", "大同市": "140200", "阳泉市": "140300", "长治市": "140400",
    "晋城市": "140500", "朔州市": "140600", "晋中市": "140700", "运城市": "140800",
    "忻州市": "140900", "临汾市": "141000", "吕梁市": "141100",
    # 内蒙古自治区
    "包头市": "150200", "呼伦贝尔市": "150700",
    # 辽宁省
    "沈阳市": "210100", "大连市": "210200", "鞍山市": "210300", "抚顺市": "210400",
    "本溪市": "210500", "丹东市": "210600", "锦州市": "210700", "营口市": "210800",
    "辽阳市": "211000", "盘锦市": "211100", "铁岭市": "211200", "朝阳市": "211300",
    "葫芦岛市": "211400",
    # 吉林省
    "长春市": "220100", "吉林市": "220200", "四平市": "220300", "辽源市": "220400",
    "通化市": "220500", "白山市": "220600", "松原市": "220700", "白城市": "220800",
    # 黑龙江省
    "哈尔滨市": "230100", "齐齐哈尔市": "230200", "鸡西市": "230300", "鹤岗市": "230400",
    "大庆市": "230600", "伊春市": "230700", "佳木斯市": "230800", "牡丹江市": "231000",
    "黑河市": "231100",
    # 上海市
    "徐汇区": "310104", "静安区": "310106", "闵行区": "310112", "宝山区": "310113",
    "嘉定区": "310114", "浦东新区": "310115", "松江区": "310117", "青浦区": "310118",
    "奉贤区": "310120", "崇明区": "310151",
    # 江苏省
    "南京市": "320100", "无锡市": "320200", "徐州市": "320300", "常州市": "320400",
    "苏州市": "320500", "南通市": "320600", "连云港市": "320700", "淮安市": "320800",
    "盐城市": "320900", "扬州市": "321000", "镇江市": "321100", "泰州市": "321200",
    "宿迁市": "321300",
    # 浙江省
    "杭州市": "330100", "宁波市": "330200", "温州市": "330300", "嘉兴市": "330400",
    "湖州市": "330500", "绍兴市": "330600", "金华市": "330700", "衢州市": "330800",
    "舟山市": "330900", "台州市": "331000", "丽水市": "331100",
    # 安徽省
    "合肥市": "340100", "芜湖市": "340200", "蚌埠市": "340300", "淮南市": "340400",
    "马鞍山市": "340500", "淮北市": "340600", "铜陵市": "340700", "安庆市": "340800",
    "黄山市": "341000", "滁州市": "341100", "阜阳市": "341200", "宿州市": "341300",
    "六安市": "341500", "亳州市": "341600", "池州市": "341700", "宣城市": "341800",
    # 福建省
    "福州市": "350100", "厦门市": "350200", "莆田市": "350300", "三明市": "350400",
    "泉州市": "350500", "漳州市": "350600", "南平市": "350700", "龙岩市": "350800",
    "宁德市": "350900",
    # 江西省
    "南昌市": "360100", "景德镇市": "360200", "萍乡市": "360300", "九江市": "360400",
    "新余市": "360500", "鹰潭市": "360600", "赣州市": "360700", "吉安市": "360800",
    "宜春市": "360900", "抚州市": "361000", "上饶市": "361100",
    # 山东省
    "济南市": "370100", "青岛市": "370200", "淄博市": "370300", "枣庄市": "370400",
    "东营市": "370500", "烟台市": "370600", "潍坊市": "370700", "济宁市": "370800",
    "泰安市": "370900", "威海市": "371000", "日照市": "371100", "临沂市": "371300",
    "德州市": "371400", "聊城市": "371500", "滨州市": "371600", "菏泽市": "371700",
    # 河南省
    "郑州市": "410100", "开封市": "410200", "洛阳市": "410300", "平顶山市": "410400",
    "安阳市": "410500", "鹤壁市": "410600", "新乡市": "410700", "焦作市": "410800",
    "濮阳市": "410900", "漯河市": "411100", "三门峡市": "411200", "南阳市": "411300",
    "商丘市": "411400", "信阳市": "411500", "周口市": "411600", "驻马店市": "411700",
    "济源市": "419001",
    # 湖北省
    "武汉市": "420100", "黄石市": "420200", "十堰市": "420300", "宜昌市": "420500",
    "襄阳市": "420600", "鄂州市": "420700", "荆门市": "420800", "孝感市": "420900",
    "荆州市": "421000", "黄冈市": "421100", "咸宁市": "421200", "随州市": "421300",
    # 湖南省
    "长沙市": "430100", "株洲市": "430200", "湘潭市": "430300", "衡阳市": "430400",
    "邵阳市": "430500", "岳阳市": "430600", "常德市": "430700", "张家界市": "430800",
    "益阳市": "430900", "郴州市": "431000", "永州市": "431100", "怀化市": "431200",
    "娄底市": "431300",
    # 广东省
    "广州市": "440100", "韶关市": "440200", "深圳市": "440300", "珠海市": "440400",
    "汕头市": "440500", "佛山市": "440600", "江门市": "440700", "湛江市": "440800",
    "茂名市": "440900", "肇庆市": "441200", "惠州市": "441300", "梅州市": "441400",
    "汕尾市": "441500", "河源市": "441600", "阳江市": "441700", "清远市": "441800",
    "东莞市": "441900", "中山市": "442000", "潮州市": "445100", "揭阳市": "445200",
    "云浮市": "445300",
    # 广西壮族自治区
    "南宁市": "450100", "柳州市": "450200", "桂林市": "450300", "梧州市": "450400",
    "北海市": "450500", "防城港市": "450600", "钦州市": "450700", "贵港市": "450800",
    "玉林市": "450900", "百色市": "451000", "贺州市": "451100", "河池市": "451200",
    "来宾市": "451300", "崇左市": "451400",
    # 海南省
    "海口市": "460100", "三亚市": "460200", "儋州市": "460400",
    # 重庆市
    "万州区": "500101", "涪陵区": "500102", "江北区": "500105", "九龙坡区": "500107",
    # 四川省
    "成都市": "510100", "自贡市": "510300", "攀枝花市": "510400", "泸州市": "510500",
    "德阳市": "510600", "绵阳市": "510700", "广元市": "510800", "遂宁市": "510900",
    "内江市": "511000", "乐山市": "511100", "南充市": "511300", "眉山市": "511400",
    "宜宾市": "511500", "广安市": "511600", "达州市": "511700", "雅安市": "511800",
    "巴中市": "511900", "资阳市": "512000",
    # 贵州省
    "贵阳市": "520100", "六盘水市": "520200", "遵义市": "520300", "安顺市": "520400",
    "毕节市": "520500", "铜仁市": "520600",
    # 云南省
    "昆明市": "530100", "曲靖市": "530300", "玉溪市": "530400", "保山市": "530500",
    "昭通市": "530600", "丽江市": "530700", "普洱市": "530800", "临沧市": "530900",
    # 西藏自治区
    "拉萨市": "540100",
    # 陕西省
    "西安市": "610100", "铜川市": "610200", "宝鸡市": "610300", "咸阳市": "610400",
    "渭南市": "610500", "延安市": "610600", "汉中市": "610700", "榆林市": "610800",
    "安康市": "610900", "商洛市": "611000",
    # 甘肃省
    "兰州市": "620100", "嘉峪关市": "620200", "金昌市": "620300", "白银市": "620400",
    "天水市": "620500", "武威市": "620600", "张掖市": "620700", "平凉市": "620800",
    "陇南市": "621200",
    # 青海省
    "西宁市": "630100", "海东市": "630200",
    # 宁夏回族自治区
    "银川市": "640100", "石嘴山市": "640200", "吴忠市": "640300", "固原市": "640400",
    "中卫市": "640500",
    # 新疆维吾尔自治区
    "乌鲁木齐市": "650100",
}


@dataclass
class WaterQualityRecord:
    """水质数据记录"""
    device_id: str
    device_name: str
    location: str
    province: str
    river_basin: str
    water_quality: str  # 水质类别 Ⅰ-劣Ⅴ类
    timestamp: datetime
    temperature: Optional[float]  # 水温
    ph: Optional[float]
    dissolved_oxygen: Optional[float]  # 溶解氧
    conductivity: Optional[float]  # 电导率 μS/cm
    turbidity: Optional[float]  # 浊度 NTU
    permanganate: Optional[float]  # 高锰酸盐指数 mg/L
    ammonia_nitrogen: Optional[float]  # 氨氮 mg/L
    total_phosphorus: Optional[float]  # 总磷 mg/L
    total_nitrogen: Optional[float]  # 总氮 mg/L
    chlorophyll_a: Optional[float] = None  # 叶绿素a mg/L
    algae_density: Optional[float] = None  # 藻密度 cells/L


class NationalWaterDataAPI:
    """国家水质数据API客户端"""

    BASE_URL = "https://szzdjc.cnemc.cn:8070"
    API_URL = f"{BASE_URL}/GJZ/Ajax/Publish.ashx"

    # 表头索引（基于API返回的thead）
    HEADERS = [
        "省份", "流域", "断面名称", "监测时间", "水质类别",
        "水温", "pH", "溶解氧", "电导率", "浊度",
        "高锰酸盐指数", "氨氮", "总磷", "总氮", "叶绿素α", "藻密度"
    ]

    def __init__(self):
        self._cache: Dict[str, Any] = {"records": None, "fetched_at": None}
        self._cache_minutes = getattr(settings, "NATIONAL_WATER_DATA_CACHE_MINUTES", 20)

    def _cache_valid(self) -> bool:
        """检查缓存是否有效"""
        fetched_at = self._cache.get("fetched_at")
        if not fetched_at:
            return False
        return dj_timezone.now() - fetched_at < dj_timezone.timedelta(minutes=self._cache_minutes)

    def _fetch_data(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """发送请求获取数据 - 使用requests库（与原pc代码一致）"""
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            # 创建session以复用连接
            session = requests.Session()

            # 设置重试策略
            retry = Retry(total=3, backoff_factor=0.3)
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            # 禁用SSL警告
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            # 发送POST请求
            response = session.post(
                self.API_URL,
                data=params,
                timeout=30,
                verify=False,  # 忽略SSL证书验证
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.warning(f"国家水质数据获取失败: {e}")
            return None

    def _clean_value(self, value: Any, col_index: int = None) -> Any:
        """清理数据值"""
        if not value or value == "--":
            return None

        if isinstance(value, str):
            # 处理监测时间（第4列，索引3）- 添加年份
            if col_index == 3 and re.match(r'^\d{2}-\d{2}\s+\d{2}:\d{2}$', value):
                current_year = datetime.now().year
                return f"{current_year}-{value}"

            # 提取span标签中的值
            span_match = re.search(r"<span[^>]*title='([^']*)'[^>]*>(.*?)</span>", value)
            if span_match:
                return span_match.group(2).strip()

            # 去除HTML标签
            value = re.sub(r'<br/>.*', '', value)
            value = re.sub(r'<[^>]+>', '', value)
            value = value.strip()

            if not value or value == "--":
                return None

        return value

    def _parse_float(self, value: Any) -> Optional[float]:
        """解析浮点数"""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """解析日期时间"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value

        text = str(value).strip()
        if not text:
            return None

        # 尝试多种格式
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%m-%d %H:%M",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(text, fmt)
                # 如果没有年份，添加当前年份
                if fmt == "%m-%d %H:%M":
                    parsed = parsed.replace(year=datetime.now().year)
                # 添加时区
                return dj_timezone.make_aware(parsed)
            except ValueError:
                continue

        return None

    def _make_device_id(self, section_name: str, province: str) -> str:
        """生成设备ID"""
        seed = f"{province}_{section_name}"
        digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]
        return f"NW_{digest}"

    def _parse_record(self, row: List[Any]) -> Optional[WaterQualityRecord]:
        """解析单条记录"""
        if len(row) < 5:
            return None

        province = self._clean_value(row[0]) or "未知"
        river_basin = self._clean_value(row[1]) or "未知"
        section_name = self._clean_value(row[2])
        monitor_time = self._clean_value(row[3], col_index=3)
        water_quality = self._clean_value(row[4]) or ""

        if not section_name:
            return None

        timestamp = self._parse_datetime(monitor_time)
        if not timestamp:
            timestamp = dj_timezone.now()

        device_id = self._make_device_id(section_name, province)
        location = f"{province} - {river_basin}"

        # 解析监测数据（索引从5开始）
        temperature = self._parse_float(self._clean_value(row[5] if len(row) > 5 else None))
        ph = self._parse_float(self._clean_value(row[6] if len(row) > 6 else None))
        dissolved_oxygen = self._parse_float(self._clean_value(row[7] if len(row) > 7 else None))
        conductivity = self._parse_float(self._clean_value(row[8] if len(row) > 8 else None))
        turbidity = self._parse_float(self._clean_value(row[9] if len(row) > 9 else None))
        permanganate = self._parse_float(self._clean_value(row[10] if len(row) > 10 else None))
        ammonia_nitrogen = self._parse_float(self._clean_value(row[11] if len(row) > 11 else None))
        total_phosphorus = self._parse_float(self._clean_value(row[12] if len(row) > 12 else None))
        total_nitrogen = self._parse_float(self._clean_value(row[13] if len(row) > 13 else None))
        chlorophyll_a = self._parse_float(self._clean_value(row[14] if len(row) > 14 else None))
        algae_density = self._parse_float(self._clean_value(row[15] if len(row) > 15 else None))

        return WaterQualityRecord(
            device_id=device_id,
            device_name=section_name,
            location=location,
            province=province,
            river_basin=river_basin,
            water_quality=water_quality,
            timestamp=timestamp,
            temperature=temperature,
            ph=ph,
            dissolved_oxygen=dissolved_oxygen,
            conductivity=conductivity,
            turbidity=turbidity,
            permanganate=permanganate,
            ammonia_nitrogen=ammonia_nitrogen,
            total_phosphorus=total_phosphorus,
            total_nitrogen=total_nitrogen,
            chlorophyll_a=chlorophyll_a,
            algae_density=algae_density,
        )

    def fetch_records(
        self,
        area_id: str = "",
        river_id: str = "",
        search_name: str = "",
        city_name: str = "",
        force_refresh: bool = False,
        max_pages: int = 5
    ) -> List[WaterQualityRecord]:
        """获取水质数据记录

        注意：城市筛选通过 AreaID 参数实现
        - 省级代码：6位，后4位为0000，如 110000（北京市）
        - 市级代码：6位，后2位为00，如 440100（广州市）
        - 区县级代码：6位，如 110108（海淀区）
        """
        # 有筛选条件时禁用缓存
        has_filters = bool(area_id or river_id or search_name or city_name)

        # 检查缓存
        if not has_filters and not force_refresh and self._cache_valid():
            return self._cache.get("records", [])

        all_records = []

        for page in range(1, max_pages + 1):
            params = {
                "action": "getRealDatas",
                "AreaID": area_id,
                "RiverID": river_id,
                "MNName": search_name,
                "PageIndex": page,
                "PageSize": 60
            }

            # 城市筛选：使用城市代码作为 AreaID
            if city_name:
                city_code = CITY_CODES.get(city_name, "")
                if city_code:
                    # 直接使用城市代码作为 AreaID
                    params["AreaID"] = city_code
                    logger.info(f"城市筛选: {city_name} -> AreaID={city_code}")
                else:
                    # 如果找不到城市代码，尝试使用城市名作为断面搜索
                    if not search_name:
                        params["MNName"] = city_name
                    logger.warning(f"未找到城市代码: {city_name}，尝试断面名称搜索")

            data = self._fetch_data(params)
            if not data or not data.get("result"):
                if city_name and page == 1:
                    logger.warning(f"城市 '{city_name}' 没有获取到数据")
                break

            tbody = data.get("tbody", [])
            if not tbody:
                break

            for row in tbody:
                record = self._parse_record(row)
                if record:
                    all_records.append(record)

            total = data.get("total", 1)
            if page >= total:
                break

        # 只在无筛选条件时更新缓存
        if not has_filters:
            self._cache["records"] = all_records
            self._cache["fetched_at"] = dj_timezone.now()

        logger.info(f"获取国家水质数据成功，共 {len(all_records)} 条记录")
        return all_records


# 全局实例
_api_instance = NationalWaterDataAPI()


class NationalWaterDataService:
    """国家水质数据服务"""

    @staticmethod
    def api() -> NationalWaterDataAPI:
        """获取API实例"""
        return _api_instance

    @staticmethod
    def enabled() -> bool:
        """检查服务是否启用"""
        return getattr(settings, "NATIONAL_WATER_DATA_ENABLED", True)

    @staticmethod
    def get_devices(
        area_id: str = "",
        river_id: str = "",
        search_name: str = ""
    ) -> List[Dict[str, Any]]:
        """获取设备（断面）列表"""
        if not NationalWaterDataService.enabled():
            return []

        records = _api_instance.fetch_records(
            area_id=area_id,
            river_id=river_id,
            search_name=search_name,
            max_pages=3
        )

        devices: Dict[str, Dict[str, Any]] = {}
        for record in records:
            if record.device_id not in devices:
                devices[record.device_id] = {
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "device_type": "sensor",
                    "status": "online",
                    "location": record.location,
                    "province": record.province,
                    "river_basin": record.river_basin,
                }

        return list(devices.values())

    @staticmethod
    def get_realtime(count: int = 10, **filters) -> Dict[str, Any]:
        """获取实时数据"""
        if not NationalWaterDataService.enabled():
            return {"timestamp": dj_timezone.now().isoformat(), "sensors": []}

        area_id = filters.get("area_id", "")
        river_id = filters.get("river_id", "")
        search_name = filters.get("search_name", "")
        city_name = filters.get("city_name", "")
        force_refresh = bool(filters.get("force_refresh", False))
        max_pages = int(filters.get("max_pages", 200))

        # 有筛选条件时获取更多页数（由 max_pages 控制上限）
        has_filters = bool(area_id or river_id or search_name or city_name)
        if has_filters and not filters.get("max_pages"):
            max_pages = 200

        records = _api_instance.fetch_records(
            area_id=area_id,
            river_id=river_id,
            search_name=search_name,
            city_name=city_name,  # 传递城市参数给 API
            force_refresh=force_refresh,
            max_pages=max_pages
        )

        if not records:
            return {"timestamp": dj_timezone.now().isoformat(), "sensors": []}

        # 按设备分组，取最新数据
        latest_by_device: Dict[str, WaterQualityRecord] = {}
        for record in records:
            current = latest_by_device.get(record.device_id)
            if not current or record.timestamp > current.timestamp:
                latest_by_device[record.device_id] = record

        latest_records = sorted(
            latest_by_device.values(),
            key=lambda r: r.timestamp,
            reverse=True
        )[:count]

        sensors = []
        for record in latest_records:
            city = DataTransformer.extract_city_from_name(record.device_name, record.province)
            sensors.append({
                "device_id": record.device_id,
                "device_name": record.device_name,
                "location": record.location,
                "province": record.province,
                "city": city,
                "river_basin": record.river_basin,
                "water_quality": record.water_quality,
                "temperature": record.temperature,
                "ph": record.ph,
                "dissolved_oxygen": record.dissolved_oxygen,
                "conductivity": record.conductivity,
                "turbidity": record.turbidity,
                "permanganate": record.permanganate,
                "ammonia_nitrogen": record.ammonia_nitrogen,
                "total_phosphorus": record.total_phosphorus,
                "total_nitrogen": record.total_nitrogen,
                "chlorophyll_a": record.chlorophyll_a,
                "algae_density": record.algae_density,
                "timestamp": record.timestamp.isoformat(),
            })

        return {
            "timestamp": dj_timezone.now().isoformat(),
            "sensors": sensors,
            "total": len(latest_by_device)
        }

    @staticmethod
    def get_history(device_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """获取历史数据"""
        if not NationalWaterDataService.enabled():
            return []

        records = _api_instance.fetch_records(max_pages=10)

        # 筛选指定设备的数据
        filtered = []
        for record in records:
            if record.device_id != device_id:
                continue

            # 时间筛选
            threshold = dj_timezone.now() - dj_timezone.timedelta(hours=hours)
            if record.timestamp and record.timestamp < threshold:
                continue

            filtered.append(record)

        filtered.sort(key=lambda r: r.timestamp)

        # 格式化时间标签
        def _format_time_label(ts: datetime) -> str:
            if hours <= 24:
                return ts.strftime("%H:%M")
            return ts.strftime("%m-%d")

        return [
            {
                "time": _format_time_label(record.timestamp),
                "timestamp": record.timestamp.isoformat(),
                "temperature": record.temperature,
                "ph": record.ph,
                "dissolved_oxygen": record.dissolved_oxygen,
                "conductivity": record.conductivity,
                "turbidity": record.turbidity,
                "permanganate": record.permanganate,
                "ammonia_nitrogen": record.ammonia_nitrogen,
                "total_phosphorus": record.total_phosphorus,
                "total_nitrogen": record.total_nitrogen,
                "chlorophyll_a": record.chlorophyll_a,
                "algae_density": record.algae_density,
            }
            for record in filtered
        ]

    @staticmethod
    def get_alerts(count: int = 10) -> List[Dict[str, Any]]:
        """获取告警数据"""
        if not NationalWaterDataService.enabled():
            return []

        records = _api_instance.fetch_records(max_pages=5)
        alerts = []

        for record in records:
            # 水质类别告警
            if record.water_quality in ["Ⅳ", "Ⅴ", "劣Ⅴ"]:
                alerts.append({
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "type": "water_quality",
                    "level": "warning" if record.water_quality in ["Ⅳ", "Ⅴ"] else "critical",
                    "message": f"水质{record.water_quality}类",
                    "value": record.water_quality,
                    "timestamp": record.timestamp.isoformat(),
                })

            # 温度告警
            if record.temperature is not None and record.temperature > 30:
                alerts.append({
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "type": "temperature",
                    "level": "warning",
                    "message": "水温偏高",
                    "value": record.temperature,
                    "timestamp": record.timestamp.isoformat(),
                })

            # 溶解氧告警
            if record.dissolved_oxygen is not None and record.dissolved_oxygen < 5:
                alerts.append({
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "type": "dissolved_oxygen",
                    "level": "warning",
                    "message": "溶解氧偏低",
                    "value": record.dissolved_oxygen,
                    "timestamp": record.timestamp.isoformat(),
                })

            # pH告警
            if record.ph is not None and (record.ph < 6.5 or record.ph > 8.5):
                alerts.append({
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "type": "ph",
                    "level": "warning",
                    "message": "pH异常",
                    "value": record.ph,
                    "timestamp": record.timestamp.isoformat(),
                })

            if len(alerts) >= count:
                break

        return alerts[:count]

    @staticmethod
    def get_areas() -> List[Dict[str, Any]]:
        """获取区域列表"""
        return [
            {"code": code, "name": name}
            for name, code in AREA_CODES.items()
        ]

    @staticmethod
    def get_rivers() -> List[Dict[str, Any]]:
        """获取流域列表"""
        return [
            {"code": code, "name": name}
            for name, code in RIVER_CODES.items()
        ]
