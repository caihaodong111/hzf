# 国家水质自动综合监管平台数据获取工具

直接调用API获取全国水质监测数据，无需浏览器。

## 快速开始

### 方式一：GUI图形界面（推荐）

```bash
python water_data_gui.py
```

### 方式二：命令行脚本

```bash
python water_data_simple.py
```

## 使用方式

### GUI界面功能

- **区域选择**: 下拉菜单选择全国/各省市
- **流域选择**: 下拉菜单选择各流域
- **断面搜索**: 输入关键词搜索特定断面
- **分页设置**: 自定义每页数量和最大页数
- **数据预览**: 表格实时显示爬取结果
- **导出功能**: 支持CSV和JSON格式导出

## API信息

- **接口地址**: `https://szzdjc.cnemc.cn:8070/GJZ/Ajax/Publish.ashx`
- **请求方法**: POST
- **数据来源**: 中国环境监测总站

## 安装

```bash
pip install requests
```

## 使用示例

```python
from water_data_simple import WaterDataAPI

api = WaterDataAPI()

# 获取全国数据（第一页）
data = api.get_real_data(page_size=60)

# 获取指定区域数据
data = api.get_real_data(area_id="440100")  # 广州市

# 获取指定流域数据
data = api.get_real_data(river_id="1100000000")  # 长江流域

# 搜索断面名称
data = api.get_real_data(mn_name="长江")

# 获取所有页数据
all_data, headers = api.get_all_data(area_id="440100")

# 保存为CSV
api.save_to_csv(all_data, headers, "output.csv")
```

## 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `AreaID` | 区域ID（空为全国） | `"440100"`=广州市 |
| `RiverID` | 流域ID（空为所有） | `"1100000000"`=长江 |
| `MNName` | 断面名称搜索 | `"长江"` |
| `PageIndex` | 页码（从1开始） | `1` |
| `PageSize` | 每页数量 | `60` |

## 常用区域ID

```
全国: (空)
北京市: 110000
上海市: 310000
广州市: 440100
深圳市: 440300
```

## 常用流域ID

```
长江流域: 1100000000
黄河流域: 0900000000
珠江流域: 1500000000
```

## 数据字段

| 字段 | 说明 |
|------|------|
| 省份 | 监测站点所在省份 |
| 流域 | 所属流域 |
| 断面名称 | 监测断面名称 |
| 监测时间 | 数据采集时间 |
| 水质类别 | Ⅰ-劣Ⅴ类 |
| 水温 | 水温度数(℃) |
| pH | 酸碱度(无量纲) |
| 溶解氧 | mg/L |
| 电导率 | μS/cm |
| 浊度 | NTU |
| 高锰酸盐指数 | mg/L |
| 氨氮 | mg/L |
| 总磷 | mg/L |
| 总氮 | mg/L |
