<template>
  <div class="dashboard-page">
    <div class="fluid-bg"></div>

    <div class="dashboard-content">
      <header class="top-bar">
        <div class="greeting">
          <h1>水质监测概览</h1>
          <p>实时监控全域 {{ total }} 个断面数据</p>
        </div>
        <div class="top-actions">
          <button
            v-if="isManualMode"
            class="action-btn manual-btn"
            type="button"
            :disabled="isManualFetching"
            @click="handleManualFetch"
          >
            {{ isManualFetching ? '获取中...' : '获取' }}
          </button>
          <button class="action-btn" @click="handleManualRefresh">
            <el-icon :class="{ spinning: isRefreshing }"><Refresh /></el-icon>
          </button>
        </div>
      </header>

      <section class="metrics-grid">
        <div class="metric-card glass" v-for="(stat, idx) in stats" :key="idx">
          <div class="metric-header">
            <span class="label">{{ stat.label }}</span>
            <div class="trend-tag" :class="stat.trend">
              {{ stat.trend === 'up' ? '↑' : stat.trend === 'down' ? '↓' : '→' }}
            </div>
          </div>
          <div class="metric-body">
            <h2 class="value">{{ stat.value }}</h2>
            <div class="sparkline-container">
              <svg viewBox="0 0 100 32" class="sparkline-svg" aria-hidden="true">
                <polyline :points="getSparklinePoints(stat.history)" :class="stat.trend" />
              </svg>
            </div>
          </div>
        </div>
      </section>

      <section class="content-grid">
        <div class="data-panel glass">
          <div class="panel-header">
            <h3>实时数据列表</h3>
          </div>

        <div class="panel-filters">
            <div class="cascader-wrapper" ref="provinceMenuRef">
              <button
                class="cascader-trigger"
                type="button"
                @click="toggleProvinceDropdown"
                :class="{ active: provinceDropdownOpen }"
              >
                <span class="trigger-text">{{ selectedProvinceLabel }}</span>
                <el-icon class="trigger-arrow" :class="{ rotated: provinceDropdownOpen }"><ArrowDown /></el-icon>
              </button>
              <div v-if="provinceDropdownOpen" class="cascader-panel">
                <div class="cascader-column cascader-main">
                  <div
                    v-for="(item, index) in provinceCascadeOptions"
                  :key="item.code || item.name"
                  class="cascader-item"
                  :class="{ active: index === activeProvinceIndex }"
                  @click="selectProvince(item, index)"
                >
                    <span>{{ item.name }}</span>
                    <span v-if="item.children && item.children.length" class="item-arrow">▶</span>
                  </div>
                </div>
                <div class="cascader-column cascader-sub" v-if="activeProvinceChildren.length">
                  <div
                    v-for="child in activeProvinceChildren"
                    :key="child"
                    class="cascader-item"
                    @click="selectProvinceChild(child)"
                  >
                    <span>{{ child }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="segment-search">
              <input
                type="text"
                placeholder="断面名称搜索..."
                v-model="filters.search"
                @keyup.enter="loadRealtimeData(true)"
              />
            </div>

            <button class="search-btn" type="button" @click="loadRealtimeData(true)">
              <el-icon class="search-icon"><Search /></el-icon>
              搜索
            </button>
          </div>

          <div class="realtime-section">
            <div class="custom-list">
            <div class="list-header">
              <span>省份</span>
              <span>流域</span>
              <span>断面名称</span>
              <span>水质类别</span>
              <span>监测时间</span>
              <span>水温(℃)</span>
              <span>pH(无量纲)</span>
              <span>溶解氧(mg/L)</span>
              <span>电导率(μS/cm)</span>
              <span>浊度(NTU)</span>
              <span>高锰酸盐指数(mg/L)</span>
              <span>氨氮(mg/L)</span>
              <span>总磷(mg/L)</span>
              <span>总氮(mg/L)</span>
              <span>叶绿素a(mg/L)</span>
              <span>藻密度(cells/L)</span>
              <span>状态</span>
            </div>
            <div class="list-body" :class="{ scrolling: shouldScroll }">
              <div class="list-track" :style="{ '--scroll-duration': scrollDuration }">
                <div
                  class="list-item"
                  v-for="(item, index) in scrollSensors"
                  :key="`${index}-${item.station_id || item.station_name}`"
                  :aria-hidden="shouldScroll && index >= sensorsCount"
                >
                  <span class="cell">{{ item.province || '-' }}</span>
                  <span class="cell">{{ item.river_basin || '-' }}</span>
                  <span class="name" :class="{ 'data-updated': item.justUpdated }">{{ item.station_name }}</span>
                  <span>
                    <b class="quality-text" :class="getQualityClass(item.water_quality)">{{ item.water_quality || '-' }}</b>
                  </span>
                  <span class="time" :class="{ 'data-updated': item.justUpdated }">{{ formatTime(item.timestamp) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'temperature')) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'ph')) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'dissolved_oxygen')) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'conductivity')) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'turbidity')) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'permanganate_index')) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'ammonia_nitrogen')) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'total_phosphorus')) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'total_nitrogen')) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'chlorophyll_a')) }}</span>
                  <span class="cell">{{ formatValue(getMetricValue(item, 'algae_density')) }}</span>
                  <span class="status">
                    <div class="indicator" :class="isOnline(item.timestamp) ? 'online' : 'offline'"></div>
                  </span>
                </div>
              </div>
            </div>
            </div>

            <!-- 加载中弹窗 -->
            <div v-if="loading" class="filter-loading">加载中...</div>
          </div>

        </div>

      </section>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getRealtimeData as apiGetRealtimeData, syncRealtimeData, getAreaOptions } from '@/api/sensors'
import { getDataSourceSettings } from '@/api/settings'
import sensorStore from '@/stores/sensorStore'
import { DataLine, Warning, Refresh, CircleCheck, ArrowDown, Search } from '@element-plus/icons-vue'

const loading = computed(() => sensorStore.tasks.realtime.loading.value)
const sensors = ref([])
const total = ref(0)
const dataSourceMode = ref('auto')
const isManualFetching = ref(false)
const isRefreshing = computed(() => (
  sensorStore.tasks.realtime.loading.value || sensorStore.tasks.sync.loading.value
))
const updateLog = ref([])
const disposed = ref(false)
const realtimeLoadSeq = ref(0)

const filters = ref({
  province: '',
  river: '',
  search: ''
})

const filteredSensors = computed(() => sensors.value)
const isManualMode = computed(() => dataSourceMode.value === 'manual')

const sensorsCount = computed(() => filteredSensors.value.length)
const shouldScroll = computed(() => filteredSensors.value.length > 8)
const scrollDuration = computed(() => {
  if (!filteredSensors.value.length) return '18s'
  const base = filteredSensors.value.length * 2.4
  return `${Math.max(base, 18)}s`
})
const scrollSensors = computed(() => {
  if (!shouldScroll.value) return filteredSensors.value
  return [...filteredSensors.value, ...filteredSensors.value]
})

const provinceCascadeOptions = ref([{ code: '', name: '全国', children: [] }])

const provinceDropdownOpen = ref(false)
const activeProvinceIndex = ref(0)
const selectedProvince = ref({ code: '', name: '全国' })
const selectedProvinceChild = ref('')
const provinceMenuRef = ref(null)

const activeProvinceChildren = computed(() => {
  const item = provinceCascadeOptions.value[activeProvinceIndex.value]
  if (!item || !item.children || item.code === '') return []
  return item.children
})

const selectedProvinceLabel = computed(() => {
  if (selectedProvinceChild.value) {
    return `${selectedProvince.value.name} / ${selectedProvinceChild.value}`
  }
  return selectedProvince.value.name
})

// 切换省份下拉
const toggleProvinceDropdown = () => {
  provinceDropdownOpen.value = !provinceDropdownOpen.value
  if (provinceDropdownOpen.value && selectedProvince.value.code) {
    const index = provinceCascadeOptions.value.findIndex(option => option.code === selectedProvince.value.code)
    activeProvinceIndex.value = index >= 0 ? index : 0
  }
}

// 选择省份
const selectProvince = (item, index = 0) => {
  selectedProvince.value = { code: item.code, name: item.name }
  selectedProvinceChild.value = ''
  filters.value.province = item.code
  if (item.children && item.children.length) {
    activeProvinceIndex.value = index
    loadRealtimeData(true) // 省级筛选
    return
  }
  provinceDropdownOpen.value = false
  loadRealtimeData(true) // 强制刷新
}

const selectProvinceChild = (child) => {
  const active = provinceCascadeOptions.value[activeProvinceIndex.value]
  if (active) {
    selectedProvince.value = { code: active.code, name: active.name }
    filters.value.province = active.code
  }
  selectedProvinceChild.value = child
  provinceDropdownOpen.value = false
  loadRealtimeData(true) // 强制刷新
}

const loadAreaOptions = async () => {
  try {
    const res = await getAreaOptions()
    if (res?.code === 200) {
      const options = res?.data?.options || []
      if (Array.isArray(options) && options.length) {
        provinceCascadeOptions.value = options
        const selectedCode = selectedProvince.value.code
        const exists = provinceCascadeOptions.value.some(option => option.code === selectedCode)
        if (!exists) {
          selectedProvince.value = { code: '', name: '全国' }
          selectedProvinceChild.value = ''
          activeProvinceIndex.value = 0
          filters.value.province = ''
        }
      }
    }
  } catch (e) {
    // ignore; keep default options
  }
}

// 点击外部关闭下拉
const handleClickOutside = (e) => {
  if (provinceMenuRef.value && !provinceMenuRef.value.contains(e.target)) {
    provinceDropdownOpen.value = false
  }
}

const justUpdatedCount = computed(() => sensors.value.filter(s => s.justUpdated).length)

const statHistory = ref({
  total: [],
  goodRate: [],
  warningCount: [],
  onlineCount: []
})

const pushHistory = (key, value) => {
  const series = statHistory.value[key]
  if (!series) return
  series.push(value)
  if (series.length > 24) series.shift()
}

const getTrend = (series) => {
  if (!series || series.length < 2) return 'flat'
  return series[series.length - 1] >= series[series.length - 2] ? 'up' : 'down'
}

const getSparklinePoints = (series) => {
  if (!series || series.length === 0) return ''
  const width = 100
  const height = 32
  const padding = 4
  const min = Math.min(...series)
  const max = Math.max(...series)
  const range = max - min || 1
  return series
    .map((value, index) => {
      const x = padding + (index / Math.max(series.length - 1, 1)) * (width - padding * 2)
      const y = padding + (1 - (value - min) / range) * (height - padding * 2)
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')
}

const qualityStats = computed(() => {
  const stats = { 'Ⅰ': 0, 'Ⅱ': 0, 'Ⅲ': 0, 'Ⅳ': 0, 'Ⅴ': 0, '劣Ⅴ': 0, '': 0 }
  sensors.value.forEach(s => {
    const quality = s.water_quality || ''
    if (quality in stats) stats[quality]++
  })
  return stats
})

const onlineCount = computed(() => sensors.value.filter(s => isOnline(s.timestamp)).length)

const goodRateValue = computed(() => {
  if (total.value === 0) return 0
  const good = qualityStats.value['Ⅰ'] + qualityStats.value['Ⅱ']
  return (good / total.value) * 100
})

const goodRateText = computed(() => `${goodRateValue.value.toFixed(1)}%`)

const warningCount = computed(() => {
  return qualityStats.value['Ⅳ'] + qualityStats.value['Ⅴ'] + qualityStats.value['劣Ⅴ']
})

const stats = computed(() => [
  {
    label: '监测总数',
    value: total.value,
    icon: DataLine,
    color: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    trend: getTrend(statHistory.value.total),
    history: statHistory.value.total
  },
  {
    label: '优良率',
    value: goodRateText.value,
    icon: CircleCheck,
    color: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
    trend: getTrend(statHistory.value.goodRate),
    history: statHistory.value.goodRate
  },
  {
    label: '异常告警',
    value: warningCount.value,
    icon: Warning,
    color: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    trend: getTrend(statHistory.value.warningCount),
    history: statHistory.value.warningCount
  },
  {
    label: '在线断面',
    value: onlineCount.value,
    icon: CircleCheck,
    color: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
    trend: getTrend(statHistory.value.onlineCount),
    history: statHistory.value.onlineCount
  }
])

const loadRealtimeData = async (forceRefresh = false) => {
  realtimeLoadSeq.value += 1
  const seq = realtimeLoadSeq.value
  // 只有在不强制刷新且没有筛选条件时才使用缓存
  if (!forceRefresh && sensorStore.isCacheValid() && sensorStore.cache.sensors.value.length > 0) {
    sensors.value = sensorStore.cache.sensors.value
    total.value = sensorStore.cache.total.value
  }

  try {
    const searchName = filters.value.search
    // 使用缓存store获取数据，筛选时强制刷新
    const res = await sensorStore.getRealtimeData(
      (lastVersion) => apiGetRealtimeData(
        100,
        filters.value.province,
        filters.value.river,
        searchName,
        selectedProvinceChild.value,
        forceRefresh,
        forceRefresh ? '' : lastVersion
      ),
      forceRefresh,
      {
        checkUpdate: true,
        taskKey: JSON.stringify({
          count: 100,
          area_id: filters.value.province,
          river_id: filters.value.river,
          search_name: searchName,
          city_name: selectedProvinceChild.value,
          force_refresh: Boolean(forceRefresh)
        })
      }
    )

    if (disposed.value || seq !== realtimeLoadSeq.value) return

    if (res.code === 200) {
      const newSensors = res.data.sensors || []
      total.value = res.data.total || newSensors.length

      const oldDeviceMap = new Map(sensors.value.map(s => [s.station_id, s]))
      const updatedDevices = []

      newSensors.forEach(newSensor => {
        const oldSensor = oldDeviceMap.get(newSensor.station_id)
        if (!oldSensor) {
          newSensor.justUpdated = true
          newSensor.isNew = true
          updatedDevices.push({ device: newSensor.station_name, type: 'new' })
        } else {
          const hasChanged =
            oldSensor.timestamp !== newSensor.timestamp ||
            oldSensor.water_quality !== newSensor.water_quality ||
            oldSensor.temperature !== newSensor.temperature ||
            oldSensor.ph !== newSensor.ph ||
            oldSensor.dissolved_oxygen !== newSensor.dissolved_oxygen

          if (hasChanged) {
            newSensor.justUpdated = true
            newSensor.isNew = false
            updatedDevices.push({ device: newSensor.station_name, type: 'update' })
          }
        }

        if (newSensor.justUpdated) {
          setTimeout(() => {
            if (newSensor.justUpdated !== undefined) {
              newSensor.justUpdated = false
            }
          }, 3000)
        }
      })

      sensors.value = newSensors

      if (updatedDevices.length > 0) {
        const logTime = new Date().toLocaleTimeString('zh-CN')
        const newCount = updatedDevices.filter(d => d.type === 'new').length
        const updateCount = updatedDevices.filter(d => d.type === 'update').length

        let logMessage = `${logTime} - `
        if (newCount > 0) logMessage += `新增 ${newCount} 个断面`
        if (updateCount > 0) {
          if (newCount > 0) logMessage += '，'
          logMessage += `更新 ${updateCount} 个断面数据`
        }

        updateLog.value.unshift({
          time: logTime,
          message: logMessage,
          newCount,
          updateCount
        })

        if (updateLog.value.length > 20) {
          updateLog.value = updateLog.value.slice(0, 20)
        }
      }

      pushHistory('total', total.value)
      pushHistory('goodRate', goodRateValue.value)
      pushHistory('warningCount', warningCount.value)
      pushHistory('onlineCount', onlineCount.value)

    }
  } catch (error) {
    console.error('加载实时数据失败:', error)
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

const handleManualRefresh = async () => {
  if (isRefreshing.value) return
  if (isManualMode.value) {
    loadRealtimeData(true)
    return
  }
  try {
    await sensorStore.runTask(
      'sync',
      () => syncRealtimeData('national', 0, false, true),
      { taskKey: 'sync:national' }
    )
  } catch (error) {
    console.error('触发国家水质数据刷新失败:', error)
  }
  loadRealtimeData(true)
}

const handleManualFetch = async () => {
  if (isManualFetching.value) return
  isManualFetching.value = true
  try {
    await syncRealtimeData()
    await loadRealtimeData(true)
  } catch (error) {
    console.error('手动获取数据失败:', error)
  } finally {
    isManualFetching.value = false
  }
}

const formatTime = (timestamp) => {
  if (!timestamp) return '-'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatValue = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  return typeof value === 'number' ? value.toFixed(2) : value
}

const metricKeyMap = {
  temperature: ['temperature', 'water_temperature', 'water_temp', 'temp'],
  ph: ['ph', 'ph_value'],
  dissolved_oxygen: ['dissolved_oxygen', 'do', 'do_value', 'dissolvedOxygen'],
  conductivity: ['conductivity', 'ec', 'electrical_conductivity'],
  turbidity: ['turbidity', 'ntu'],
  permanganate_index: ['permanganate_index', 'codmn', 'cod_mn', 'mn_index', 'permanganateIndex'],
  ammonia_nitrogen: ['ammonia_nitrogen', 'nh3_n', 'nh3n', 'ammonia', 'ammoniaNitrogen'],
  total_phosphorus: ['total_phosphorus', 'tp', 'totalPhosphorus'],
  total_nitrogen: ['total_nitrogen', 'tn', 'totalNitrogen'],
  chlorophyll_a: ['chlorophyll_a', 'chlorophyll', 'chla', 'chlorophyllA'],
  algae_density: ['algae_density', 'algae', 'algae_density_cells', 'algaeDensity']
}

const getMetricValue = (item, key) => {
  const keys = metricKeyMap[key] || [key]
  for (const field of keys) {
    const value = item[field]
    if (value !== null && value !== undefined && value !== '') {
      return value
    }
  }
  return null
}

const getQualityClass = (quality) => {
  const classMap = {
    'Ⅰ': 'q1',
    'Ⅱ': 'q2',
    'Ⅲ': 'q3',
    'Ⅳ': 'q4',
    'Ⅴ': 'q5',
    '劣Ⅴ': 'q6'
  }
  return classMap[quality] || 'q0'
}

const isOnline = (timestamp) => {
  if (!timestamp) return false
  const now = new Date()
  const time = new Date(timestamp)
  const diff = (now - time) / 1000 / 60
  return diff < 60
}

onMounted(async () => {
  await loadDataSourceMode()
  await loadAreaOptions()
  if (isManualMode.value) {
    sensorStore.clearCache()
  }
  loadRealtimeData()

  // 添加点击外部关闭下拉的事件监听
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  disposed.value = true
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped lang="scss">
:root {
  --primary: #0984e3;
  --glass: rgba(255, 255, 255, 0.8);
}

$glass-bg: rgba(255, 255, 255, 0.5);
$glass-border: rgba(255, 255, 255, 0.55);
$text-main: #1f2937;
$text-sub: #64748b;

.dashboard-page {
  min-height: 100%;
  background-color: #f0f2f5;
  background-image:
    radial-gradient(at 0% 0%, rgba(9, 132, 227, 0.05) 0px, transparent 50%),
    radial-gradient(at 100% 100%, rgba(108, 92, 231, 0.05) 0px, transparent 50%);
  color: $text-main;
  font-family: "Sora", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  position: relative;
  overflow: hidden;
}

.fluid-bg {
  display: none;
}

.dashboard-content {
  padding: 18px 22px 24px;
  position: relative;
  z-index: 1;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  h1 {
    font-size: 22px;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.6px;
  }

  p {
    color: $text-sub;
    margin: 4px 0 0 0;
    font-size: 12px;
  }

  .top-actions {
    display: flex;
    gap: 10px;

    .action-btn {
      background: $glass-bg;
      border: 1px solid $glass-border;
      border-radius: 10px;
      padding: 6px 10px;
      cursor: pointer;
      color: $text-main;
    }

    .manual-btn {
      padding: 6px 12px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.4px;
    }

    .action-btn:disabled {
      cursor: not-allowed;
      opacity: 0.6;
    }
  }
}

.glass {
  background: $glass-bg;
  backdrop-filter: blur(16px);
  border: 1px solid $glass-border;
  border-radius: 18px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;

  .metric-card {
    padding: 14px 16px;

    .metric-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .label {
        font-size: 12px;
        color: $text-sub;
      }

      .trend-tag {
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 20px;

        &.up {
          background: rgba(34, 197, 94, 0.2);
          color: #16a34a;
        }

        &.down {
          background: rgba(248, 113, 113, 0.2);
          color: #ef4444;
        }

        &.flat {
          background: rgba(148, 163, 184, 0.2);
          color: #64748b;
        }
      }
    }

    .value {
      font-size: 26px;
      margin: 10px 0;
      font-weight: 700;
    }
  }
}

.sparkline-svg {
  width: 100%;
  height: 26px;

  polyline {
    fill: none;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .up {
    stroke: #22c55e;
  }

  .down {
    stroke: #ef4444;
  }

  .flat {
    stroke: #94a3b8;
  }
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.data-panel {
  padding: 14px 16px;
  width: 100%;
  overflow: hidden;

  .panel-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;

    h3 {
      margin: 0;
      font-size: 16px;
    }

  }
}

.panel-filters {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  align-items: center;

  :deep(.el-input__wrapper) {
    background: rgba(255, 255, 255, 0.6);
  }
}

.cascader-wrapper {
  position: relative;
  z-index: 100;
}

.cascader-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  min-width: 110px;
  border-radius: 8px;
  border: 1px solid #c8c8c8;
  background: #d9d9d9;
  color: #1f2937;
  font-weight: 600;
  cursor: pointer;
  transition: box-shadow 0.2s ease;

  &.active {
    box-shadow: 0 0 0 2px rgba(148, 163, 184, 0.4);
  }
}

.cascader-trigger .trigger-text {
  font-size: 13px;
  white-space: nowrap;
}

.cascader-trigger .trigger-arrow {
  margin-left: 10px;
  transition: transform 0.2s ease;

  &.rotated {
    transform: rotate(180deg);
  }
}

.cascader-panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  display: flex;
  background: #ffffff;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.14);
  overflow: hidden;
  min-width: 360px;
}

.cascader-column {
  min-width: 200px;
  max-height: 320px;
  overflow-y: auto;
  padding: 8px;
  border-right: 1px solid #f1f5f9;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: #d1d5db;
    border-radius: 3px;
  }
}

.cascader-main {
  display: grid;
  grid-template-columns: repeat(2, minmax(140px, 1fr));
  gap: 4px;
}

.cascader-main .cascader-item {
  justify-content: space-between;
}

.cascader-sub {
  min-width: 220px;
  border-right: none;
}

.cascader-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 12px;
  border-radius: 6px;
  font-size: 13px;
  color: #1f2937;
  cursor: pointer;
  transition: background 0.2s ease;

  &:hover {
    background: rgba(15, 23, 42, 0.06);
  }

  &.active {
    background: rgba(15, 23, 42, 0.08);
    font-weight: 600;
  }

  .item-arrow {
    color: #c7c7c7;
    font-size: 10px;
  }
}

.segment-search {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  padding-right: 0;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #ffffff;
  min-width: 200px;

  input {
    border: none;
    outline: none;
    width: 100%;
    font-size: 13px;
    color: #1f2937;

    &::placeholder {
      color: #9ca3af;
    }
  }
}

.search-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 12px;
  margin-left: 6px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #ffffff;
  color: #1f2937;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;

  &:hover {
    background: #f9fafb;
    border-color: #c7c7c7;
    transform: translateY(-1px);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  }

  &:active {
    transform: translateY(0);
    box-shadow: none;
  }

  .search-icon {
    margin-right: 6px;
    font-size: 16px;
  }
}

.filter-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 12px;
  padding: 16px 24px;
  font-size: 14px;
  color: #1f2937;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  backdrop-filter: blur(8px);
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;

  &::before {
    content: '';
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid #e5e7eb;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

// 给实时数据列表区域添加相对定位，让加载弹窗可以定位
.realtime-section {
  position: relative;
}

.river-item {
  font-size: 14px;
  padding: 12px 16px;
}

.province-select {
  :deep(.el-input__wrapper) {
    background: #d9d9d9;
    border: 1px solid #c8c8c8;
    box-shadow: none;
    border-radius: 8px;
    font-weight: 600;
    color: #1f2937;
  }

  :deep(.el-input__inner::placeholder) {
    color: #374151;
  }
}

.river-select {
  :deep(.el-input__wrapper) {
    background: #ffffff;
    border: 1px solid #d1d5db;
    box-shadow: none;
    border-radius: 8px;
  }

  :deep(.el-input__inner::placeholder) {
    color: #9ca3af;
  }
}

.custom-list {
  overflow-x: auto;
  overflow-y: hidden;
  width: 100%;
  max-width: 100%;
  padding-bottom: 4px;
  position: relative;

  .list-header {
    display: grid;
    grid-template-columns:
      80px
      100px
      160px
      90px
      130px
      80px
      80px
      110px
      110px
      90px
      140px
      90px
      90px
      90px
      110px
      120px
      60px;
    padding: 6px 0;
    font-size: 11px;
    color: #94a3b8;
    border-bottom: 1px solid rgba(0, 0, 0, 0.05);
    min-width: 1600px;
    width: max-content;
  }

  .list-body {
    position: relative;
    height: clamp(340px, 56vh, 720px);
    overflow: hidden;
    min-width: 1600px;
    width: max-content;
    border-radius: 12px;
    box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.06);

    &.scrolling .list-track {
      animation: slowScrollUp var(--scroll-duration) linear infinite;
    }
  }

  .list-body:hover .list-track {
    animation-play-state: paused;
  }

  .list-track {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .list-item {
    display: grid;
    grid-template-columns:
      80px
      100px
      160px
      90px
      130px
      80px
      80px
      110px
      110px
      90px
      140px
      90px
      90px
      90px
      110px
      120px
      60px;
    padding: 10px 0;
    border-bottom: 1px solid rgba(0, 0, 0, 0.03);
    align-items: center;
    font-size: 12px;
    transition: 0.2s;
    min-width: 1600px;
    width: max-content;

    &:hover {
      background: rgba(255, 255, 255, 0.3);
      transform: scale(1.005);
    }

    .name {
      font-weight: 600;
      color: #1f2937;
    }

    .cell {
      color: #475569;
      font-size: 12px;
    }

    .quality-text {
      &.q1 {
        color: #16a34a;
      }

      &.q2 {
        color: #0284c7;
      }

      &.q3 {
        color: #f59e0b;
      }

      &.q4 {
        color: #f97316;
      }

      &.q5 {
        color: #ef4444;
      }

      &.q6 {
        color: #b91c1c;
      }

      &.q0 {
        color: #94a3b8;
      }
    }

    .indicator {
      width: 6px;
      height: 6px;
      border-radius: 50%;

      &.online {
        background: #22c55e;
      }

      &.offline {
        background: #94a3b8;
      }
    }
  }
}


.update-log {
  padding: 16px 20px;

  .log-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(15, 23, 42, 0.08);

    h4 {
      font-size: 14px;
      font-weight: 600;
      color: #1f2937;
      margin: 0;
    }
  }

  .log-list {
    max-height: 180px;
    overflow-y: auto;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: rgba(24, 144, 255, 0.2);
      border-radius: 2px;
    }
  }

  .log-item {
    display: flex;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid rgba(15, 23, 42, 0.04);
    font-size: 12px;
    transition: all 0.3s ease;

    &:last-child {
      border-bottom: none;
    }

    &.log-item-new {
      background: rgba(22, 163, 74, 0.08);
      padding: 8px 12px;
      border-radius: 6px;
      margin: 0 -12px;

      .log-time {
        color: #16a34a;
        font-weight: 600;
      }

      .log-message {
        color: #1f2937;
        font-weight: 500;
      }

      animation: slideInLeft 0.3s ease-out;
    }

    .log-time {
      color: #6b7280;
      margin-right: 12px;
      min-width: 70px;
      font-family: "Monaco", "Consolas", monospace;
    }

    .log-message {
      color: #6b7280;
      flex: 1;
    }
  }
}

.progress-ring {
  width: 26px;
  height: 26px;

  &.small {
    width: 22px;
    height: 22px;
  }

  .ring-bg {
    fill: none;
    stroke: #e5e7eb;
    stroke-width: 3;
  }

  .ring-fill {
    fill: none;
    stroke: #2563eb;
    stroke-width: 3;
    stroke-linecap: round;
    transition: stroke-dasharray 0.3s ease;
  }
}

.data-updated {
  animation: dataUpdate 1s ease-out;
}

.spinning {
  animation: rotate 1s linear infinite;
}

@keyframes slowScrollUp {
  from {
    transform: translateY(0);
  }
  to {
    transform: translateY(-50%);
  }
}

@keyframes dataUpdate {
  0% {
    background: rgba(82, 196, 26, 0.2);
    color: #2563eb;
  }
  100% {
    background: transparent;
    color: inherit;
  }
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@media (max-width: 1200px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .dashboard-content {
    padding: 14px 12px 18px;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .top-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }

  .panel-filters {
    flex-direction: column;
    align-items: stretch;
  }

  .custom-list {
    .list-header,
    .list-item {
      grid-template-columns:
        80px
        100px
        160px
        130px
        90px
        80px
        80px
        110px
        110px
        90px
        140px
        90px
        90px
        90px
        110px
        120px
        60px;
    }
  }
}
</style>
