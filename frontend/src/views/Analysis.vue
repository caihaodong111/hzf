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
              <span class="label">告警数量</span>
              <span class="value danger">{{ overview.alert_count || 0 }}</span>
              <span class="sub">最新快照</span>
            </div>
          </div>
          <div class="metrics-card glass-card">
            <div class="card-header">核心指标均值</div>
            <div class="metric-grid">
              <div v-for="metric in avgMetricCards" :key="metric.key" class="metric-cell">
                <span class="metric-name">{{ metric.label }}</span>
                <span class="metric-value">{{ metric.value }}</span>
              </div>
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
          <el-table
            :data="riskTable"
            style="width: 100%"
            height="320"
            class="custom-table compact risk-table"
            @row-click="handleRiskRowClick"
            :row-class-name="getRiskRowClass"
          >
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
            <el-table-column prop="risk_score" label="风险" width="80" align="center" sortable>
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
              <span v-if="currentStationHistory.length > 0" class="data-count">
                累计数据点: {{ currentStationHistory.length }} 个
              </span>
              <span v-if="historyTimeRange" class="time-range-badge">
                <el-icon><Clock /></el-icon>
                {{ timeRangeText }}
              </span>
            </div>
            <div class="card-actions">
              <el-button
                type="primary"
                size="small"
                :loading="loadingAllHistory"
                :icon="Download"
                @click="loadAllHistory"
                class="load-all-btn"
              >
                {{ loadingAllHistory ? '加载中...' : '加载全部历史' }}
              </el-button>
              <el-input
                v-model="trendSearch"
                placeholder="搜索站点..."
                :prefix-icon="Search"
                @keyup.enter="applyTrendSearch"
                size="small"
                class="search-input"
              />
            </div>
          </div>
          <div ref="trendChartRef" class="chart-box trend-chart"></div>
        </section>

        <section class="charts-row">
          <section class="chart-secondary glass-card quality-chart">
            <div class="card-title">水质类别占比 <span class="live-indicator">实时</span></div>
            <div ref="qualityChartRef" class="chart-box"></div>
          </section>

          <section class="chart-secondary glass-card province-chart">
            <div class="card-title">省内站点 Top 10 <span class="live-indicator">实时</span></div>
            <div ref="provinceChartRef" class="chart-box"></div>
          </section>
        </section>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { getDashboardOverview, getRealtimeData, getHistoricalData, getAllHistoricalData } from '@/api/sensors'
import { getDataSourceSettings } from '@/api/settings'
import sensorStore from '@/stores/sensorStore'
import { Refresh, Search, Download, Clock } from '@element-plus/icons-vue'

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
const loadingAllHistory = ref(false)
const historyTimeRange = ref(null) // 存储历史数据时间范围

// 持久化存储所有历史趋势数据，按站点ID分组
const trendHistoryCache = ref(new Map()) // Map<stationId, HistoryDataPoint[]>
const currentStationHistory = ref([]) // 当前显示的趋势数据（合并后的完整数据）

const dataSourceLabel = computed(() => {
  const map = { national: '国家水质', huawei: '华为云', database: '数据库', manual: '手动入库', auto: '自动' }
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

const formatAvg = (value, digits = 2, unit = '') => {
  const num = typeof value === 'string' ? Number(value) : Number(value)
  if (!Number.isFinite(num)) return '-'
  return `${num.toFixed(digits)}${unit}`
}

const avgMetricCards = computed(() => {
  const data = overview.value || {}
  return [
    { key: 'ph', label: 'pH(无量纲)', value: formatAvg(data.avg_ph, 2) },
    { key: 'dissolved_oxygen', label: '溶解氧(mg/L)', value: formatAvg(data.avg_dissolved_oxygen, 2) },
    { key: 'conductivity', label: '电导率(μS/cm)', value: formatAvg(data.avg_conductivity, 2) },
    { key: 'turbidity', label: '浊度(NTU)', value: formatAvg(data.avg_turbidity, 2) },
    { key: 'permanganate_index', label: '高锰酸盐指数(mg/L)', value: formatAvg(data.avg_permanganate_index, 2) },
    { key: 'ammonia_nitrogen', label: '氨氮(mg/L)', value: formatAvg(data.avg_ammonia_nitrogen, 2) },
    { key: 'total_phosphorus', label: '总磷(mg/L)', value: formatAvg(data.avg_total_phosphorus, 2) },
    { key: 'total_nitrogen', label: '总氮(mg/L)', value: formatAvg(data.avg_total_nitrogen, 2) },
    { key: 'chlorophyll_a', label: '叶绿素a(mg/L)', value: formatAvg(data.avg_chlorophyll_a, 2) },
    { key: 'algae_density', label: '藻密度(cells/L)', value: formatAvg(data.avg_algae_density, 2) }
  ]
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

// 更新图表 - 带动画效果
const updateCharts = () => {
  // 使用当前站点的历史数据（包含所有累计数据）
  const displayHistory = currentStationHistory.value.length > 0 ? currentStationHistory.value : trendHistory.value
  const trendCount = displayHistory.length
  const showTrendPoints = trendCount <= 1

  // 水质类别占比饼图 - 添加动画
  const qData = Object.entries(qualityColors)
    .map(([name, color]) => ({
      name,
      value: sensors.value.filter(s => s.water_quality === name).length,
      itemStyle: {
        color,
        borderRadius: 8,
        borderColor: '#fff',
        borderWidth: 2
      }
    }))
    .filter(item => item.value > 0)

  charts[0]?.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderRadius: 12,
      padding: [12, 16],
      textStyle: { fontSize: 13 }
    },
    series: [
      {
        type: 'pie',
        radius: ['55%', '82%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 8 },
        label: {
          show: true,
          position: 'outside',
          formatter: '{b}: {c}个\n({d}%)',
          fontSize: 11,
          color: '#475569'
        },
        labelLine: {
          show: true,
          length: 15,
          length2: 10,
          smooth: true
        },
        emphasis: {
          scale: true,
          scaleSize: 15,
          itemStyle: {
            shadowBlur: 20,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.3)'
          }
        },
        data: qData,
        // 添加动画配置
        animationType: 'expansion',
        animationEasing: 'cubicOut',
        animationDelay: (idx) => idx * 100
      }
    ],
    // 添加整体动画
    animation: true,
    animationDuration: 1500,
    animationEasing: 'cubicOut',
    animationDelayUpdate: (idx) => idx * 5
  }, true) // true 表示不合并，完全重绘

  // 关键指标趋势图 - 使用持久化的数据
  const times = displayHistory.map(item => {
    if (item?.time) return item.time
    const ts = item?.timestamp
    if (typeof ts === 'string') return timeRange.value >= 24 ? ts.slice(5, 10) : ts.slice(11, 16)
    return '--'
  })

  charts[3]?.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderRadius: 12,
      padding: [12, 16],
      textStyle: { fontSize: 12 },
      axisPointer: {
        type: 'cross',
        crossStyle: { color: '#999' },
        lineStyle: { type: 'dashed' }
      }
    },
    legend: {
      type: 'scroll',
      icon: 'circle',
      top: 8,
      left: 20,
      right: 20,
      itemGap: 12,
      textStyle: { fontSize: 11 }
    },
    grid: { left: 50, right: 30, top: 60, bottom: 50 },
    xAxis: {
      type: 'category',
      data: times,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { fontSize: 10, color: '#64748b' }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } },
      axisLabel: { fontSize: 10, color: '#64748b' }
    },
    series: [
      {
        name: '溶解氧',
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        showSymbol: trendCount <= 20,
        symbolSize: trendCount <= 20 ? 6 : 4,
        data: displayHistory.map(item => item.dissolved_oxygen),
        lineStyle: { width: 2.5, color: '#0ea5e9' },
        itemStyle: { color: '#0ea5e9', borderColor: '#fff', borderWidth: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(14, 165, 233, 0.25)' },
            { offset: 1, color: 'rgba(14, 165, 233, 0.02)' }
          ])
        },
        emphasis: { focus: 'series' }
      },
      {
        name: 'pH值',
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        showSymbol: trendCount <= 20,
        symbolSize: trendCount <= 20 ? 6 : 4,
        data: displayHistory.map(item => item.ph),
        lineStyle: { width: 2.5, color: '#14b8a6' },
        itemStyle: { color: '#14b8a6', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series' }
      },
      {
        name: '电导率',
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        showSymbol: trendCount <= 20,
        symbolSize: trendCount <= 20 ? 6 : 4,
        data: displayHistory.map(item => item.conductivity),
        lineStyle: { width: 2.5, color: '#6366f1' },
        itemStyle: { color: '#6366f1', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series' }
      },
      {
        name: '浊度',
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        showSymbol: trendCount <= 20,
        symbolSize: trendCount <= 20 ? 6 : 4,
        data: displayHistory.map(item => item.turbidity),
        lineStyle: { width: 2.5, color: '#f97316' },
        itemStyle: { color: '#f97316', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series' }
      },
      {
        name: '高锰酸盐指数',
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        showSymbol: trendCount <= 20,
        symbolSize: trendCount <= 20 ? 6 : 4,
        data: displayHistory.map(item => item.permanganate_index ?? item.permanganate),
        lineStyle: { width: 2.5, color: '#f59e0b' },
        itemStyle: { color: '#f59e0b', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series' }
      },
      {
        name: '氨氮',
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        showSymbol: trendCount <= 20,
        symbolSize: trendCount <= 20 ? 6 : 4,
        data: displayHistory.map(item => item.ammonia_nitrogen),
        lineStyle: { width: 2.5, color: '#ef4444' },
        itemStyle: { color: '#ef4444', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series' }
      },
      {
        name: '总磷',
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        showSymbol: trendCount <= 20,
        symbolSize: trendCount <= 20 ? 6 : 4,
        data: displayHistory.map(item => item.total_phosphorus),
        lineStyle: { width: 2.5, color: '#22c55e' },
        itemStyle: { color: '#22c55e', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series' }
      },
      {
        name: '总氮',
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        showSymbol: trendCount <= 20,
        symbolSize: trendCount <= 20 ? 6 : 4,
        data: displayHistory.map(item => item.total_nitrogen),
        lineStyle: { width: 2.5, color: '#0f766e' },
        itemStyle: { color: '#0f766e', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series' }
      },
      {
        name: '叶绿素a',
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        showSymbol: trendCount <= 20,
        symbolSize: trendCount <= 20 ? 6 : 4,
        data: displayHistory.map(item => item.chlorophyll_a),
        lineStyle: { width: 2.5, color: '#a855f7' },
        itemStyle: { color: '#a855f7', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series' }
      },
      {
        name: '藻密度',
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        showSymbol: trendCount <= 20,
        symbolSize: trendCount <= 20 ? 6 : 4,
        data: displayHistory.map(item => item.algae_density),
        lineStyle: { width: 2.5, color: '#64748b' },
        itemStyle: { color: '#64748b', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series' }
      }
    ],
    // 添加动画配置
    animation: true,
    animationDuration: 800,
    animationEasing: 'cubicOut',
    animationDelayUpdate: (idx) => idx * 50
  }, true)

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
          width: 10,
          itemStyle: { color: '#f59e0b' }
        },
        axisLine: {
          lineStyle: {
            width: 10,
            color: [[1, 'rgba(245, 158, 11, 0.15)']]
          }
        },
        splitLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        detail: { show: false },
        data: [{ value: qualityIndex.value }],
        // 添加动画
        animation: true,
        animationDuration: 1000,
        animationEasing: 'cubicOut'
      }
    ]
  }, true)

  // 省份站点Top 10 - 添加动画效果
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
  const maxCount = sorted.length > 0 ? sorted[0][1] : 1

  charts[2]?.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderRadius: 12,
      padding: [12, 16],
      formatter: '{b}: {c}个站点'
    },
    grid: { left: '5%', right: '5%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: sorted.map(item => item[0]),
      axisLabel: {
        rotate: 35,
        fontSize: 11,
        color: '#64748b',
        interval: 0
      },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } },
      axisLabel: { fontSize: 11, color: '#64748b' }
    },
    series: [
      {
        type: 'bar',
        data: sorted.map(item => item[1]),
        itemStyle: {
          color: (params) => {
            const colors = [
              new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#00b894' },
                { offset: 1, color: '#55efc4' }
              ]),
              new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#0ea5e9' },
                { offset: 1, color: '#14b8a6' }
              ]),
              new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#6366f1' },
                { offset: 1, color: '#8b5cf6' }
              ]),
              new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#f59e0b' },
                { offset: 1, color: '#fbbf24' }
              ])
            ]
            return colors[params.dataIndex % colors.length]
          },
          borderRadius: [6, 6, 0, 0]
        },
        label: {
          show: true,
          position: 'top',
          fontSize: 11,
          color: '#475569',
          formatter: '{c}'
        },
        // 添加生长动画
        animationDelay: (idx) => idx * 100
      }
    ],
    // 添加动画配置
    animation: true,
    animationDuration: 1500,
    animationEasing: 'cubicOut',
    animationDelayUpdate: (idx) => idx * 50
  }, true)
}

const loadData = async () => {
  // 先使用缓存数据快速显示
  if (sensorStore.isCacheValid() && sensorStore.cache.sensors.value.length > 0) {
    sensors.value = sensorStore.cache.sensors.value
    overview.value = sensorStore.cache.overview.value
    if (!trendDeviceId.value && sensors.value.length) {
      trendDeviceId.value = riskTable.value[0]?.station_id || sensors.value[0].station_id
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
        trendDeviceId.value = riskTable.value[0]?.station_id || sensors.value[0].station_id
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

// 加载趋势数据 - 支持数据持久化
const loadTrend = async () => {
  if (!trendDeviceId.value) {
    trendHistory.value = []
    currentStationHistory.value = []
    return
  }

  try {
    const res = await getHistoricalData(trendDeviceId.value, timeRange.value)
    if (res?.code === 200 && Array.isArray(res.data?.data)) {
      const newData = res.data.data

      // 合并到缓存中（去除重复时间点）
      const existingCache = trendHistoryCache.value.get(trendDeviceId.value) || []
      const mergedData = mergeHistoryData(existingCache, newData)

      // 更新缓存
      trendHistoryCache.value.set(trendDeviceId.value, mergedData)

      // 更新当前显示的数据
      currentStationHistory.value = mergedData
      trendHistory.value = newData
    } else {
      // 如果请求失败，使用缓存的数据
      const cached = trendHistoryCache.value.get(trendDeviceId.value) || []
      currentStationHistory.value = cached
      trendHistory.value = cached
    }
  } catch (error) {
    console.error('加载趋势数据失败:', error)
    // 出错时使用缓存的数据
    const cached = trendHistoryCache.value.get(trendDeviceId.value) || []
    currentStationHistory.value = cached
    trendHistory.value = cached
  }
}

// 合并历史数据，去除重复的时间点
const mergeHistoryData = (existing, newData) => {
  if (!existing || existing.length === 0) return newData
  if (!newData || newData.length === 0) return existing

  // 使用Map去重，以timestamp为key
  const dataMap = new Map()

  // 先添加现有数据
  existing.forEach(item => {
    if (item?.timestamp) {
      dataMap.set(item.timestamp, item)
    }
  })

  // 再添加新数据（新数据会覆盖同时间点的旧数据）
  newData.forEach(item => {
    if (item?.timestamp) {
      dataMap.set(item.timestamp, item)
    }
  })

  // 转换回数组并按时间排序
  const merged = Array.from(dataMap.values()).sort((a, b) => {
    return new Date(a.timestamp) - new Date(b.timestamp)
  })

  return merged
}

// 加载站点所有历史数据
const loadAllHistory = async () => {
  if (!trendDeviceId.value) return

  loadingAllHistory.value = true
  try {
    const res = await getAllHistoricalData(trendDeviceId.value)
    if (res?.code === 200 && res?.data) {
      const allData = res.data.data || []

      // 更新时间范围信息
      if (res.data.time_range) {
        historyTimeRange.value = {
          start: new Date(res.data.time_range.start).toLocaleDateString('zh-CN'),
          end: new Date(res.data.time_range.end).toLocaleDateString('zh-CN')
        }
      }

      // 合并到缓存
      trendHistoryCache.value.set(trendDeviceId.value, allData)
      currentStationHistory.value = allData

      // 更新图表
      updateCharts()
    }
  } catch (error) {
    console.error('加载全部历史数据失败:', error)
  } finally {
    loadingAllHistory.value = false
  }
}

// 格式化时间范围显示
const timeRangeText = computed(() => {
  if (!historyTimeRange.value) return ''
  return `${historyTimeRange.value.start} ~ ${historyTimeRange.value.end}`
})

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
    // 切换站点时使用缓存数据
    const cached = trendHistoryCache.value.get(match.station_id) || []
    currentStationHistory.value = cached
    if (cached.length > 0) {
      // 有缓存数据，先显示缓存
      updateCharts()
    }
    // 然后加载最新数据
    loadTrend().then(() => updateCharts())
  }
}

const handleRiskRowClick = (row) => {
  if (!row?.station_id) return
  trendDeviceId.value = row.station_id
  // 切换站点时使用缓存数据
  const cached = trendHistoryCache.value.get(row.station_id) || []
  currentStationHistory.value = cached
  if (cached.length > 0) {
    // 有缓存数据，先显示缓存
    updateCharts()
  }
  // 然后加载最新数据
  loadTrend().then(() => updateCharts())
}

const getRiskRowClass = ({ row }) => {
  return row?.station_id && row.station_id === trendDeviceId.value ? 'is-selected' : ''
}

// 自动刷新定时器
let autoRefreshTimer = null

// 启动自动刷新
const startAutoRefresh = () => {
  // 清除现有定时器
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
  }

  // 每30秒自动刷新一次
  autoRefreshTimer = setInterval(() => {
    // 静默刷新，不显示loading
    loadTrend()
    updateCharts()
  }, 30000) // 30秒
}

// 停止自动刷新
const stopAutoRefresh = () => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

onMounted(async () => {
  await initCharts()
  await loadDataSourceMode()
  if (dataSourceMode.value === 'manual') {
    sensorStore.clearCache()
  }
  await loadData()

  // 启动自动刷新
  startAutoRefresh()
})

onUnmounted(() => {
  // 停止自动刷新
  stopAutoRefresh()

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

// 数据更新闪烁动画
@keyframes dataFlash {
  0% { opacity: 1; }
  50% { opacity: 0.6; }
  100% { opacity: 1; }
}

// 脉动动画
@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
}

// 加载动画
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

// 条形图生长动画
@keyframes growUp {
  from { transform: scaleY(0); }
  to { transform: scaleY(1); }
}

// 饼图旋转动画
@keyframes rotateIn {
  from { transform: rotate(-90deg) scale(0.8); opacity: 0; }
  to { transform: rotate(0) scale(1); opacity: 1; }
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

.risk-table :deep(.el-table__row.is-selected) {
  background: rgba(14, 165, 233, 0.14);
}

.risk-table :deep(.el-table__row.is-selected:hover) {
  background: rgba(14, 165, 233, 0.18);
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

  .chart-box {
    animation: rotateIn 0.8s cubic-out;
  }
}

.province-chart {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 280px;

  .chart-box {
    animation: growUp 0.6s cubic-out;
    transform-origin: bottom;
  }
}

// 图表容器动画效果
.chart-box {
  position: relative;
  transition: all 0.3s ease;

  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.3),
      transparent
    );
    animation: shimmer 2s infinite;
    pointer-events: none;
    opacity: 0;
  }

  &:hover::after {
    opacity: 1;
  }
}

// 标题动画
.card-title {
  position: relative;
  padding-left: 12px;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 4px;
    height: 16px;
    background: linear-gradient(180deg, var(--primary), #14b8a6);
    border-radius: 2px;
    animation: pulse 2s ease-in-out infinite;
  }
}

// 实时指示器
.live-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #22c55e;
  margin-left: 8px;

  &::before {
    content: '';
    width: 8px;
    height: 8px;
    background: #22c55e;
    border-radius: 50%;
    animation: dataFlash 1.5s ease-in-out infinite;
  }
}

// 数据计数器
.data-count {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  margin-left: 8px;
  font-size: 11px;
  color: #64748b;
  background: rgba(14, 165, 233, 0.08);
  border-radius: 10px;
  border: 1px solid rgba(14, 165, 233, 0.2);

  &:hover {
    background: rgba(14, 165, 233, 0.12);
  }
}

// 时间范围标签
.time-range-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  margin-left: 8px;
  font-size: 11px;
  color: #22c55e;
  background: rgba(34, 197, 94, 0.08);
  border-radius: 10px;
  border: 1px solid rgba(34, 197, 94, 0.2);

  .el-icon {
    font-size: 12px;
  }

  &:hover {
    background: rgba(34, 197, 94, 0.12);
  }
}

// 卡片操作区域
.card-actions {
  display: flex;
  align-items: center;
  gap: 10px;

  .load-all-btn {
    background: linear-gradient(135deg, #0ea5e9, #14b8a6);
    border: none;
    border-radius: 8px;
    font-size: 12px;
    padding: 6px 14px;
    transition: all 0.3s ease;

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
    }

    &:active {
      transform: translateY(0);
    }
  }

  .search-input {
    width: 180px;

    :deep(.el-input__wrapper) {
      background: rgba(255, 255, 255, 0.9);
      border-radius: 8px;
      box-shadow: none;
      border: 1px solid #e2e8f0;
    }
  }
}

// 标题区域布局
.title-info {
  display: flex;
  flex-direction: column;
  gap: 4px;

  h3 {
    margin: 0;
    font-size: 16px;
    color: #0f172a;
  }

  .subtitle {
    font-size: 12px;
    color: #64748b;
  }
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
  grid-template-columns: 1fr;
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
  overflow: hidden;

  .card-header {
    font-size: 14px;
    font-weight: 600;
  }
}

.metric-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px 12px;
  width: 100%;
}

.metric-cell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(15, 23, 42, 0.06);
  min-width: 0;
}

.metric-name {
  font-size: 12px;
  color: #475569;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.metric-value {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
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

.risk-table {
  :deep(.el-table__header-wrapper th.is-sortable .cell) {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    white-space: nowrap;
  }

  :deep(.el-table__header-wrapper th.is-sortable .caret-wrapper) {
    flex: 0 0 auto;
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

  .metric-grid {
    grid-template-columns: 1fr;
  }
}
</style>
