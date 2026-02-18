<template>
  <div class="analysis-page">
    <div class="analysis-hero glass-card">
      <div class="hero-left">
        <div class="hero-title">水质综合分析</div>
        <div class="hero-subtitle">水质类别、指标均值与站点风险的综合视图</div>
        <div class="hero-meta">
          <el-tag size="small" type="info">数据源: {{ dataSourceLabel }}</el-tag>
          <el-tag size="small" type="success">更新时间: {{ lastUpdateText }}</el-tag>
          <el-tag size="small" type="warning">样本数: {{ sensors.length }}</el-tag>
        </div>
      </div>
      <div class="hero-actions">
        <el-select v-model="timeRange" class="analysis-select" style="width: 140px" @change="loadData">
          <el-option label="最近24小时" :value="24" />
          <el-option label="最近7天" :value="168" />
          <el-option label="最近30天" :value="720" />
        </el-select>
        <div class="segment-search">
          <input
            type="text"
            placeholder="站点搜索..."
            v-model="trendSearch"
            @keyup.enter="applyTrendSearch"
          />
        </div>
        <button class="refresh-btn" type="button" @click="loadData" :disabled="loading">
          <el-icon :class="{ spinning: loading }"><Refresh /></el-icon>
          <span>刷新</span>
        </button>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card glass-card">
        <div class="kpi-label">监测站点</div>
        <div class="kpi-value">{{ overview.total_devices || sensors.length || 0 }}</div>
        <div class="kpi-desc">在线 {{ overview.online_devices || onlineCount }}</div>
      </div>
      <div class="kpi-card glass-card">
        <div class="kpi-label">告警数量</div>
        <div class="kpi-value">{{ overview.alert_count || 0 }}</div>
        <div class="kpi-desc">近 {{ timeRange }} 小时</div>
      </div>
      <div class="kpi-card glass-card">
        <div class="kpi-label">平均水温</div>
        <div class="kpi-value">{{ avgMetrics.temperature }}°C</div>
        <div class="kpi-desc">全站点均值</div>
      </div>
      <div class="kpi-card glass-card">
        <div class="kpi-label">平均溶解氧</div>
        <div class="kpi-value">{{ avgMetrics.dissolved_oxygen }} mg/L</div>
        <div class="kpi-desc">全站点均值</div>
      </div>
      <div class="kpi-card glass-card">
        <div class="kpi-label">平均 pH</div>
        <div class="kpi-value">{{ avgMetrics.ph }}</div>
        <div class="kpi-desc">全站点均值</div>
      </div>
      <div class="kpi-card glass-card">
        <div class="kpi-label">综合指数</div>
        <div class="kpi-value">{{ qualityIndex }}</div>
        <div class="kpi-desc">水质综合评分</div>
      </div>
    </div>

    <div class="section-grid">
      <div class="chart-card glass-card">
        <div class="card-title">水质类别分布</div>
        <div ref="qualityChartRef" class="chart-box"></div>
      </div>
      <div class="chart-card glass-card">
        <div class="card-title">综合水质指数</div>
        <div ref="indexChartRef" class="chart-box"></div>
      </div>
      <div class="chart-card glass-card">
        <div class="card-title">关键指标均值</div>
        <div ref="paramChartRef" class="chart-box"></div>
      </div>
      <div class="chart-card glass-card">
        <div class="card-title">省份站点分布</div>
        <div ref="provinceChartRef" class="chart-box"></div>
      </div>
      <div class="chart-card glass-card">
        <div class="card-title">流域站点分布</div>
        <div ref="basinChartRef" class="chart-box"></div>
      </div>
      <div class="chart-card glass-card full-width">
        <div class="card-title">关键指标趋势（{{ trendDeviceName }}）</div>
        <div ref="trendChartRef" class="chart-box chart-tall"></div>
      </div>
    </div>

    <div class="table-card glass-card">
      <div class="card-title">风险站点清单</div>
      <el-table :data="riskTable" style="width: 100%" max-height="420">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="device_name" label="站点" width="200">
          <template #default="{ row }">
            {{ row.device_name || row.device_id }}
          </template>
        </el-table-column>
        <el-table-column prop="location" label="位置" width="160" />
        <el-table-column prop="water_quality" label="水质类别" width="100">
          <template #default="{ row }">
            <el-tag :type="getQualityType(row.water_quality)">
              {{ row.water_quality || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="temperature" label="水温" width="90" />
        <el-table-column prop="ph" label="pH" width="80" />
        <el-table-column prop="dissolved_oxygen" label="溶解氧" width="110" />
        <el-table-column prop="risk_level" label="风险等级" width="110">
          <template #default="{ row }">
            <el-tag :type="row.risk_tag">{{ row.risk_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="risk_score" label="风险分" width="90" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getDashboardOverview, getRealtimeData, getHistoricalData } from '@/api/sensors'
import { Refresh } from '@element-plus/icons-vue'

const timeRange = ref(24)
const loading = ref(false)
const overview = ref({})
const sensors = ref([])
const dataSource = ref('-')
const lastUpdate = ref('')
const trendDeviceId = ref('')
const trendHistory = ref([])
const trendSearch = ref('')

const dataSourceLabel = computed(() => {
  const map = {
    national: '国家水质',
    open: '开放数据',
    simulator: '模拟数据',
    database: '数据库'
  }
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
  const target = sensors.value.find(s => s.device_id === trendDeviceId.value)
  return target?.device_name || target?.device_id || '未选择'
})

const onlineCount = computed(() => sensors.value.filter(s => s.status === 'online').length)

const avgMetrics = computed(() => {
  const averages = {}
  const params = ['temperature', 'ph', 'dissolved_oxygen']
  params.forEach(param => {
    const values = sensors.value.map(s => s[param]).filter(v => v !== null && v !== undefined)
    averages[param] = values.length ? (values.reduce((a, b) => a + b, 0) / values.length).toFixed(2) : 0
  })
  return averages
})

const qualityIndex = computed(() => {
  const scores = { 'Ⅰ': 100, 'Ⅱ': 85, 'Ⅲ': 70, 'Ⅳ': 55, 'Ⅴ': 40, '劣Ⅴ': 25 }
  const list = sensors.value.map(s => scores[s.water_quality]).filter(v => v !== undefined)
  if (!list.length) return 0
  const sum = list.reduce((a, b) => a + b, 0)
  return Math.round(sum / list.length)
})

const riskTable = computed(() => {
  const rows = sensors.value.map(sensor => {
    let score = 0
    const temperature = sensor.temperature
    const ph = sensor.ph
    const dissolvedOxygen = sensor.dissolved_oxygen
    const turbidity = sensor.turbidity
    const conductivity = sensor.conductivity
    const waterQuality = sensor.water_quality

    if (temperature !== null && temperature !== undefined && (temperature < 18 || temperature > 32)) score += 1
    if (ph !== null && ph !== undefined && (ph < 6.5 || ph > 8.5)) score += 2
    if (dissolvedOxygen !== null && dissolvedOxygen !== undefined && dissolvedOxygen < 5) score += 2
    if (turbidity !== null && turbidity !== undefined && turbidity > 10) score += 1
    if (conductivity !== null && conductivity !== undefined && conductivity > 1000) score += 1
    if (waterQuality === 'Ⅳ') score += 1
    if (waterQuality === 'Ⅴ' || waterQuality === '劣Ⅴ') score += 2

    let riskLevel = '低'
    let riskTag = 'success'
    if (score >= 4) {
      riskLevel = '高'
      riskTag = 'danger'
    } else if (score >= 2) {
      riskLevel = '中'
      riskTag = 'warning'
    }

    return {
      ...sensor,
      risk_score: score,
      risk_level: riskLevel,
      risk_tag: riskTag
    }
  })

  return rows
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, 20)
})

const qualityColors = {
  'Ⅰ': '#52c41a',
  'Ⅱ': '#73d13d',
  'Ⅲ': '#ffc53d',
  'Ⅳ': '#ff9c6e',
  'Ⅴ': '#ff4d4f',
  '劣Ⅴ': '#cf1322'
}

const getQualityType = (quality) => {
  const typeMap = {
    'Ⅰ': 'success',
    'Ⅱ': 'success',
    'Ⅲ': 'warning',
    'Ⅳ': 'warning',
    'Ⅴ': 'danger',
    '劣Ⅴ': 'danger'
  }
  return typeMap[quality] || 'info'
}

const qualityChartRef = ref(null)
const indexChartRef = ref(null)
const paramChartRef = ref(null)
const provinceChartRef = ref(null)
const basinChartRef = ref(null)
const trendChartRef = ref(null)

let qualityChart = null
let indexChart = null
let paramChart = null
let provinceChart = null
let basinChart = null
let trendChart = null
let resizeHandler = null

const loadData = async () => {
  loading.value = true
  try {
    const [overviewRes, realtimeRes] = await Promise.all([
      getDashboardOverview(timeRange.value, 300),
      getRealtimeData(300, '', '', '', '', true)
    ])

    if (overviewRes.code === 200) {
      overview.value = overviewRes.data.summary || {}
      dataSource.value = overviewRes.data.data_source || '-'
      lastUpdate.value = overviewRes.data.timestamp
    }

    if (realtimeRes.code === 200) {
      sensors.value = realtimeRes.data?.sensors || []
      lastUpdate.value = realtimeRes.data?.timestamp || lastUpdate.value
      if (!trendDeviceId.value && sensors.value.length) {
        trendDeviceId.value = sensors.value[0].device_id
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

const loadTrend = async () => {
  if (!trendDeviceId.value) {
    trendHistory.value = []
    updateTrendChart()
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
  } finally {
    updateTrendChart()
  }
}

const applyTrendSearch = () => {
  const keyword = trendSearch.value.trim()
  if (!keyword) return
  const match = sensors.value.find(sensor => {
    const name = sensor.device_name || ''
    const id = sensor.device_id || ''
    return name.includes(keyword) || id.includes(keyword)
  })
  if (match) {
    trendDeviceId.value = match.device_id
    loadTrend()
  }
}

const updateCharts = () => {
  updateQualityChart()
  updateIndexChart()
  updateParamChart()
  updateProvinceChart()
  updateBasinChart()
  updateTrendChart()
}

const updateQualityChart = () => {
  const qualityCount = {}
  sensors.value.forEach(sensor => {
    const quality = sensor.water_quality || '未知'
    qualityCount[quality] = (qualityCount[quality] || 0) + 1
  })

  const data = Object.entries(qualityCount).map(([name, value]) => ({
    name,
    value,
    itemStyle: { color: qualityColors[name] || '#d9d9d9' }
  }))

  qualityChart?.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, left: 'center' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
        data
      }
    ]
  })
}

const updateIndexChart = () => {
  indexChart?.setOption({
    series: [
      {
        type: 'gauge',
        min: 0,
        max: 100,
        splitNumber: 5,
        progress: { show: true, width: 14 },
        axisLine: {
          lineStyle: {
            width: 14,
            color: [
              [0.4, '#ff4d4f'],
              [0.7, '#faad14'],
              [1, '#52c41a']
            ]
          }
        },
        axisTick: { show: false },
        splitLine: { length: 8 },
        axisLabel: { distance: 6 },
        pointer: { width: 4 },
        detail: { valueAnimation: true, formatter: '{value}', fontSize: 22 },
        data: [{ value: qualityIndex.value, name: '水质指数' }]
      }
    ]
  })
}

const updateParamChart = () => {
  const paramDefs = [
    { key: 'temperature', label: '温度', unit: '°C', max: 40 },
    { key: 'ph', label: 'pH', unit: '', max: 14 },
    { key: 'dissolved_oxygen', label: '溶解氧', unit: 'mg/L', max: 15 },
    { key: 'conductivity', label: '电导率', unit: 'μS/cm', max: 2000 },
    { key: 'turbidity', label: '浊度', unit: 'NTU', max: 100 },
    { key: 'ammonia_nitrogen', label: '氨氮', unit: 'mg/L', max: 5 }
  ]

  const rawValues = paramDefs.map(def => {
    const items = sensors.value.map(s => s[def.key]).filter(v => v !== null && v !== undefined)
    return items.length ? Number((items.reduce((a, b) => a + b, 0) / items.length).toFixed(2)) : 0
  })

  const normalizedValues = rawValues.map((value, index) => {
    const max = paramDefs[index].max || 1
    return Number(((value / max) * 100).toFixed(2))
  })

  paramChart?.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        return params
          .map(item => `${item.name}: ${rawValues[item.dataIndex]}${paramDefs[item.dataIndex].unit}`)
          .join('<br/>')
      }
    },
    grid: { left: '3%', right: '4%', bottom: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: paramDefs.map(def => def.label),
      axisLabel: { rotate: 20 }
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%' }
    },
    series: [
      {
        type: 'bar',
        data: normalizedValues,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#5b8ff9' },
            { offset: 1, color: '#61d9a0' }
          ]),
          borderRadius: [6, 6, 0, 0]
        }
      }
    ]
  })
}

const updateProvinceChart = () => {
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

  provinceChart?.setOption({
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
            { offset: 0, color: '#667eea' },
            { offset: 1, color: '#764ba2' }
          ]),
          borderRadius: [6, 6, 0, 0]
        }
      }
    ]
  })
}

const updateBasinChart = () => {
  const basinCount = {}
  sensors.value.forEach(sensor => {
    const value = typeof sensor.river_basin === 'string' ? sensor.river_basin.trim() : sensor.river_basin
    const basin = value || '未知'
    basinCount[basin] = (basinCount[basin] || 0) + 1
  })

  let entries = Object.entries(basinCount)
  if (entries.length > 1) {
    entries = entries.filter(([name]) => name !== '未知')
  }

  const data = entries.map(([name, value]) => ({ name, value }))

  basinChart?.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}个' },
    series: [
      {
        type: 'pie',
        radius: '65%',
        data,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.4)'
          }
        }
      }
    ]
  })
}

const formatTimeLabel = (item) => {
  if (item?.time) return item.time
  const ts = item?.timestamp
  if (typeof ts === 'string') {
    return timeRange.value >= 24 ? ts.slice(5, 10) : ts.slice(11, 16)
  }
  if (ts instanceof Date) {
    return timeRange.value >= 24
      ? ts.toISOString().slice(5, 10)
      : ts.toISOString().slice(11, 16)
  }
  return '--:--'
}

const updateTrendChart = () => {
  const sorted = [...trendHistory.value].sort((a, b) => {
    const at = a?.timestamp ? new Date(a.timestamp).getTime() : 0
    const bt = b?.timestamp ? new Date(b.timestamp).getTime() : 0
    return at - bt
  })

  const times = sorted.map(item => formatTimeLabel(item))
  const tempSeries = sorted.map(item => item.temperature ?? null)
  const phSeries = sorted.map(item => item.ph ?? null)
  const doSeries = sorted.map(item => item.dissolved_oxygen ?? null)

  const hasData = times.length > 0

  trendChart?.setOption(
    {
      title: hasData ? undefined : { text: '暂无趋势数据', left: 'center', top: 'center', textStyle: { color: '#9CA3AF', fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      legend: { data: ['水温', 'pH', '溶解氧'] },
      grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
      xAxis: { type: 'category', data: hasData ? times : ['--'] },
      yAxis: { type: 'value' },
      series: [
        { name: '水温', type: 'line', smooth: true, data: hasData ? tempSeries : [0] },
        { name: 'pH', type: 'line', smooth: true, data: hasData ? phSeries : [0] },
        { name: '溶解氧', type: 'line', smooth: true, data: hasData ? doSeries : [0] }
      ]
    },
    true
  )
}

const initCharts = async () => {
  await nextTick()
  qualityChart = echarts.init(qualityChartRef.value)
  indexChart = echarts.init(indexChartRef.value)
  paramChart = echarts.init(paramChartRef.value)
  provinceChart = echarts.init(provinceChartRef.value)
  basinChart = echarts.init(basinChartRef.value)
  trendChart = echarts.init(trendChartRef.value)

  resizeHandler = () => {
    qualityChart?.resize()
    indexChart?.resize()
    paramChart?.resize()
    provinceChart?.resize()
    basinChart?.resize()
    trendChart?.resize()
  }

  window.addEventListener('resize', resizeHandler)
}

onMounted(async () => {
  await initCharts()
  await loadData()
  resizeHandler?.()
})

onUnmounted(() => {
  qualityChart?.dispose()
  indexChart?.dispose()
  paramChart?.dispose()
  provinceChart?.dispose()
  basinChart?.dispose()
  trendChart?.dispose()
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
  }
})
</script>

<style scoped lang="scss">
.analysis-page {
  padding: 24px 32px;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}

.analysis-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 24px;
  margin-bottom: 20px;
}

.hero-left {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hero-title {
  font-size: 22px;
  font-weight: 600;
  color: #1F2937;
}

.hero-subtitle {
  font-size: 13px;
  color: #6B7280;
}

.hero-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.analysis-select {
  :deep(.el-input__wrapper) {
    background: #d9d9d9;
    border: 1px solid #c8c8c8;
    box-shadow: none;
    border-radius: 8px;
    font-weight: 600;
    color: #1f2937;
    padding: 8px 12px;
    min-height: 36px;
    height: 36px;
  }

  :deep(.el-input__inner) {
    height: 20px;
    line-height: 20px;
  }

  :deep(.el-input__inner::placeholder) {
    color: #374151;
  }
}

.segment-search {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #ffffff;
  min-width: 220px;

  input {
    border: none;
    outline: none;
    width: 100%;
    font-size: 14px;
    color: #1f2937;

    &::placeholder {
      color: #9ca3af;
    }
  }
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: rgba(255, 255, 255, 0.85);
  color: #1f2937;
  font-weight: 600;
  cursor: pointer;
  transition: box-shadow 0.2s ease, transform 0.2s ease;

  &:hover:not(:disabled) {
    box-shadow: 0 6px 16px rgba(15, 23, 42, 0.12);
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.kpi-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kpi-label {
  font-size: 12px;
  color: #6B7280;
}

.kpi-value {
  font-size: 22px;
  font-weight: 600;
  color: #111827;
}

.kpi-desc {
  font-size: 12px;
  color: #9CA3AF;
}

.section-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

.chart-card {
  padding: 20px;
  min-height: 280px;
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #1F2937;
  margin-bottom: 12px;
}

.chart-box {
  width: 100%;
  height: 260px;
}

.chart-tall {
  height: 320px;
}

.table-card {
  padding: 20px;
}

@media (max-width: 1400px) {
  .kpi-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .section-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .analysis-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .section-grid {
    grid-template-columns: 1fr;
  }
}
</style>
