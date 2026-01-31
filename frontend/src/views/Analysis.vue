<template>
  <div class="analysis-container">
    <div class="animated-grid-bg"></div>

    <!-- 导航栏 -->
    <header class="glass-nav">
      <div class="nav-content">
        <div class="logo">智慧渔业监控平台</div>
        <nav class="nav-menu">
          <router-link to="/" class="nav-item">实时监控</router-link>
          <router-link to="/analysis" class="nav-item active">数据分析</router-link>
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

    <!-- 主内容 -->
    <main class="main-content">
      <div class="page-header">
        <h2>数据分析</h2>
        <p>查看历史水质数据趋势和统计分析</p>
      </div>

      <!-- 筛选条件 -->
      <div class="filter-card glass-card">
        <el-form :inline="true">
          <el-form-item label="设备:">
            <el-select v-model="selectedDevice" placeholder="选择设备" style="width: 200px">
              <el-option
                v-for="item in devices"
                :key="item.device_id"
                :label="item.device_name"
                :value="item.device_id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="时间范围:">
            <el-select v-model="timeRange" placeholder="选择时间范围" style="width: 150px" @change="loadData">
              <el-option label="最近24小时" :value="24" />
              <el-option label="最近7天" :value="168" />
              <el-option label="最近30天" :value="720" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadData">查询</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 图表网格 -->
      <div class="charts-grid">
        <div class="chart-card glass-card">
          <h3>温度变化趋势</h3>
          <div ref="tempChartRef" class="chart-box"></div>
        </div>
        <div class="chart-card glass-card">
          <h3>溶解氧变化趋势</h3>
          <div ref="doChartRef" class="chart-box"></div>
        </div>
        <div class="chart-card glass-card">
          <h3>pH值变化趋势</h3>
          <div ref="phChartRef" class="chart-box"></div>
        </div>
        <div class="chart-card glass-card">
          <h3>盐度变化趋势</h3>
          <div ref="salinityChartRef" class="chart-box"></div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getHistoricalData } from '@/api/sensors'
import { getDeviceList } from '@/api/sensors'

const router = useRouter()
const selectedDevice = ref('sensor_001')
const timeRange = ref(24)
const devices = ref([])

// 模板引用
const tempChartRef = ref(null)
const doChartRef = ref(null)
const phChartRef = ref(null)
const salinityChartRef = ref(null)

// 图表实例
let tempChart = null
let doChart = null
let phChart = null
let salinityChart = null

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}

const loadDevices = async () => {
  try {
    const res = await getDeviceList()
    console.log('设备列表响应:', res)
    if (res.code === 200) {
      devices.value = res.data.devices
      console.log('设备列表:', devices.value)
    }
  } catch (error) {
    console.error('加载设备列表失败:', error)
  }
}

const loadData = async () => {
  try {
    console.log('加载数据, 设备ID:', selectedDevice.value, '时间范围:', timeRange.value)
    const res = await getHistoricalData(selectedDevice.value, timeRange.value)
    console.log('历史数据响应:', res)
    if (res.code === 200) {
      updateCharts(res.data.data)
    }
  } catch (error) {
    console.error('加载数据失败:', error)
  }
}

const initCharts = () => {
  tempChart = echarts.init(tempChartRef.value)
  doChart = echarts.init(doChartRef.value)
  phChart = echarts.init(phChartRef.value)
  salinityChart = echarts.init(salinityChartRef.value)

  loadData()

  window.addEventListener('resize', () => {
    tempChart?.resize()
    doChart?.resize()
    phChart?.resize()
    salinityChart?.resize()
  })
}

const updateCharts = (data) => {
  const times = data.map(item => item.time)
  const commonOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: times, boundaryGap: false },
    yAxis: { type: 'value' }
  }

  tempChart.setOption({
    ...commonOption,
    series: [{
      name: '温度',
      type: 'line',
      data: data.map(item => item.temperature),
      smooth: true,
      lineStyle: { color: '#667eea', width: 3 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(102, 126, 234, 0.3)' },
          { offset: 1, color: 'rgba(102, 126, 234, 0.05)' }
        ])
      }
    }]
  })

  doChart.setOption({
    ...commonOption,
    series: [{
      name: '溶解氧',
      type: 'line',
      data: data.map(item => item.dissolved_oxygen),
      smooth: true,
      lineStyle: { color: '#4facfe', width: 3 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(79, 172, 254, 0.3)' },
          { offset: 1, color: 'rgba(79, 172, 254, 0.05)' }
        ])
      }
    }]
  })

  phChart.setOption({
    ...commonOption,
    series: [{
      name: 'pH值',
      type: 'line',
      data: data.map(item => item.ph),
      smooth: true,
      lineStyle: { color: '#43e97b', width: 3 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(67, 233, 123, 0.3)' },
          { offset: 1, color: 'rgba(67, 233, 123, 0.05)' }
        ])
      }
    }]
  })

  salinityChart.setOption({
    ...commonOption,
    series: [{
      name: '盐度',
      type: 'line',
      data: data.map(item => item.salinity),
      smooth: true,
      lineStyle: { color: '#fa709a', width: 3 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(250, 112, 154, 0.3)' },
          { offset: 1, color: 'rgba(250, 112, 154, 0.05)' }
        ])
      }
    }]
  })
}

onMounted(() => {
  loadDevices()
  initCharts()
})

onUnmounted(() => {
  tempChart?.dispose()
  doChart?.dispose()
  phChart?.dispose()
  salinityChart?.dispose()
  window.removeEventListener('resize', () => {})
})
</script>

<style scoped lang="scss">
.analysis-container {
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

.page-header {
  margin-bottom: 24px;

  h2 {
    font-size: 28px;
    font-weight: 600;
    color: #1F2937;
    margin-bottom: 8px;
  }

  p {
    font-size: 14px;
    color: #6B7280;
  }
}

.filter-card {
  padding: 20px 24px;
  margin-bottom: 24px;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
}

.chart-card {
  padding: 24px;

  h3 {
    font-size: 16px;
    font-weight: 600;
    color: #1F2937;
    margin-bottom: 16px;
  }
}

.chart-box {
  width: 100%;
  height: 300px;
}

@media (max-width: 1024px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
