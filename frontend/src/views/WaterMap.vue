<template>
  <div class="map-page">
    <div class="map-bg"></div>

    <header class="map-header">
      <div>
        <h1>水域监测地图</h1>
        <p>点击断面标记查看实时数据与趋势</p>
      </div>
      <div class="header-actions">
        <div class="update-tag">
          <span class="dot" :class="{ active: !loading }"></span>
          <span>更新于 {{ lastUpdateText }}</span>
        </div>
        <button class="refresh-btn" type="button" @click="loadRealtime" :disabled="loading">
          <el-icon :class="{ spinning: loading }"><Refresh /></el-icon>
          刷新
        </button>
      </div>
    </header>

    <div class="map-layout">
      <section class="map-panel glass-card">
        <div class="panel-header">
          <div class="panel-actions">
            <el-input
              v-model="search"
              placeholder="搜索断面/城市"
              :prefix-icon="Search"
              size="small"
              @keyup.enter="applySearch"
            />
            <el-select v-model="qualityFilter" size="small" class="quality-select">
              <el-option label="全部水质" value="" />
              <el-option v-for="q in qualityOptions" :key="q" :label="`水质 ${q}`" :value="q" />
            </el-select>
          </div>
        </div>

        <div class="map-shell">
          <div class="map-canvas">
            <!-- 高德地图容器 -->
            <div id="amap-container" class="map-container"></div>

            <div class="map-legend">
              <div v-for="(color, label) in qualityColors" :key="label" class="legend-item">
                <span class="legend-dot" :style="{ background: color }"></span>
                <span>水质 {{ label }}</span>
              </div>
            </div>

            <!-- 数据状态提示 -->
            <div v-if="!mapConfig.hasCoordinates && displaySensors.length" class="map-status-tip">
              正在获取地理坐标...
            </div>

            <!-- 地图加载错误提示 -->
            <div v-if="mapLoadError" class="map-status-tip map-error-tip">
              {{ mapLoadError }} - 请检查控制台查看详细URL
            </div>
          </div>

          <div v-if="loading" class="map-loading">数据加载中...</div>
          <div v-if="!loading && !displaySensors.length" class="map-empty">暂无可展示的断面数据</div>
        </div>
      </section>
    </div>

    <el-dialog
      v-model="sensorDialogVisible"
      width="860px"
      top="10vh"
      class="sensor-dialog"
      :destroy-on-close="true"
      :close-on-click-modal="true"
      @opened="handleDialogOpened"
      @closed="handleDialogClosed"
    >
      <template #header>
        <div class="dialog-title">
          <div>
            <h3>{{ selectedSensor?.station_name || selectedSensor?.station_id || '断面详情' }}</h3>
            <p>{{ selectedSensor?.province || '-' }} · {{ selectedSensor?.river_basin || '未知流域' }}</p>
          </div>
          <span class="quality-chip" :style="{ background: qualityColors[selectedSensor?.water_quality] || '#94a3b8' }">
            {{ selectedSensor?.water_quality ? `水质 ${selectedSensor.water_quality}` : '无水质' }}
          </span>
        </div>
      </template>

      <div class="metric-grid">
        <div class="metric-item">
          <span>水温</span>
          <strong>{{ formatValue(selectedSensor?.temperature, '°C') }}</strong>
        </div>
        <div class="metric-item">
          <span>pH</span>
          <strong>{{ formatValue(selectedSensor?.ph) }}</strong>
        </div>
        <div class="metric-item">
          <span>溶解氧</span>
          <strong>{{ formatValue(selectedSensor?.dissolved_oxygen, 'mg/L') }}</strong>
        </div>
        <div class="metric-item">
          <span>电导率</span>
          <strong>{{ formatValue(selectedSensor?.conductivity, 'μS/cm') }}</strong>
        </div>
        <div class="metric-item">
          <span>浊度</span>
          <strong>{{ formatValue(selectedSensor?.turbidity, 'NTU') }}</strong>
        </div>
        <div class="metric-item">
          <span>数据时间</span>
          <strong>{{ formatTime(selectedSensor?.timestamp) }}</strong>
        </div>
      </div>

      <div class="trend-card">
        <div class="trend-header">
          <span>近 24h 趋势</span>
          <button class="ghost-btn" type="button" @click="loadHistory" :disabled="historyLoading || !selectedId">
            {{ historyLoading ? '加载中...' : '刷新趋势' }}
          </button>
        </div>
        <div ref="historyChartRef" class="trend-chart"></div>
        <p v-if="!historySeries.length && !historyLoading" class="trend-empty">暂无历史趋势数据</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { Refresh, Search } from '@element-plus/icons-vue'
import { getRealtimeData, getHistoricalData } from '@/api/sensors'
import { createRealtimeSocket } from '@/utils/realtimeSocket'

const loading = ref(false)
const sensors = ref([])
const search = ref('')
const qualityFilter = ref('')
const selectedId = ref('')
const lastUpdate = ref('')
const sensorDialogVisible = ref(false)

const historyChartRef = ref(null)
const historySeries = ref([])
const historyLoading = ref(false)
let historyChart = null
let realtimeSocket = null
let realtimeRefreshTimer = null

// 高德地图实例
let amapInstance = null
const mapLoadError = ref(null)

const handleMapError = (e) => {
  console.error('地图加载失败')
  mapLoadError.value = '地图加载失败'
}

// 初始化高德地图
const initAmap = () => {
  if (amapInstance) return

  // 检查高德地图API是否已加载
  if (!window.AMap) {
    console.error('高德地图API未加载')
    return
  }

  try {
    // 解析中心点坐标
    const centerParts = mapConfig.value.center.split(',')
    const centerLng = parseFloat(centerParts[0])
    const centerLat = parseFloat(centerParts[1])

    console.log('=== 初始化高德地图 ===')
    console.log('中心点:', mapConfig.value.center, '→', [centerLng, centerLat])
    console.log('缩放级别:', mapConfig.value.zoom)

    // 创建地图实例
    amapInstance = new AMap.Map('amap-container', {
      zoom: mapConfig.value.zoom,
      center: [centerLng, centerLat],
      mapStyle: 'amap://styles/normal',
      viewMode: '2D'
    })

    // 添加工具栏（部分加载方式下需要插件式加载）
    if (window.AMap && typeof window.AMap.plugin === 'function') {
      window.AMap.plugin(['AMap.Scale', 'AMap.ToolBar'], () => {
        if (window.AMap.Scale) amapInstance.addControl(new window.AMap.Scale())
        if (window.AMap.ToolBar) amapInstance.addControl(new window.AMap.ToolBar())
      })
    } else if (window.AMap?.Scale && window.AMap?.ToolBar) {
      amapInstance.addControl(new window.AMap.Scale())
      amapInstance.addControl(new window.AMap.ToolBar())
    }

    console.log('高德地图初始化成功')
    updateMapMarkers()
  } catch (error) {
    console.error('高德地图初始化失败:', error)
  }
}

// 更新地图标记
const updateMapMarkers = () => {
  if (!amapInstance) return

  // 清除现有标记
  amapInstance.clearMap()

  // 添加新标记
  const sensorsWithCoords = displaySensors.value.filter(s => s.longitude && s.latitude)

  console.log('=== 添加标记点到高德地图 ===')
  console.log('标记点数量:', sensorsWithCoords.length)
  sensorsWithCoords.slice(0, 5).forEach(s => {
    console.log(`${s.station_name}: [${s.longitude}, ${s.latitude}] 省份:${s.province}`)
  })

  const markers = []
  const coordCounts = new Map()
  const coordUsed = new Map()

  sensorsWithCoords.forEach(sensor => {
    const lng = parseFloat(sensor.longitude)
    const lat = parseFloat(sensor.latitude)
    if (isNaN(lng) || isNaN(lat)) return
    const key = `${lng.toFixed(6)},${lat.toFixed(6)}`
    coordCounts.set(key, (coordCounts.get(key) || 0) + 1)
  })

  sensorsWithCoords.forEach(sensor => {
    // 确保坐标是数字类型
    const lng = parseFloat(sensor.longitude)
    const lat = parseFloat(sensor.latitude)

    if (isNaN(lng) || isNaN(lat)) {
      console.warn(`坐标无效: ${sensor.station_name}`, sensor.longitude, sensor.latitude)
      return
    }

    const key = `${lng.toFixed(6)},${lat.toFixed(6)}`
    const total = coordCounts.get(key) || 1
    const used = coordUsed.get(key) || 0
    coordUsed.set(key, used + 1)

    let markerLng = lng
    let markerLat = lat

    if (total > 1) {
      const angle = (used / total) * Math.PI * 2
      const ring = Math.floor(used / 8)
      const radius = 0.0005 * (1 + ring)
      markerLng = lng + Math.cos(angle) * radius
      markerLat = lat + Math.sin(angle) * radius
    }

    const marker = new AMap.Marker({
      position: [markerLng, markerLat],
      title: sensor.station_name || sensor.station_id,
      content: `<div style="background:${qualityColors[sensor.water_quality] || '#38bdf8'};width:20px;height:20px;border-radius:50%;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);cursor:pointer;"></div>`,
      offset: new AMap.Pixel(-10, -10)
    })

    // 点击事件
    marker.on('click', () => {
      selectSensor(sensor)
    })

    markers.push(marker)
  })

  if (markers.length > 0) {
    amapInstance.add(markers)
    amapInstance.setFitView(markers)
  }
}

const handleMapLoad = () => {
  console.log('地图加载成功')
  mapLoadError.value = null
}

const qualityColors = {
  'Ⅰ': '#16a34a',
  'Ⅱ': '#22c55e',
  'Ⅲ': '#facc15',
  'Ⅳ': '#fb923c',
  'Ⅴ': '#ef4444',
  '劣Ⅴ': '#b91c1c'
}

const qualityOptions = Object.keys(qualityColors)

const lastUpdateText = computed(() => {
  if (!lastUpdate.value) return '-'
  try {
    return new Date(lastUpdate.value).toLocaleString('zh-CN')
  } catch (error) {
    return lastUpdate.value
  }
})

const displaySensors = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return sensors.value.filter(sensor => {
    const matchQuality = !qualityFilter.value || sensor.water_quality === qualityFilter.value
    const matchKeyword =
      !keyword ||
      `${sensor.station_name || ''}${sensor.station_id || ''}${sensor.city || ''}${sensor.province || ''}`
        .toLowerCase()
        .includes(keyword)
    return matchQuality && matchKeyword
  })
})

const selectedSensor = computed(() =>
  sensors.value.find(sensor => sensor.station_id === selectedId.value)
)

const mapPoints = computed(() => {
  return displaySensors.value.map(sensor => {
    const key = sensor.station_id || sensor.station_name || sensor.location || 'unknown'
    const position = resolvePosition(key, sensor)
    return {
      key,
      ...sensor,
      x: position.x,
      y: position.y,
      longitude: sensor.longitude,
      latitude: sensor.latitude
    }
  })
})

// 高德地图配置（来自 Vite 环境变量）
const AMAP_API_KEY = import.meta.env.VITE_AMAP_JS_API_KEY || import.meta.env.VITE_AMAP_API_KEY || ''
const AMAP_SECURITY_CODE = import.meta.env.VITE_AMAP_SECURITY_CODE || ''

// 计算地图配置
const mapConfig = computed(() => {
  const sensorsWithCoords = displaySensors.value.filter(s => s.longitude && s.latitude)

  if (sensorsWithCoords.length === 0) {
    // 没有经纬度数据时，使用默认中心点（北京）
    return {
      center: '116.397428,39.90923',
      zoom: 10,
      hasCoordinates: false
    }
  }

  // 计算中心点
  const centerLng = sensorsWithCoords.reduce((sum, s) => sum + s.longitude, 0) / sensorsWithCoords.length
  const centerLat = sensorsWithCoords.reduce((sum, s) => sum + s.latitude, 0) / sensorsWithCoords.length

  // 计算边界以确定合适的缩放级别
  const minLng = Math.min(...sensorsWithCoords.map(s => s.longitude))
  const maxLng = Math.max(...sensorsWithCoords.map(s => s.longitude))
  const minLat = Math.min(...sensorsWithCoords.map(s => s.latitude))
  const maxLat = Math.max(...sensorsWithCoords.map(s => s.latitude))

  const lngDiff = maxLng - minLng
  const latDiff = maxLat - minLat
  const maxDiff = Math.max(lngDiff, latDiff)

  // 根据经纬度范围计算缩放级别
  let zoom = 10
  if (maxDiff < 0.01) zoom = 15
  else if (maxDiff < 0.05) zoom = 13
  else if (maxDiff < 0.1) zoom = 11
  else if (maxDiff < 0.5) zoom = 9
  else if (maxDiff < 1) zoom = 7
  else if (maxDiff < 2) zoom = 6
  else if (maxDiff < 5) zoom = 5
  else zoom = 4

  return {
    center: `${centerLng.toFixed(6)},${centerLat.toFixed(6)}`,
    zoom,
    hasCoordinates: true
  }
})

// 生成高德静态地图URL
const amapUrl = computed(() => {
  const sensorsWithCoords = displaySensors.value.filter(s => s.longitude && s.latitude)

  if (sensorsWithCoords.length === 0) {
    // 没有经纬度数据时，使用默认地图（不添加markers参数）
    return `https://restapi.amap.com/v3/staticmap?location=${mapConfig.value.center}&zoom=${mapConfig.value.zoom}&size=1024*768&scale=2&key=${AMAP_API_KEY}`
  }

  // 有经纬度数据时，添加所有标记点（最多10个，避免URL过长）
  const markers = sensorsWithCoords
    .slice(0, 10)
    .map(s => `${s.longitude.toFixed(6)},${s.latitude.toFixed(6)}`)
    .join('|')

  // 使用正确的 markers 格式：size,颜色,标注内容:坐标1|坐标2
  return `https://restapi.amap.com/v3/staticmap?location=${mapConfig.value.center}&zoom=${mapConfig.value.zoom}&size=1024*768&scale=2&markers=-1,0xFF0000,A:${markers}&key=${AMAP_API_KEY}`
})

const positionCache = new Map()

const hashCode = (value, seed = 0) => {
  let hash = seed
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

const resolvePosition = (key, sensor) => {
  if (positionCache.has(key)) return positionCache.get(key)

  // 如果有经纬度数据，计算相对位置（0-100%）
  if (sensor?.longitude && sensor?.latitude) {
    // 获取所有有经纬度的传感器
    const sensorsWithCoords = displaySensors.value.filter(s => s.longitude && s.latitude)

    if (sensorsWithCoords.length > 0) {
      const minLng = Math.min(...sensorsWithCoords.map(s => s.longitude))
      const maxLng = Math.max(...sensorsWithCoords.map(s => s.longitude))
      const minLat = Math.min(...sensorsWithCoords.map(s => s.latitude))
      const maxLat = Math.max(...sensorsWithCoords.map(s => s.latitude))

      const lngRange = maxLng - minLng || 1
      const latRange = maxLat - minLat || 1

      // 计算相对位置（留出边距）
      const x = 10 + ((sensor.longitude - minLng) / lngRange) * 80
      const y = 15 + ((sensor.latitude - minLat) / latRange) * 70

      const position = { x, y }
      positionCache.set(key, position)
      return position
    }
  }

  // 没有经纬度数据时，使用hash算法随机分布
  const base = key || 'default'
  const x = 8 + (hashCode(base, 23) % 84)
  const y = 12 + (hashCode(base, 71) % 76)
  const position = { x, y }
  positionCache.set(key, position)
  return position
}

const applySearch = () => {
  if (!displaySensors.value.find(sensor => sensor.station_id === selectedId.value)) {
    selectedId.value = displaySensors.value[0]?.station_id || ''
  }
}

const loadRealtime = async () => {
  loading.value = true
  try {
    // 地图页需要尽量展示全量断面（否则会看起来“很多地方没标点”）
    const res = await getRealtimeData(5000)
    const data = res?.data?.sensors || []
    sensors.value = data
    lastUpdate.value = res?.data?.timestamp || ''
    if (!selectedId.value && data.length) {
      selectedId.value = data[0].station_id
    }
  } catch (error) {
    sensors.value = []
  } finally {
    loading.value = false
  }
}

const scheduleRealtimeRefresh = () => {
  if (realtimeRefreshTimer) {
    clearTimeout(realtimeRefreshTimer)
  }
  realtimeRefreshTimer = setTimeout(() => {
    realtimeRefreshTimer = null
    loadRealtime()
  }, 250)
}

const selectSensor = (sensor) => {
  if (!sensor.station_id) return
  selectedId.value = sensor.station_id
  if (!sensorDialogVisible.value) {
    sensorDialogVisible.value = true
    return
  }

  // 输出调试信息
  console.log('=== 选中的断面 ===')
  console.log('名称:', sensor.station_name)
  console.log('经度:', sensor.longitude)
  console.log('纬度:', sensor.latitude)
  console.log('省份:', sensor.province)
  console.log('城市:', sensor.city)
  console.log('前端计算位置:', `x=${sensor.x}%, y=${sensor.y}%`)

  loadHistory()
}

const formatValue = (value, unit = '') => {
  if (value === null || value === undefined || value === '') return '--'
  const formatted = Number.isFinite(Number(value)) ? Number(value).toFixed(2) : value
  return unit ? `${formatted} ${unit}` : formatted
}

const formatTime = (value) => {
  if (!value) return '--'
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch (error) {
    return value
  }
}

const initChart = async () => {
  await nextTick()
  if (!historyChartRef.value) return
  historyChart?.dispose()
  historyChart = echarts.init(historyChartRef.value)
  window.removeEventListener('resize', resizeChart)
  window.addEventListener('resize', resizeChart)
  updateChart()
}

const resizeChart = () => {
  historyChart?.resize()
}

const loadHistory = async () => {
  if (!selectedId.value) return
  historyLoading.value = true
  try {
    const res = await getHistoricalData(selectedId.value, 24)
    historySeries.value = res?.data?.data || []
    updateChart()
  } catch (error) {
    historySeries.value = []
    updateChart()
  } finally {
    historyLoading.value = false
  }
}

const updateChart = () => {
  if (!historyChart) return
  const times = historySeries.value.map(item => item.time)
  const temperature = historySeries.value.map(item => item.temperature)
  const dissolvedOxygen = historySeries.value.map(item => item.dissolved_oxygen)
  const ph = historySeries.value.map(item => item.ph)

  historyChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['水温', '溶解氧', 'pH'] },
    grid: { left: 20, right: 20, top: 30, bottom: 20, containLabel: true },
    xAxis: { type: 'category', data: times, axisLabel: { color: '#64748b' } },
    yAxis: { type: 'value', axisLabel: { color: '#64748b' } },
    series: [
      {
        name: '水温',
        type: 'line',
        smooth: true,
        data: temperature,
        itemStyle: { color: '#38bdf8' },
        areaStyle: { color: 'rgba(56, 189, 248, 0.12)' }
      },
      {
        name: '溶解氧',
        type: 'line',
        smooth: true,
        data: dissolvedOxygen,
        itemStyle: { color: '#4ade80' },
        areaStyle: { color: 'rgba(74, 222, 128, 0.12)' }
      },
      {
        name: 'pH',
        type: 'line',
        smooth: true,
        data: ph,
        itemStyle: { color: '#fb923c' },
        areaStyle: { color: 'rgba(251, 146, 60, 0.12)' }
      }
    ]
  })
}

const handleDialogOpened = async () => {
  await initChart()
  await loadHistory()
}

const handleDialogClosed = () => {
  window.removeEventListener('resize', resizeChart)
  historyChart?.dispose()
  historyChart = null
  historySeries.value = []
}

onMounted(async () => {
  // 设置高德地图安全密钥
  window._AMapSecurityConfig = {
    securityJsCode: AMAP_SECURITY_CODE || '',
  }

  // 动态加载高德地图API
  if (!window.AMap) {
    const script = document.createElement('script')
    script.type = 'text/javascript'
    // 加载坐标转换插件
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${AMAP_API_KEY}&plugin=AMap.Converter`
    script.onload = () => {
      console.log('高德地图API加载完成')
      initAmap()
    }
    script.onerror = () => {
      console.error('高德地图API加载失败')
    }
    document.head.appendChild(script)
  } else {
    initAmap()
  }

  loadRealtime()

  realtimeSocket = createRealtimeSocket({
    onMessage: (message) => {
      if (!message || message.event !== 'realtime.snapshot.updated') return
      scheduleRealtimeRefresh()
    }
  })
  realtimeSocket.connect()
})

watch(displaySensors, (next) => {
  if (!next.length) return
  const exists = next.some(sensor => sensor.station_id === selectedId.value)
  if (!exists) {
    selectedId.value = next[0].station_id || ''
  }

  // 更新地图标记
  updateMapMarkers()
})

onUnmounted(() => {
  if (realtimeRefreshTimer) {
    clearTimeout(realtimeRefreshTimer)
    realtimeRefreshTimer = null
  }
  realtimeSocket?.close()
  // 销毁地图实例
  if (amapInstance) {
    amapInstance.destroy()
    amapInstance = null
  }

  window.removeEventListener('resize', resizeChart)
  historyChart?.dispose()
  historyChart = null
})
</script>

<style scoped lang="scss">
.map-page {
  height: 100vh;
  position: relative;
  padding: 20px 22px 22px;
  font-family: "DM Sans", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #0f172a;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.map-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 20%, rgba(14, 165, 233, 0.16), transparent 45%),
    radial-gradient(circle at 80% 30%, rgba(16, 185, 129, 0.16), transparent 50%),
    linear-gradient(140deg, #f8fafc 0%, #eef6ff 45%, #f1f5f9 100%);
  z-index: 0;
}

.map-header {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;

  h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 700;
  }

  p {
    margin: 6px 0 0;
    color: #64748b;
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.update-tag {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(226, 232, 240, 0.7);
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.06);
  font-size: 12px;
  color: #475569;

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: #cbd5f5;

    &.active {
      background: #22c55e;
      box-shadow: 0 0 8px rgba(34, 197, 94, 0.6);
    }
  }
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  padding: 8px 14px;
  border-radius: 12px;
  background: rgba(14, 165, 233, 0.12);
  color: #0369a1;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.refresh-btn:not(:disabled):hover {
  background: rgba(14, 165, 233, 0.2);
}

.refresh-btn .spinning {
  animation: spin 1s linear infinite;
}

.map-layout {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  margin-top: 22px;
  min-height: 0;
}

.glass-card {
  background: rgba(255, 255, 255, 0.86);
  border-radius: 20px;
  border: 1px solid rgba(226, 232, 240, 0.85);
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.1);
  backdrop-filter: blur(12px);
}

.map-panel {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 18px;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  justify-content: flex-end;
}

.quality-select {
  min-width: 120px;
}

.map-shell {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.map-canvas {
  position: relative;
  width: 100%;
  height: 100%;
  flex: 1;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(226, 232, 240, 0.7);
}

.map-container {
  width: 100%;
  height: 100%;
  min-height: 0;
}

.map-points {
  position: absolute;
  inset: 0;
}

.map-point {
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  transform: translate(-50%, -50%);
  border: none;
  background: transparent;
  cursor: pointer;
}

.map-point .pulse {
  position: absolute;
  inset: -10px;
  border-radius: 999px;
  opacity: 0.2;
  animation: pulse 2.4s ease-in-out infinite;
}

.map-point .dot {
  position: absolute;
  inset: 4px;
  border-radius: 999px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.2);
}

.map-point.active .pulse {
  opacity: 0.4;
}

.map-legend {
  position: absolute;
  left: 16px;
  bottom: 14px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.7);
  font-size: 12px;
  color: #475569;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.map-status-tip {
  position: absolute;
  top: 16px;
  right: 16px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.7);
  font-size: 12px;
  color: #64748b;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.1);
}

.map-error-tip {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: #dc2626;
}

.map-loading,
.map-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: #64748b;
}

.dialog-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;

  h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 700;
  }

  p {
    margin: 6px 0 0;
    color: #64748b;
    font-size: 12px;
  }
}

.quality-chip {
  padding: 6px 12px;
  border-radius: 999px;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.metric-grid {
  margin-top: 4px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.metric-item {
  padding: 12px;
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.8);
  border: 1px solid rgba(226, 232, 240, 0.7);
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: #64748b;

  strong {
    font-size: 16px;
    color: #0f172a;
  }
}

.trend-card {
  margin-top: 16px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(226, 232, 240, 0.7);
}

.trend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #475569;
  margin-bottom: 8px;
}

.trend-chart {
  width: 100%;
  height: 220px;
}

.trend-empty {
  text-align: center;
  color: #94a3b8;
  font-size: 12px;
  margin: 6px 0 0;
}

.ghost-btn {
  border: 1px solid rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.1);
  color: #1d4ed8;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  cursor: pointer;
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

@keyframes pulse {
  0% {
    transform: scale(0.7);
  }
  50% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(0.7);
  }
}

@media (max-width: 1100px) {
  .trend-chart {
    height: 200px;
  }
}

@media (max-width: 700px) {
  .map-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .panel-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .panel-actions {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }
}
</style>
