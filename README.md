# 智慧渔业水质监控系统

基于 Django + Vue 3 + ECharts 的水质监测数据可视化平台

## 项目结构

```
D:\hzf\
├── backend/                    # Django后端
│   ├── aquaculture/           # 项目配置
│   ├── apps/                   # 业务应用
│   │   ├── sensors/           # 传感器管理
│   │   ├── alerts/            # 预警系统
│   │   ├── devices/           # 设备管理
│   │   └── dashboard/         # 数据看板
│   ├── core/                   # 核心模块
│   │   └── data_generator.py  # 假数据生成器
│   ├── manage.py              # Django管理脚本
│   ├── init_database.sql      # 数据库初始化脚本
│   └── requirements.txt       # Python依赖
│
└── frontend/                   # Vue3前端
    ├── src/
    │   ├── views/             # 页面组件
    │   ├── api/               # API接口
    │   ├── router/            # 路由配置
    │   └── styles/            # 全局样式
    ├── package.json           # Node依赖
    └── vite.config.js         # Vite配置
```

## 快速开始

### 1. 数据库初始化

连接到MySQL数据库并执行初始化脚本：

```bash
mysql -h 47.93.141.103 -P 3306 -u hzf -phzf123123 < backend/init_database.sql
```

或使用MySQL客户端执行 `backend/init_database.sql` 中的SQL语句。

### 2. 后端启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动Django服务
python manage.py runserver
```

后端将运行在 http://localhost:8000

### 3. 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将运行在 http://localhost:5173

## 功能特性

### 已实现功能

✅ **实时监控** - 传感器数据实时展示
✅ **数据分析** - 历史数据趋势图表
✅ **预警中心** - 告警信息管理
✅ **设备管理** - 设备列表和状态查看

### 技术特点

- 蓝白色配色方案
- iOS风格玻璃态组件
- 网格背景动画
- ECharts数据可视化
- 假数据生成器（无需真实传感器）
- 响应式设计

## API接口

### 实时数据
```
GET /api/v1/sensors/data/realtime/
```

### 历史数据
```
GET /api/v1/sensors/data/history/?device_id=sensor_001&hours=24
```

### 告警列表
```
GET /api/v1/alerts/list_fake/?count=10
```

### 设备列表
```
GET /api/v1/devices/
```

### 看板概览
```
GET /api/v1/dashboard/overview/
```

## 数据库配置

数据库信息已在 `backend/aquaculture/settings.py` 中配置：

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'aquaculture',
        'HOST': '47.93.141.103',
        'PORT': '3306',
        'USER': 'hzf',
        'PASSWORD': 'hzf123123',
    }
}
```

## 开发说明

### 假数据生成器

位置: `backend/core/data_generator.py`

生成器类 `SensorDataGenerator` 提供以下方法：

- `generate_sensor_data()` - 生成单条传感器数据
- `generate_historical_data(hours)` - 生成历史数据
- `generate_multi_sensors_realtime(count)` - 生成多个传感器实时数据
- `generate_alert()` - 生成告警数据
- `generate_device_list()` - 生成设备列表

### 样式定制

全局样式变量: `frontend/src/styles/variables.scss`

主题色采用蓝白色系，所有组件使用iOS风格的毛玻璃效果。

## 常见问题

### 1. 数据库连接失败
- 确认MySQL服务正在运行
- 检查数据库配置信息是否正确
- 确认数据库用户有足够权限

### 2. 前端无法访问后端API
- 确认后端服务已启动 (http://localhost:8000)
- 检查Vite代理配置是否正确

### 3. 安装依赖失败
- 后端: 使用国内镜像源 `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt`
- 前端: 使用国内镜像源 `npm install --registry=https://registry.npmmirror.com`

## 后续扩展

- [ ] 接入真实MQTT传感器数据
- [ ] 实现WebSocket实时推送
- [ ] 添加数据导出功能
- [ ] 移动端适配
- [ ] 用户权限管理

## 许可证

MIT License
