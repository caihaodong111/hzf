<template>
  <div class="dashboard-container">
    <!-- 动态背景 -->
    <div class="animated-grid-bg"></div>

    <!-- 顶部导航栏 -->
    <header class="glass-nav">
      <div class="nav-content">
        <div class="logo">智慧渔业监控平台</div>
        <nav class="nav-menu">
          <router-link to="/" class="nav-item active">实时监控</router-link>
          <router-link to="/analysis" class="nav-item">数据分析</router-link>
          <router-link to="/devices" class="nav-item">设备管理</router-link>
          <router-link to="/alerts" class="nav-item">预警中心</router-link>
        </nav>
        <div class="user-profile">
          <el-avatar :size="36">管</el-avatar>
          <span class="username">管理员</span>
          <el-button type="danger" size="small" text @click="handleLogout">退出</el-button>
        </div>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 传感器数据卡片 -->
      <div class="sensor-grid">
        <div
          class="sensor-card glass-card"
          v-for="sensor in sensors"
          :key="sensor.device_id"
        >
          <div class="sensor-icon" :style="{ background: getSensorColor(sensor.device_id) }">
            <el-icon><icon-monitor /></el-icon>
          </div>
          <div class="sensor-info">
            <div class="sensor-label">{{ sensor.location }}</div>
            <div class="sensor-value">{{ sensor.temperature }}℃</div>
            <div class="sensor-details">
              <span>DO: {{ sensor.dissolved_oxygen }}mg/L</span>
              <span>pH: {{ sensor.ph }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 图表区域 -->
      <div class="charts-container">
        <div class="chart-card glass-card">
          <div class="chart-header">
            <h3>24小时水质趋势</h3>
            <el-radio-group v-model="chartType" size="small" @change="updateChart">
              <el-radio-button label="temperature">温度</el-radio-button>
              <el-radio-button label="dissolved_oxygen">溶解氧</el-radio-button>
              <el-radio-button label="ph">pH值</el-radio-button>
            </el-radio-group>
          </div>
          <div ref="trendChart" class="chart-box"></div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getRealtimeData, getHistoricalData } from '@/api/sensors'
import { ElMessage } from 'element-plus'

const router = useRouter()
const sensors = ref([])
const trendChart = ref(null)
const chartType = ref('temperature')
let chartInstance = null
let refreshTimer = null

// 传感器颜色配置
const sensorColors = [
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)'
]

const getSensorColor = (deviceId) => {
  const index = parseInt(deviceId.split('_')[1]) - 1
  return sensorColors[index % sensorColors.length]
}

// 加载实时数据
const loadRealtimeData = async () => {
  try {
    const res = await getRealtimeData()
    if (res.code === 200) {
      sensors.value = res.data.sensors
    }
  } catch (error) {
    console.error('加载实时数据失败:', error)
  }
}

// 加载历史数据并更新图表
const loadHistoricalData = async () => {
  try {
    const res = await getHistoricalData('sensor_001', 24)
    if (res.code === 200) {
      updateChartWithData(res.data.data)
    }
  } catch (error) {
    console.error('加载历史数据失败:', error)
  }
}

// 初始化图表
const initChart = () => {
  if (!trendChart.value) return

  chartInstance = echarts.init(trendChart.value)
  loadHistoricalData()

  // 响应式
  window.addEventListener('resize', () => {
    chartInstance?.resize()
  })
}

// 使用数据更新图表
const updateChartWithData = (data) => {
  if (!chartInstance) return

  const times = data.map(item => item.time)
  let values, name, color

  switch (chartType.value) {
    case 'temperature':
      values = data.map(item => item.temperature)
      name = '温度'
      color = '#667eea'
      break
    case 'dissolved_oxygen':
      values = data.map(item => item.dissolved_oxygen)
      name = '溶解氧'
      color = '#4facfe'
      break
    case 'ph':
      values = data.map(item => item.ph)
      name = 'pH值'
      color = '#43e97b'
      break
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      borderColor: 'rgba(24, 144, 255, 0.2)',
      textStyle: { color: '#1F2937' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: times,
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(24, 144, 255, 0.2)' } },
      axisLabel: { color: '#6B7280' }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#6B7280' },
      splitLine: { lineStyle: { color: 'rgba(24, 144, 255, 0.05)' } }
    },
    series: [{
      name: name,
      type: 'line',
      data: values,
      smooth: true,
      lineStyle: { color: color, width: 3 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: color + '40' },
          { offset: 1, color: color + '05' }
        ])
      },
      itemStyle: { color: color }
    }]
  }

  chartInstance.setOption(option)
}

// 切换图表类型
const updateChart = () => {
  loadHistoricalData()
}

// 退出登录
const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.push('/login')
}

onMounted(() => {
  loadRealtimeData()
  initChart()

  // 定时刷新数据（每30秒）
  refreshTimer = setInterval(() => {
    loadRealtimeData()
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  if (chartInstance) {
    chartInstance.dispose()
  }
  window.removeEventListener('resize', () => {})
})
</script>

<style scoped lang="scss">
.dashboard-container {
  min-height: 100vh;
  position: relative;
}

.nav-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  height: 64px;
}

.logo {
  font-size: 20px;
  font-weight: 600;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.nav-menu {
  display: flex;
  gap: 8px;
}

.nav-item {
  padding: 8px 16px;
  border-radius: 8px;
  color: #6B7280;
  text-decoration: none;
  transition: all 0.3s ease;

  &:hover {
    color: #1890FF;
    background: rgba(24, 144, 255, 0.1);
  }

  &.active {
    color: #1890FF;
    background: rgba(24, 144, 255, 0.15);
  }
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  font-size: 14px;
  color: #1F2937;
}

.main-content {
  padding: 24px 32px;
}

.sensor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.sensor-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
  margin-bottom: 12px;
}

.sensor-info {
  position: relative;
  z-index: 1;
}

.sensor-label {
  font-size: 14px;
  color: #6B7280;
  margin-bottom: 8px;
}

.sensor-value {
  font-size: 32px;
  font-weight: 600;
  color: #1F2937;
  margin-bottom: 8px;
}

.sensor-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #6B7280;
}

.charts-container {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
}

.chart-card {
  padding: 24px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;

  h3 {
    font-size: 18px;
    font-weight: 600;
    color: #1F2937;
    margin: 0;
  }
}

.chart-box {
  width: 100%;
  height: 400px;
}

@media (max-width: 768px) {
  .nav-content {
    padding: 0 16px;
  }

  .main-content {
    padding: 16px;
  }

  .sensor-grid {
    grid-template-columns: 1fr;
  }

  .nav-menu {
    display: none;
  }
}
</style>
