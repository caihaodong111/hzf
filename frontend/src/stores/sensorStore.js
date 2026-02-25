/**
 * 传感器数据缓存 Store
 * 用于在页面间共享数据，避免重复请求
 */
import { ref } from 'vue'

// 缓存数据
const cache = {
  sensors: ref([]),
  total: ref(0),
  overview: ref({}),
  timestamp: ref(null),
  dataVersion: ref(''),
  loading: ref(false)
}

// 缓存有效期（毫秒）
const CACHE_DURATION = 30000 // 30秒

// 检查缓存是否有效
function isCacheValid() {
  if (!cache.timestamp.value) return false
  const now = Date.now()
  return (now - cache.timestamp.value) < CACHE_DURATION
}

// 获取实时数据（带缓存）
async function getRealtimeData(fetchFn, forceRefresh = false, options = {}) {
  const { checkUpdate = false } = options
  const hasCache = isCacheValid() && cache.sensors.value.length > 0
  // 如果有有效缓存且不强制刷新，直接返回缓存
  if (!forceRefresh && !checkUpdate && hasCache) {
    return {
      code: 200,
      data: {
        sensors: cache.sensors.value,
        total: cache.total.value,
        timestamp: cache.timestamp.value,
        fromCache: true,
        data_version: cache.dataVersion.value,
        changed: false
      }
    }
  }

  // 否则请求新数据
  cache.loading.value = true
  try {
    const result = await fetchFn(cache.dataVersion.value)
    if (result?.code === 200) {
      const changed = result.data?.changed !== false
      const dataVersion = result.data?.data_version || cache.dataVersion.value
      if (!changed && hasCache) {
        cache.timestamp.value = Date.now()
        cache.dataVersion.value = dataVersion
        return {
          code: 200,
          data: {
            sensors: cache.sensors.value,
            total: cache.total.value,
            timestamp: cache.timestamp.value,
            fromCache: true,
            data_version: cache.dataVersion.value,
            changed: false
          }
        }
      }
      cache.sensors.value = result.data?.sensors || []
      cache.total.value = result.data?.total || 0
      cache.timestamp.value = Date.now()
      cache.dataVersion.value = dataVersion
    }
    return result
  } finally {
    cache.loading.value = false
  }
}

// 获取概览数据（带缓存）
async function getOverviewData(fetchFn, forceRefresh = false) {
  // 如果有有效缓存且不强制刷新，直接返回缓存
  if (!forceRefresh && isCacheValid() && Object.keys(cache.overview.value).length > 0) {
    return {
      code: 200,
      data: {
        ...cache.overview.value,
        fromCache: true
      }
    }
  }

  cache.loading.value = true
  try {
    const result = await fetchFn()
    if (result?.code === 200) {
      cache.overview.value = result.data?.summary || result.data || {}
      cache.timestamp.value = Date.now()
    }
    return result
  } finally {
    cache.loading.value = false
  }
}

// 清除缓存
function clearCache() {
  cache.sensors.value = []
  cache.total.value = 0
  cache.overview.value = {}
  cache.timestamp.value = null
  cache.dataVersion.value = ''
}

// 导出
export default {
  cache,
  getRealtimeData,
  getOverviewData,
  clearCache,
  isCacheValid
}
