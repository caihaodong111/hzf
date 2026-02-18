<template>
  <div class="dashboard-page">
    <!-- 平台标题栏 -->
    <div class="platform-header">
      <div class="platform-title">
        <h1>国家水质自动综合监管平台</h1>
        <p>National Water Quality Automatic Monitoring Platform</p>
      </div>
      <div class="header-controls">
        <div class="refresh-info">
          <div class="auto-refresh-control">
            <el-switch
              v-model="autoRefresh"
              @change="toggleAutoRefresh"
              size="small"
              inline-prompt
              active-text="自动"
              inactive-text="手动"
            />
            <el-select v-model="refreshInterval" size="small" style="width: 90px; margin-left: 8px" @change="onIntervalChange" :disabled="!autoRefresh">
              <el-option label="10秒" :value="10" />
              <el-option label="30秒" :value="30" />
              <el-option label="60秒" :value="60" />
              <el-option label="5分钟" :value="300" />
            </el-select>
          </div>
          <div class="update-status">
            <span class="last-update">更新时间: {{ lastUpdateTime }}</span>
            <span v-if="autoRefresh" class="next-update">下次: {{ nextUpdateTime }}</span>
          </div>
          <el-button
            type="primary"
            :icon="refreshIcon"
            :loading="loading && isManualRefresh"
            @click="manualRefresh"
            circle
            size="small"
            :class="{ 'refreshing': isRefreshing }"
          />
        </div>
      </div>
    </div>

    <!-- 刷新进度条 -->
    <div v-if="autoRefresh" class="refresh-progress">
      <div class="progress-bar" :style="{ width: progressPercent + '%' }"></div>
    </div>

    <!-- 数据统计卡片 -->
    <div class="stats-cards">
      <div class="stat-card stat-total">
        <div class="stat-icon">
          <el-icon><icon-data /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ total }}</div>
          <div class="stat-label">监测断面总数</div>
        </div>
      </div>
      <div class="stat-card stat-excellent">
        <div class="stat-icon">
          <el-icon><icon-success /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ qualityStats.Ⅰ + qualityStats.Ⅱ }}</div>
          <div class="stat-label">优良(Ⅰ-Ⅱ类)</div>
        </div>
      </div>
      <div class="stat-card stat-good">
        <div class="stat-icon">
          <el-icon><icon-warning /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ qualityStats.Ⅲ }}</div>
          <div class="stat-label">良好(Ⅲ类)</div>
        </div>
      </div>
      <div class="stat-card stat-poor">
        <div class="stat-icon">
          <el-icon><icon-close /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ qualityStats.Ⅳ + qualityStats.Ⅴ + qualityStats.劣Ⅴ }}</div>
          <div class="stat-label">污染(Ⅳ-劣Ⅴ类)</div>
        </div>
      </div>
      <div class="stat-card stat-online">
        <div class="stat-icon">
          <el-icon><icon-circle-check /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ onlineCount }}</div>
          <div class="stat-label">在线断面</div>
        </div>
      </div>
    </div>

    <!-- 筛选条件 -->
    <div class="filter-card glass-card">
      <el-form :inline="true">
        <el-form-item label="省份:">
          <el-select v-model="filters.province" placeholder="全部省份" style="width: 150px" clearable @change="loadRealtimeData">
            <el-option label="全国" value="" />
            <el-option v-for="item in provinces" :key="item.code" :label="item.name" :value="item.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="流域:">
          <el-select v-model="filters.river" placeholder="全部流域" style="width: 150px" clearable @change="loadRealtimeData">
            <el-option label="所有流域" value="" />
            <el-option v-for="item in rivers" :key="item.code" :label="item.name" :value="item.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索:">
          <el-input
            v-model="filters.search"
            placeholder="输入断面名称"
            style="width: 200px"
            @keyup.enter="loadRealtimeData"
            clearable
          >
            <template #append>
              <el-button :icon="searchIcon" @click="loadRealtimeData" />
            </template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadRealtimeData">查询</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 数据表格 -->
    <div class="data-table glass-card">
      <el-table
        :data="sensors"
        style="width: 100%"
        v-loading="loading && isManualRefresh"
        :height="tableHeight"
        :row-class-name="getRowClassName"
        stripe
        :row-key="getRowKey"
      >
        <el-table-column prop="province" label="省份" width="100" fixed />
        <el-table-column prop="river_basin" label="流域" width="120" fixed />
        <el-table-column prop="device_name" label="断面名称" width="180" fixed>
          <template #default="{ row }">
            <div class="station-name" :class="{ 'data-updated': row.justUpdated }">{{ row.device_name }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="timestamp" label="监测时间" width="160">
          <template #default="{ row }">
            <span :class="{ 'data-updated': row.justUpdated }">{{ formatTime(row.timestamp) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="water_quality" label="水质类别" width="90" align="center">
          <template #default="{ row }">
            <span class="quality-badge" :class="getQualityClass(row.water_quality)">
              {{ row.water_quality || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="temperature" label="水温(℃)" width="100" align="right">
          <template #default="{ row }">
            <span :class="[getValueClass('temperature', row.temperature), { 'data-updated': row.justUpdated }]">
              {{ formatValue(row.temperature) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="ph" label="pH" width="80" align="right">
          <template #default="{ row }">
            <span :class="[getValueClass('ph', row.ph), { 'data-updated': row.justUpdated }]">
              {{ formatValue(row.ph) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="dissolved_oxygen" label="溶解氧(mg/L)" width="120" align="right">
          <template #default="{ row }">
            <span :class="[getValueClass('dissolved_oxygen', row.dissolved_oxygen), { 'data-updated': row.justUpdated }]">
              {{ formatValue(row.dissolved_oxygen) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="conductivity" label="电导率(μS/cm)" width="130" align="right">
          <template #default="{ row }">
            <span :class="[getValueClass('conductivity', row.conductivity), { 'data-updated': row.justUpdated }]">
              {{ formatValue(row.conductivity) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="turbidity" label="浊度(NTU)" width="110" align="right">
          <template #default="{ row }">
            <span :class="[getValueClass('turbidity', row.turbidity), { 'data-updated': row.justUpdated }]">
              {{ formatValue(row.turbidity) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <div class="status-indicator" :class="{ 'status-online': isOnline(row.timestamp) }">
              <span class="status-dot"></span>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="table-footer">
        <div class="total-info">
          共 {{ total }} 条记录，当前显示 {{ sensors.length }} 条
          <span v-if="justUpdatedCount > 0" class="update-hint">
            ，刚刚更新 {{ justUpdatedCount }} 条
          </span>
        </div>
        <div class="auto-refresh-status">
          <el-tag :type="autoRefresh ? 'success' : 'info'" size="small">
            {{ autoRefresh ? '自动刷新中' : '手动模式' }}
          </el-tag>
          <span class="refresh-interval">每 {{ refreshInterval }} 秒</span>
        </div>
      </div>
    </div>

    <!-- 更新日志 -->
    <div v-if="updateLog.length > 0" class="update-log glass-card">
      <div class="log-header">
        <h4>数据更新日志</h4>
        <el-button size="small" text @click="updateLog = []">清空</el-button>
      </div>
      <div class="log-list">
        <div
          v-for="(log, index) in updateLog"
          :key="index"
          class="log-item"
          :class="{ 'log-item-new': index === 0 }"
        >
          <span class="log-time">{{ log.time }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getRealtimeData } from '@/api/sensors'
import { Refresh, Search, DataLine, SuccessFilled, Warning, CircleClose, CircleCheck } from '@element-plus/icons-vue'

// Icons
const refreshIcon = Refresh
const searchIcon = Search
const iconData = DataLine
const iconSuccess = SuccessFilled
const iconWarning = Warning
const iconClose = CircleClose
const iconCircleCheck = CircleCheck

const loading = ref(false)
const sensors = ref([])
const total = ref(0)
const lastUpdateTime = ref('-')
const nextUpdateTime = ref('-')
const tableHeight = ref(600)
const autoRefresh = ref(true)
const refreshInterval = ref(30) // 默认30秒刷新一次
const progressPercent = ref(0)
const isManualRefresh = ref(false)
const isRefreshing = ref(false)
const updateLog = ref([]) // 更新日志
let refreshTimer = null
let progressTimer = null
let elapsedSinceRefresh = 0

// 筛选条件
const filters = ref({
  province: '',
  river: '',
  search: ''
})

// 省份列表
const provinces = [
  { code: '110000', name: '北京市' },
  { code: '120000', name: '天津市' },
  { code: '130000', name: '河北省' },
  { code: '140000', name: '山西省' },
  { code: '150000', name: '内蒙古自治区' },
  { code: '210000', name: '辽宁省' },
  { code: '220000', name: '吉林省' },
  { code: '230000', name: '黑龙江省' },
  { code: '310000', name: '上海市' },
  { code: '320000', name: '江苏省' },
  { code: '330000', name: '浙江省' },
  { code: '340000', name: '安徽省' },
  { code: '350000', name: '福建省' },
  { code: '360000', name: '江西省' },
  { code: '370000', name: '山东省' },
  { code: '410000', name: '河南省' },
  { code: '420000', name: '湖北省' },
  { code: '430000', name: '湖南省' },
  { code: '440000', name: '广东省' },
  { code: '450000', name: '广西壮族自治区' },
  { code: '460000', name: '海南省' },
  { code: '500000', name: '重庆市' },
  { code: '510000', name: '四川省' },
  { code: '520000', name: '贵州省' },
  { code: '530000', name: '云南省' },
  { code: '540000', name: '西藏自治区' },
  { code: '610000', name: '陕西省' },
  { code: '620000', name: '甘肃省' },
  { code: '630000', name: '青海省' },
  { code: '640000', name: '宁夏回族自治区' },
  { code: '650000', name: '新疆维吾尔自治区' }
]

// 流域列表
const rivers = [
  { code: '1100000000', name: '长江流域' },
  { code: '0900000000', name: '黄河流域' },
  { code: '1500000000', name: '珠江流域' },
  { code: '0200000000', name: '松花江流域' },
  { code: '1000000000', name: '淮河流域' },
  { code: '6010000000', name: '海河流域' },
  { code: '0500000000', name: '辽河流域' },
  { code: '1200000000', name: '太湖流域' }
]

// 计算刚刚更新的记录数
const justUpdatedCount = computed(() => {
  return sensors.value.filter(s => s.justUpdated).length
})

// 水质类别统计
const qualityStats = computed(() => {
  const stats = { 'Ⅰ': 0, 'Ⅱ': 0, 'Ⅲ': 0, 'Ⅳ': 0, 'Ⅴ': 0, '劣Ⅴ': 0, '': 0 }
  sensors.value.forEach(s => {
    const quality = s.water_quality || ''
    if (quality in stats) {
      stats[quality]++
    }
  })
  return stats
})

// 在线断面数量
const onlineCount = computed(() => {
  return sensors.value.filter(s => isOnline(s.timestamp)).length
})

// 获取行唯一标识
const getRowKey = (row) => {
  return row.device_id || row.device_name
}

// 加载实时数据
const loadRealtimeData = async (isAuto = false) => {
  if (!isAuto) {
    loading.value = true
    isManualRefresh.value = true
  }
  isRefreshing.value = true

  try {
    const res = await getRealtimeData(
      100, // 获取100条数据
      filters.value.province,
      filters.value.river,
      filters.value.search
    )
    if (res.code === 200) {
      const newSensors = res.data.sensors || []
      total.value = res.data.total || newSensors.length
      lastUpdateTime.value = new Date().toLocaleTimeString('zh-CN')

      // 标记数据变化
      const oldDeviceMap = new Map(sensors.value.map(s => [s.device_id, s]))
      const updatedDevices = []

      newSensors.forEach(newSensor => {
        const oldSensor = oldDeviceMap.get(newSensor.device_id)
        // 检查是否是新数据或数据有更新
        if (!oldSensor) {
          // 新设备
          newSensor.justUpdated = true
          newSensor.isNew = true
          updatedDevices.push({ device: newSensor.device_name, type: 'new' })
        } else {
          // 检查数据是否有变化
          const hasChanged =
            oldSensor.timestamp !== newSensor.timestamp ||
            oldSensor.water_quality !== newSensor.water_quality ||
            oldSensor.temperature !== newSensor.temperature ||
            oldSensor.ph !== newSensor.ph ||
            oldSensor.dissolved_oxygen !== newSensor.dissolved_oxygen

          if (hasChanged) {
            newSensor.justUpdated = true
            newSensor.isNew = false
            updatedDevices.push({ device: newSensor.device_name, type: 'update' })
          }
        }

        // 2秒后移除高亮标记
        if (newSensor.justUpdated) {
          setTimeout(() => {
            if (newSensor.justUpdated !== undefined) {
              newSensor.justUpdated = false
            }
          }, 3000)
        }
      })

      // 更新传感器数据
      sensors.value = newSensors

      // 添加更新日志
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

        // 只保留最近20条日志
        if (updateLog.value.length > 20) {
          updateLog.value = updateLog.value.slice(0, 20)
        }
      }

      // 重置进度
      elapsedSinceRefresh = 0
      progressPercent.value = 0
    }
  } catch (error) {
    console.error('加载实时数据失败:', error)
  } finally {
    loading.value = false
    isManualRefresh.value = false
    isRefreshing.value = false
  }
}

// 手动刷新
const manualRefresh = () => {
  loadRealtimeData(false)
}

// 切换自动刷新
const toggleAutoRefresh = (enabled) => {
  if (enabled) {
    startProgressTimer()
    startRefreshTimer()
  } else {
    stopRefreshTimer()
    stopProgressTimer()
    nextUpdateTime.value = '-'
    progressPercent.value = 0
  }
}

// 刷新间隔改变
const onIntervalChange = () => {
  if (autoRefresh.value) {
    stopRefreshTimer()
    stopProgressTimer()
    elapsedSinceRefresh = 0
    startProgressTimer()
    startRefreshTimer()
  }
}

// 启动刷新定时器
const startRefreshTimer = () => {
  stopRefreshTimer()
  refreshTimer = setInterval(() => {
    loadRealtimeData(true)
  }, refreshInterval.value * 1000)
}

// 停止刷新定时器
const stopRefreshTimer = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// 启动进度定时器
const startProgressTimer = () => {
  stopProgressTimer()
  const interval = 100 // 每100ms更新一次
  progressTimer = setInterval(() => {
    elapsedSinceRefresh += interval
    progressPercent.value = (elapsedSinceRefresh / (refreshInterval.value * 1000)) * 100

    // 更新下次刷新时间
    const now = new Date()
    const nextTime = new Date(now.getTime() + (refreshInterval.value * 1000 - elapsedSinceRefresh))
    nextUpdateTime.value = nextTime.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }, interval)
}

// 停止进度定时器
const stopProgressTimer = () => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

// 格式化时间
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

// 格式化数值
const formatValue = (value) => {
  if (value === null || value === undefined) return '-'
  return typeof value === 'number' ? value.toFixed(2) : value
}

// 获取水质类别对应的样式类名（国家标准颜色）
const getQualityClass = (quality) => {
  const classMap = {
    'Ⅰ': 'quality-excellent',  // 绿色 - 优
    'Ⅱ': 'quality-excellent',  // 绿色 - 优
    'Ⅲ': 'quality-good',       // 蓝色 - 良好
    'Ⅳ': 'quality-fair',       // 黄色 - 轻度污染
    'Ⅴ': 'quality-poor',       // 橙色 - 中度污染
    '劣Ⅴ': 'quality-bad'       // 红色 - 重度污染
  }
  return classMap[quality] || 'quality-unknown'
}

// 获取数值样式类名
const getValueClass = (field, value) => {
  if (value === null || value === undefined) return 'value-null'

  // 水温告警
  if (field === 'temperature' && value > 30) return 'value-warning'

  // pH告警
  if (field === 'ph' && (value < 6.5 || value > 8.5)) return 'value-warning'

  // 溶解氧告警
  if (field === 'dissolved_oxygen' && value < 5) return 'value-warning'

  return 'value-normal'
}

// 判断是否在线
const isOnline = (timestamp) => {
  if (!timestamp) return false
  const now = new Date()
  const time = new Date(timestamp)
  const diff = (now - time) / 1000 / 60 // 分钟差
  return diff < 60 // 1小时内算在线
}

// 获取行样式
const getRowClassName = ({ row }) => {
  if (!isOnline(row.timestamp)) return 'row-offline'
  return ''
}

// 计算表格高度 - 参考国家平台设计
const updateTableHeight = () => {
  const windowHeight = window.innerHeight
  // 采用国家平台的固定高度布局设计
  // 平台标题栏约90px + 进度条2px + 统计卡片约100px + 筛选卡片约70px + 更新日志约200px + padding约50px ≈ 510px
  // 留出更多空间给表格，采用内部滚动
  tableHeight.value = windowHeight - 500
}

onMounted(() => {
  loadRealtimeData()
  updateTableHeight()
  window.addEventListener('resize', updateTableHeight)

  // 启动自动刷新
  if (autoRefresh.value) {
    startProgressTimer()
    startRefreshTimer()
  }
})

onUnmounted(() => {
  stopRefreshTimer()
  stopProgressTimer()
  window.removeEventListener('resize', updateTableHeight)
})
</script>

<style scoped lang="scss">
.dashboard-page {
  padding: 20px 32px;
  // 参考国家平台，采用固定高度布局，内部滚动
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;

  &::-webkit-scrollbar {
    width: 8px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(24, 144, 255, 0.3);
    border-radius: 4px;

    &:hover {
      background: rgba(24, 144, 255, 0.5);
    }
  }

  &::-webkit-scrollbar-track {
    background: rgba(24, 144, 255, 0.05);
  }
}

// 平台标题栏
.platform-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  margin-bottom: 16px;
  background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
  border-radius: 12px;
  color: white;
  box-shadow: 0 4px 20px rgba(30, 58, 138, 0.3);

  .platform-title {
    h1 {
      font-size: 24px;
      font-weight: 700;
      margin: 0 0 4px 0;
      letter-spacing: 1px;
    }

    p {
      font-size: 12px;
      margin: 0;
      opacity: 0.8;
      font-weight: 300;
      letter-spacing: 0.5px;
    }
  }

  .header-controls {
    .refresh-info {
      display: flex;
      align-items: center;
      gap: 16px;

      .auto-refresh-control {
        display: flex;
        align-items: center;
        padding-right: 16px;
        border-right: 1px solid rgba(255, 255, 255, 0.2);

        :deep(.el-switch) {
          --el-switch-on-color: #52c41a;
          --el-switch-off-color: rgba(255, 255, 255, 0.3);
        }

        :deep(.el-select) {
          .el-input__wrapper {
            background: rgba(255, 255, 255, 0.15);
            border-color: rgba(255, 255, 255, 0.2);
            color: white;

            .el-input__inner {
              color: white;
            }

            .el-input__suffix {
              color: white;
            }
          }
        }
      }

      .update-status {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 2px;

        .last-update,
        .next-update {
          font-size: 11px;
          white-space: nowrap;
        }

        .last-update {
          color: rgba(255, 255, 255, 0.8);
        }

        .next-update {
          color: #52c41a;
          font-weight: 600;
        }
      }

      :deep(.el-button) {
        background: rgba(255, 255, 255, 0.2);
        border-color: rgba(255, 255, 255, 0.3);
        color: white;

        &:hover {
          background: rgba(255, 255, 255, 0.3);
        }
      }
    }
  }
}

// 数据统计卡片
.stats-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  border-radius: 12px;
  background: white;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  }

  .stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    margin-right: 16px;
    flex-shrink: 0;
  }

  .stat-content {
    flex: 1;
    min-width: 0;

    .stat-value {
      font-size: 24px;
      font-weight: 700;
      line-height: 1;
      margin-bottom: 6px;
    }

    .stat-label {
      font-size: 12px;
      color: #6B7280;
    }
  }

  &.stat-total .stat-icon {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
  }
  .stat-total .stat-value { color: #667eea; }

  &.stat-excellent .stat-icon {
    background: linear-gradient(135deg, #52c41a 0%, #73d13d 100%);
    color: white;
  }
  .stat-excellent .stat-value { color: #52c41a; }

  &.stat-good .stat-icon {
    background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%);
    color: white;
  }
  .stat-good .stat-value { color: #1890ff; }

  &.stat-poor .stat-icon {
    background: linear-gradient(135deg, #ff4d4f 0%, #ff7875 100%);
    color: white;
  }
  .stat-poor .stat-value { color: #ff4d4f; }

  &.stat-online .stat-icon {
    background: linear-gradient(135deg, #13c2c2 0%, #36cfc9 100%);
    color: white;
  }
  .stat-online .stat-value { color: #13c2c2; }
}

// 刷新进度条
.refresh-progress {
  height: 2px;
  background: rgba(24, 144, 255, 0.1);
  border-radius: 1px;
  overflow: hidden;
  margin-bottom: 16px;

  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #1890FF 0%, #52C41A 100%);
    transition: width 0.1s linear;
  }
}

.filter-card {
  padding: 16px 20px;
  margin-bottom: 20px;
}

.data-table {
  padding: 16px;

  // 水质类别徽章
  .quality-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;

    &.quality-excellent {
      background: #f0f9ff;
      color: #52c41a;
      border: 1px solid #b7eb8f;
    }

    &.quality-good {
      background: #e6f7ff;
      color: #1890ff;
      border: 1px solid #91d5ff;
    }

    &.quality-fair {
      background: #fffbe6;
      color: #faad14;
      border: 1px solid #ffe58f;
    }

    &.quality-poor {
      background: #fff7e6;
      color: #fa8c16;
      border: 1px solid #ffd591;
    }

    &.quality-bad {
      background: #fff1f0;
      color: #ff4d4f;
      border: 1px solid #ffccc7;
    }

    &.quality-unknown {
      background: #f5f5f5;
      color: #8c8c8c;
      border: 1px solid #d9d9d9;
    }
  }

  .station-name {
    font-weight: 500;
    color: #1F2937;
  }

  .status-indicator {
    display: flex;
    justify-content: center;
    align-items: center;

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #D1D5DB;
    }

    &.status-online .status-dot {
      background: #52C41A;
      box-shadow: 0 0 6px rgba(82, 196, 26, 0.5);
    }
  }

  .value-normal {
    color: #1F2937;
  }

  .value-warning {
    color: #FF4D4F;
    font-weight: 500;
  }

  .value-null {
    color: #9CA3AF;
  }

  // 数据更新动画
  .data-updated {
    animation: dataUpdate 1s ease-out;
  }
}

@keyframes dataUpdate {
  0% {
    background: rgba(82, 196, 26, 0.3);
    color: #1890FF;
  }
  100% {
    background: transparent;
    color: inherit;
  }
}

.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(24, 144, 255, 0.1);

  .total-info {
    font-size: 13px;
    color: #6B7280;

    .update-hint {
      color: #52C41A;
      font-weight: 500;
    }
  }

  .auto-refresh-status {
    display: flex;
    align-items: center;
    gap: 12px;

    .refresh-interval {
      font-size: 12px;
      color: #6B7280;
    }
  }
}

// 更新日志
.update-log {
  margin-top: 20px;
  padding: 16px 20px;
  max-height: 250px;
  overflow: hidden;

  .log-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(24, 144, 255, 0.1);

    h4 {
      font-size: 14px;
      font-weight: 600;
      color: #1F2937;
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
    border-bottom: 1px solid rgba(24, 144, 255, 0.05);
    font-size: 12px;
    transition: all 0.3s ease;

    &:last-child {
      border-bottom: none;
    }

    &.log-item-new {
      background: rgba(82, 196, 26, 0.05);
      padding: 8px 12px;
      border-radius: 6px;
      margin: 0 -12px;

      .log-time {
        color: #52C41A;
        font-weight: 600;
      }

      .log-message {
        color: #1F2937;
        font-weight: 500;
      }

      animation: slideInLeft 0.3s ease-out;
    }

    .log-time {
      color: #6B7280;
      margin-right: 12px;
      min-width: 70px;
      font-family: 'Monaco', 'Consolas', monospace;
    }

    .log-message {
      color: #6B7280;
      flex: 1;
    }
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

// 刷新按钮旋转动画
.refreshing {
  animation: rotate 0.5s linear;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

// 离线行样式
:deep(.el-table .row-offline) {
  background: rgba(24, 144, 255, 0.02);
  opacity: 0.7;
}

// 响应式
@media (max-width: 768px) {
  .dashboard-page {
    padding: 16px;
  }

  .platform-header {
    flex-direction: column;
    gap: 16px;
    padding: 16px;

    .platform-title h1 {
      font-size: 18px;
    }

    .header-controls .refresh-info {
      flex-wrap: wrap;
      gap: 8px;

      .auto-refresh-control {
        border-right: none;
        padding-right: 0;
      }
    }
  }

  .stats-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .stats-cards {
    grid-template-columns: 1fr;
  }
}

// 筛选卡片响应式
@media (max-width: 768px) {
  .filter-card {
    .el-form {
      flex-direction: column;

      .el-form-item {
        margin-right: 0;
        margin-bottom: 12px;
        width: 100%;

        .el-select,
        .el-input {
          width: 100% !important;
        }
      }
    }
  }
}
</style>
