"""
国家水质自动综合监管平台 - API直接调用版本
直接调用API获取数据，无需浏览器
"""

import json
import csv
import requests
from datetime import datetime
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class WaterDataAPI:
    """水质数据API客户端"""

    def __init__(self):
        self.base_url = "https://szzdjc.cnemc.cn:8070"
        self.api_url = f"{self.base_url}/GJZ/Ajax/Publish.ashx"
        self.session = requests.Session()
        self.session.verify = False  # 忽略SSL证书验证

    def get_real_data(self, area_id="", river_id="", mn_name="", page_index=1, page_size=60):
        """
        获取实时水质数据

        参数:
            area_id: 区域ID (空字符串为全国, 如 "440100" 为广州市)
            river_id: 流域ID (空为所有流域)
            mn_name: 断面名称搜索关键词
            page_index: 页码 (从1开始)
            page_size: 每页数量 (建议60)

        返回:
            dict: API响应数据
        """
        params = {
            "action": "getRealDatas",
            "AreaID": area_id,
            "RiverID": river_id,
            "MNName": mn_name,
            "PageIndex": page_index,
            "PageSize": page_size
        }

        try:
            response = self.session.post(self.api_url, data=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return None

    def get_all_data(self, area_id="", river_id="", max_pages=10):
        """
        获取所有数据（自动翻页）

        参数:
            area_id: 区域ID
            river_id: 流域ID
            max_pages: 最大页数限制

        返回:
            list: 所有数据记录
        """
        all_data = []
        page_index = 1

        while page_index <= max_pages:
            print(f"正在获取第 {page_index} 页...")
            data = self.get_real_data(
                area_id=area_id,
                river_id=river_id,
                page_index=page_index,
                page_size=60
            )

            if not data or not data.get("result"):
                break

            tbody = data.get("tbody", [])
            if not tbody:
                break

            all_data.extend(tbody)
            print(f"  获取到 {len(tbody)} 条记录")

            # 检查是否还有下一页
            total = data.get("total", 1)
            if page_index >= total:
                break

            page_index += 1

        return all_data, data.get("thead", [])

    def clean_value(self, value, col_index=None):
        """清理数据值，去除HTML标签和多余字符"""
        import re
        if not value or value == "--":
            return ""

        # 如果是字符串，去除HTML标签
        if isinstance(value, str):
            # 处理监测时间（第4列，索引3）- 添加年份
            if col_index == 3 and re.match(r'^\d{2}-\d{2}\s+\d{2}:\d{2}$', value):
                current_year = datetime.now().year
                return f"{current_year}-{value}"

            # 提取span标签中的title值（原始值）或直接获取文本
            span_match = re.search(r"<span[^>]*title='([^']*)'[^>]*>(.*?)</span>", value)
            if span_match:
                # 返回显示值（更简洁）
                return span_match.group(2).strip()
            # 去除其他HTML标签
            value = re.sub(r'<br/>.*', '', value)  # 去除<br/>及后面的单位
            value = re.sub(r'<[^>]+>', '', value)  # 去除所有HTML标签
            return value.strip()

        return str(value)

    def save_to_csv(self, data, headers, filename=None):
        """
        保存数据到CSV文件

        参数:
            data: 数据列表（list of list）
            headers: 表头列表
            filename: 文件名（可选）
        """
        import re
        if not filename:
            filename = f'water_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

        # 清理表头（去除HTML标签）
        clean_headers = []
        for h in headers:
            # 去除<br/>及后面的单位说明
            h_clean = re.sub(r'<br/>.*', '', h)
            clean_headers.append(h_clean)

        # 清理数据
        rows = []
        for row in data:
            clean_row = [self.clean_value(cell, i) for i, cell in enumerate(row)]
            rows.append(clean_row)

        # 保存CSV
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(clean_headers)
            writer.writerows(rows)

        print(f"数据已保存到: {filename}")
        return filename

    def save_to_json(self, data, filename=None):
        """保存数据到JSON文件"""
        if not filename:
            filename = f'water_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"数据已保存到: {filename}")
        return filename


# 常用区域ID
AREA_CODES = {
    "全国": "",
    "北京市": "110000",
    "上海市": "310000",
    "广州市": "440100",
    "深圳市": "440300",
    "杭州市": "330100",
    "南京市": "320100",
    "成都市": "510100",
    "武汉市": "420100",
    "西安市": "610100",
}

# 常用流域ID
RIVER_CODES = {
    "所有流域": "",
    "长江流域": "1100000000",
    "黄河流域": "0900000000",
    "珠江流域": "1500000000",
    "松花江流域": "0200000000",
    "淮河流域": "1000000000",
    "海河流域": "6010000000",
    "辽河流域": "0500000000",
}


def main():
    """主函数"""
    print("="*50)
    print("国家水质自动综合监管平台 - API调用工具")
    print("="*50)

    api = WaterDataAPI()

    # 示例1: 获取全国数据（第一页）
    print("\n【示例1】获取全国数据（第一页）")
    data = api.get_real_data(page_index=1, page_size=10)
    if data:
        print(f"获取成功！共 {len(data.get('tbody', []))} 条记录")
        print(f"总页数: {data.get('total', 0)}")

        # 保存为JSON
        api.save_to_json(data, "sample_data.json")

        # 保存为CSV
        thead = data.get("thead", [])
        tbody = data.get("tbody", [])
        api.save_to_csv(tbody, thead, "sample_data.csv")

    # 示例2: 获取广州市数据
    print("\n【示例2】获取广州市数据")
    guangzhou_data, headers = api.get_all_data(area_id="440100", max_pages=3)
    if guangzhou_data:
        print(f"共获取 {len(guangzhou_data)} 条记录")
        api.save_to_csv(guangzhou_data, headers, "guangzhou_data.csv")

    # 示例3: 按断面名称搜索
    print("\n【示例3】搜索包含'长江'的断面")
    search_data = api.get_real_data(mn_name="长江", page_size=20)
    if search_data:
        print(f"找到 {len(search_data.get('tbody', []))} 条记录")
        thead = search_data.get("thead", [])
        tbody = search_data.get("tbody", [])
        api.save_to_csv(tbody, thead, "yangtze_data.csv")

    print("\n" + "="*50)
    print("数据获取完成！")
    print("="*50)


if __name__ == '__main__':
    main()
