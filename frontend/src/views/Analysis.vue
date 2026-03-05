<template>
  <div class="analysis-container">
    <header class="dashboard-header">
      <div class="header-content">
        <div class="brand">
          <h1>水质综合分析 <span class="badge">{{ dataSourceLabel }}</span></h1>
          <p class="timestamp">数据更新于: {{ lastUpdateText }}</p>
        </div>
        <div class="header-actions">
          <el-select v-model="timeRange" class="styled-select" @change="loadData">
            <el-option label="最近24小时" :value="24" />
            <el-option label="最近7天" :value="168" />
            <el-option label="最近30天" :value="720" />
          </el-select>
          <button class="icon-btn" @click="loadData" :disabled="loading">
            <el-icon :class="{ spinning: loading }"><Refresh /></el-icon>
          </button>
        </div>
      </div>
    </header>

    <main class="analysis-layout">
      <section class="rail">
        <div class="kpi-stack">
          <div class="kpi-card glass-card">
            <div class="kpi-info">
              <span class="label">水质综合指数</span>
              <span class="value">{{ qualityIndex }}</span>
            </div>
            <div ref="indexChartRef" class="mini-chart"></div>
          </div>
          <div class="kpi-mini-grid">
            <div class="mini-card glass-card">
              <span class="label">在线站点</span>
              <span class="value">{{ overview.online_devices || onlineCount }}</span>
              <span class="sub">总数 {{ sensors.length }}</span>
            </div>
            <div class="mini-card glass-card">
              <span class="label">告警数量</span>
              <span class="value danger">{{ overview.alert_count || 0 }}</span>
              <span class="sub">近 {{ timeRange }}h</span>
            </div>
          </div>
          <div class="metrics-card glass-card">
            <div class="card-header">核心指标均值</div>
            <div class="metric-item">
              <span>水温</span>
              <div class="bar-bg">
                <div class="bar-fill" :style="{ width: (avgMetrics.temperature / 40) * 100 + '%' }"></div>
              </div>
              <span class="num">{{ avgMetrics.temperature }}°C</span>
            </div>
            <div class="metric-item">
              <span>溶解氧</span>
              <div class="bar-bg">
                <div class="bar-fill oxygen" :style="{ width: (avgMetrics.dissolved_oxygen / 15) * 100 + '%' }"></div>
              </div>
              <span class="num">{{ avgMetrics.dissolved_oxygen }}</span>
            </div>
            <div class="metric-item">
              <span>pH值</span>
              <div class="bar-bg">
                <div class="bar-fill ph" :style="{ width: (avgMetrics.ph / 14) * 100 + '%' }"></div>
              </div>
              <span class="num">{{ avgMetrics.ph }}</span>
            </div>
          </div>
        </div>

        <section class="risk-section glass-card">
          <div class="card-header-flex">
            <div class="title-group">
              <h3>风险站点</h3>
              <span class="subtitle">共 {{ riskTable.length }} 个</span>
            </div>
            <el-tag type="danger" effect="dark" round>高风险优先</el-tag>
          </div>
          <el-table :data="riskTable" style="width: 100%" height="320" class="custom-table compact">
            <el-table-column prop="station_name" label="站点" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="risk-name">{{ row.station_name || '-' }}</div>
                <div class="risk-meta">
                  DO {{ row.dissolved_oxygen ?? '-' }} · pH {{ row.ph ?? '-' }}
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="water_quality" label="水质" width="72">
              <template #default="{ row }">
                <span class="quality-dot" :style="{ background: qualityColors[row.water_quality] }"></span>
                {{ row.water_quality || '未知' }}
              </template>
            </el-table-column>
            <el-table-column prop="risk_score" label="风险" width="68" align="center" sortable>
              <template #default="{ row }">
                <span :class="['score-tag', row.risk_tag]">{{ row.risk_score }}</span>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </section>

      <section class="canvas">
        <section class="trend-section glass-card">
          <div class="card-header-flex">
            <div class="title-info">
              <h3>关键指标趋势</h3>
              <span class="subtitle">当前站点: {{ trendDeviceName }}</span>
            </div>
            <div class="card-search">
              <el-input
                v-model="trendSearch"
                placeholder="搜索站点..."
                :prefix-icon="Search"
                @keyup.enter="applyTrendSearch"
                size="small"
              />
            </div>
          </div>
          <div ref="trendChartRef" class="chart-box trend-chart"></div>
        </section>

        <section class="charts-row">
          <section class="chart-secondary glass-card quality-chart">
            <div class="card-title">水质类别占比</div>
            <div ref="qualityChartRef" class="chart-box"></div>
          </section>

          <section class="chart-secondary glass-card province-chart">
            <div class="card-title">省内站点 Top 10</div>
            <div ref="provinceChartRef" class="chart-box"></div>
          </section>
        </section>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getDashboardOverview, getRealtimeData, getHistoricalData } from '@/api/sensors'
import { getDataSourceSettings } from '@/api/settings'
import sensorStore from '@/stores/sensorStore'
import { Refresh, Search } from '@element-plus/icons-vue'

const timeRange = ref(24)
const loading = ref(false)
const overview = ref({})
const dataSourceMode = ref('auto')
const sensors = ref([])
const dataSource = ref('-')
const lastUpdate = ref('')
const trendDeviceId = ref('')
const trendHistory = ref([])
const trendSearch = ref('')

const dataSourceLabel = computed(() => {
  const map = { national: '国家水质', open: '开放数据', simulator: '模拟数据', database: '数据库' }
  return map[dataSource.value] || '未知'
})

const lastUpdateText = computed(() => {
  if (!lastUpdate.value) return '-'
  try {
    return new Date(lastUpdate.value).toLocaleString('zh-CN')
  } catch (error) {
    return lastUpdate.value
  }
})

const trendDeviceName = computed(() => {
  const target = sensors.value.find(s => s.station_id === trendDeviceId.value)
  return target?.station_name || target?.station_id || '未选择'
})

const onlineCount = computed(() => sensors.value.filter(s => s.status === 'online').length)

const avgMetrics = computed(() => {
  const averages = { temperature: 0, ph: 0, dissolved_oxygen: 0 }
  Object.keys(averages).forEach(key => {
    const values = sensors.value.map(s => s[key]).filter(v => v !== null && v !== undefined)
    averages[key] = values.length ? (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1) : 0
  })
  return averages
})

const qualityIndex = computed(() => {
  const scores = { 'Ⅰ': 100, 'Ⅱ': 85, 'Ⅲ': 70, 'Ⅳ': 55, 'Ⅴ': 40, '劣Ⅴ': 25 }
  const list = sensors.value.map(s => scores[s.water_quality]).filter(v => v !== undefined)
  return list.length ? Math.round(list.reduce((a, b) => a + b, 0) / list.length) : 0
})

const riskTable = computed(() => {
  return sensors.value
    .map(sensor => {
      let score = 0
      if (sensor.dissolved_oxygen !== null && sensor.dissolved_oxygen !== undefined && sensor.dissolved_oxygen < 5) score += 3
      if (sensor.ph !== null && sensor.ph !== undefined && (sensor.ph < 6.5 || sensor.ph > 8.5)) score += 2
      if (['Ⅴ', '劣Ⅴ'].includes(sensor.water_quality)) score += 4

      return {
        ...sensor,
        risk_score: score,
        risk_tag: score >= 5 ? 'danger' : score >= 2 ? 'warning' : 'success'
      }
    })
    .sort((a, b) => b.risk_score - a.risk_score)
})

const qualityColors = {
  'Ⅰ': '#00b894',
  'Ⅱ': '#55efc4',
  'Ⅲ': '#ffeaa7',
  'Ⅳ': '#fab1a0',
  'Ⅴ': '#ff7675',
  '劣Ⅴ': '#d63031'
}

const qualityChartRef = ref(null)
const indexChartRef = ref(null)
const provinceChartRef = ref(null)
const trendChartRef = ref(null)
let charts = []
let resizeHandler = null

const initCharts = async () => {
  await nextTick()
  const qChart = echarts.init(qualityChartRef.value)
  const iChart = echarts.init(indexChartRef.value)
  const pChart = echarts.init(provinceChartRef.value)
  const tChart = echarts.init(trendChartRef.value)
  charts = [qChart, iChart, pChart, tChart]

  resizeHandler = () => charts.forEach(chart => chart.resize())
  window.addEventListener('resize', resizeHandler)
}

const updateCharts = () => {
  const trendCount = trendHistory.value.length
  const showTrendPoints = trendCount <= 1
  const qData = Object.entries(qualityColors)
    .map(([name, color]) => ({
      name,
      value: sensors.value.filter(s => s.water_quality === name).length,
      itemStyle: { color }
    }))
    .filter(item => item.value > 0)

  charts[0]?.setOption({
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['60%', '85%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 6 },
        label: { show: false },
        data: qData
      }
    ]
  })

  const times = trendHistory.value.map(item => {
    if (item?.time) return item.time
    const ts = item?.timestamp
    if (typeof ts === 'string') return timeRange.value >= 24 ? ts.slice(5, 10) : ts.slice(11, 16)
    return '--'
  })

  charts[3]?.setOption({
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(255,255,255,0.9)', borderRadius: 12 },
    legend: { icon: 'circle', right: 20 },
    grid: { left: 40, right: 20, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: times, axisLine: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
    series: [
      {
        name: '溶解氧',
        type: 'line',
        smooth: true,
        showSymbol: showTrendPoints,
        symbolSize: showTrendPoints ? 6 : 4,
        data: trendHistory.value.map(item => item.dissolved_oxygen),
        lineStyle: { width: showTrendPoints ? 0 : 3, color: '#0ea5e9' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(9, 132, 227, 0.2)' },
            { offset: 1, color: 'transparent' }
          ])
        }
      },
      {
        name: 'pH值',
        type: 'line',
        smooth: true,
        showSymbol: showTrendPoints,
        symbolSize: showTrendPoints ? 6 : 4,
        data: trendHistory.value.map(item => item.ph),
        lineStyle: { width: showTrendPoints ? 0 : 3, color: '#14b8a6' }
      }
    ]
  })

  charts[1]?.setOption({
    series: [
      {
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        pointer: { show: false },
        progress: {
          show: true,
          overlap: false,
          roundCap: true,
          width: 8,
          itemStyle: { color: '#f59e0b' }
        },
        axisLine: { lineStyle: { width: 8 } },
        splitLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        detail: { show: false },
        data: [{ value: qualityIndex.value }]
      }
    ]
  })

  const provinceCount = {}
  sensors.value.forEach(sensor => {
    const value = typeof sensor.province === 'string' ? sensor.province.trim() : sensor.province
    const province = value || '未知'
    provinceCount[province] = (provinceCount[province] || 0) + 1
  })

  let entries = Object.entries(provinceCount)
  if (entries.length > 1) {
    entries = entries.filter(([name]) => name !== '未知')
  }

  const sorted = entries.sort((a, b) => b[1] - a[1]).slice(0, 10)

  charts[2]?.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '8%', containLabel: true },
    xAxis: { type: 'category', data: sorted.map(item => item[0]), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        data: sorted.map(item => item[1]),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#0ea5e9' },
            { offset: 1, color: '#14b8a6' }
          ]),
          borderRadius: [6, 6, 0, 0]
        }
      }
    ]
  })
}

const loadData = async () => {
  // 先使用缓存数据快速显示
  if (sensorStore.isCacheValid() && sensorStore.cache.sensors.value.length > 0) {
    sensors.value = sensorStore.cache.sensors.value
    overview.value = sensorStore.cache.overview.value
    if (!trendDeviceId.value && sensors.value.length) {
      trendDeviceId.value = sensors.value[0].station_id
    }
    // 立即更新图表
    await nextTick()
    updateCharts()
  }

  loading.value = true
  try {
    const [overviewRes, realtimeRes] = await Promise.all([
      getDashboardOverview(timeRange.value, 300),
      sensorStore.getRealtimeData(
        (lastVersion) => getRealtimeData(300, '', '', '', '', false, lastVersion),
        false,
        { checkUpdate: true }
      )
    ])

    if (overviewRes?.code === 200) {
      overview.value = overviewRes.data.summary || {}
      dataSource.value = overviewRes.data.data_source || '-'
      lastUpdate.value = overviewRes.data.timestamp
    }

    if (realtimeRes?.code === 200) {
      sensors.value = realtimeRes.data?.sensors || []
      lastUpdate.value = realtimeRes.data?.timestamp || lastUpdate.value
      if (!trendDeviceId.value && sensors.value.length) {
        trendDeviceId.value = sensors.value[0].station_id
      }
    }

    await loadTrend()
    updateCharts()
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

const loadDataSourceMode = async () => {
  try {
    const res = await getDataSourceSettings()
    dataSourceMode.value = res?.data?.mode || 'auto'
  } catch (error) {
    dataSourceMode.value = 'auto'
  }
}

const loadTrend = async () => {
  if (!trendDeviceId.value) {
    trendHistory.value = []
    return
  }

  try {
    const res = await getHistoricalData(trendDeviceId.value, timeRange.value)
    if (res?.code === 200 && Array.isArray(res.data?.data)) {
      trendHistory.value = res.data.data
    } else {
      trendHistory.value = []
    }
  } catch (error) {
    console.error('加载趋势数据失败:', error)
    trendHistory.value = []
  }
}

const applyTrendSearch = () => {
  const keyword = trendSearch.value.trim()
  if (!keyword) return
  const match = sensors.value.find(sensor => {
    const name = sensor.station_name || ''
    const id = sensor.station_id || ''
    return name.includes(keyword) || id.includes(keyword)
  })
  if (match) {
    trendDeviceId.value = match.station_id
    loadTrend().then(() => updateCharts())
  }
}

onMounted(async () => {
  await initCharts()
  await loadDataSourceMode()
  if (dataSourceMode.value === 'manual') {
    sensorStore.clearCache()
  }
  await loadData()
})

onUnmounted(() => {
  charts.forEach(chart => chart.dispose())
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
  }
})
</script>

<style scoped lang="scss">
:host {
  --primary: #0ea5e9;
  --glass: rgba(255, 255, 255, 0.86);
}

.analysis-container {
  padding: 24px 30px;
  min-height: 100vh;
  color: #0f172a;
  font-family: "Space Grotesk", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  background:
    radial-gradient(circle at 15% 15%, rgba(16, 185, 129, 0.16), transparent 45%),
    radial-gradient(circle at 85% 0%, rgba(245, 158, 11, 0.18), transparent 50%),
    linear-gradient(160deg, #f5f7fb 0%, #edf2f7 45%, #f3f4f6 100%);
  position: relative;
  overflow: hidden;
}

.analysis-container::before,
.analysis-container::after {
  content: "";
  position: absolute;
  border-radius: 999px;
  filter: blur(0.5px);
  opacity: 0.35;
  z-index: 0;
}

.analysis-container::before {
  width: 360px;
  height: 360px;
  background: conic-gradient(from 90deg, rgba(14, 165, 233, 0.2), transparent 55%);
  top: -140px;
  right: 6%;
}

.analysis-container::after {
  width: 280px;
  height: 280px;
  background: radial-gradient(circle, rgba(245, 158, 11, 0.28), transparent 60%);
  bottom: -120px;
  left: 6%;
}

.dashboard-header {
  margin-bottom: 24px;
  position: relative;
  z-index: 1;

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  h1 {
    font-size: 24px;
    color: #0f172a;
    margin: 0;

    .badge {
      font-size: 12px;
      background: rgba(255, 255, 255, 0.9);
      padding: 2px 8px;
      border-radius: 12px;
      border: 1px solid rgba(15, 23, 42, 0.08);
      vertical-align: middle;
    }
  }

  .timestamp {
    font-size: 13px;
    color: #94a3b8;
    margin-top: 4px;
  }
}

.header-actions {
  display: flex;
  gap: 12px;

  .icon-btn {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    background: #fff;
    cursor: pointer;

    &:hover {
      background: #f8fafc;
      color: var(--primary);
    }

    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
}

.styled-select {
  min-width: 160px;

  :deep(.el-input__wrapper) {
    background: #fff;
    border: 1px solid #e2e8f0;
    box-shadow: none;
    border-radius: 10px;
  }
}

.analysis-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 22px;
  position: relative;
  z-index: 1;
}

.rail {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.canvas {
  display: flex;
  flex-direction: column;
  gap: 22px;
  min-width: 0;
}

.kpi-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.risk-section {
  display: flex;
  flex-direction: column;

  .title-group {
    h3 {
      margin: 0;
      font-size: 16px;
    }

    .subtitle {
      font-size: 12px;
      color: #94a3b8;
      margin-left: 8px;
    }
  }
}

.trend-section {
  display: flex;
  flex-direction: column;
  min-height: 340px;
}

.trend-chart {
  min-height: 300px;
}

.charts-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.quality-chart {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 280px;
}

.province-chart {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 280px;
}

.glass-card {
  background: var(--glass);
  backdrop-filter: blur(12px);
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
  padding: 20px;
  transition: transform 0.25s ease, box-shadow 0.25s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
  }
}

.kpi-card {
  background: linear-gradient(140deg, rgba(255, 255, 255, 0.95), rgba(236, 253, 245, 0.9));
  display: flex;
  align-items: center;
  justify-content: space-between;

  .kpi-info {
    .label {
      font-size: 13px;
      color: #0f766e;
      display: block;
    }

    .value {
      font-size: 32px;
      font-weight: 800;
      color: #0f172a;
    }
  }

  .mini-chart {
    width: 80px;
    height: 60px;
  }
}

.kpi-mini-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;

  .mini-card {
    padding: 15px;

    .label {
      font-size: 12px;
      color: #475569;
      display: block;
    }

    .value {
      font-size: 20px;
      font-weight: 700;
      margin: 4px 0;
      display: block;
    }

    .value.danger {
      color: #dc2626;
    }

    .sub {
      font-size: 11px;
      color: #94a3b8;
    }
  }
}

.metrics-card {
  .card-header {
    font-size: 14px;
    font-weight: 600;
  }
}

.metric-item {
  margin-top: 15px;

  span {
    font-size: 12px;
    color: #475569;
  }

  .bar-bg {
    height: 6px;
    background: #e2e8f0;
    border-radius: 3px;
    margin: 4px 0;
    overflow: hidden;
  }

  .bar-fill {
    height: 100%;
    background: #f59e0b;
    width: 0;
    transition: width 1s;
  }

  .bar-fill.oxygen {
    background: #0ea5e9;
  }

  .bar-fill.ph {
    background: #14b8a6;
  }

  .num {
    font-weight: 600;
    color: #1e293b;
  }
}

.card-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 15px;

  h3 {
    margin: 0;
    font-size: 16px;
  }

  .subtitle {
    font-size: 12px;
    color: #94a3b8;
  }
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}

.chart-box {
  flex: 1;
  min-height: 0;
  width: 100%;
}

.risk-name {
  font-weight: 600;
  color: #0f172a;
}

.risk-meta {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.custom-table {
  :deep(.el-table__header) th {
    background: #f8fafc !important;
    color: #64748b;
    font-weight: 600;
    padding: 8px 0;
    font-size: 12px;
  }

  :deep(.el-table__body) td {
    padding: 6px 0;
    font-size: 12px;
  }

  &.compact {
    :deep(.el-table__header) th {
      padding: 6px 0;
    }

    :deep(.el-table__body) td {
      padding: 4px 0;
    }
  }

  .quality-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    margin-right: 4px;
  }

  .score-tag {
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
  }

  .score-tag.danger {
    background: #fee2e2;
    color: #ef4444;
  }

  .score-tag.warning {
    background: #fef3c7;
    color: #d97706;
  }

  .score-tag.success {
    background: #dcfce7;
    color: #22c55e;
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.spinning {
  animation: spin 1s linear infinite;
}

@media (max-width: 1200px) {
  .analysis-layout {
    grid-template-columns: 1fr;
  }

  .charts-row {
    grid-template-columns: 1fr;
  }

  .risk-section {
    :deep(.el-table) {
      height: 200px !important;
    }
  }

  .quality-chart,
  .province-chart {
    min-height: 240px;
  }
}
</style>
