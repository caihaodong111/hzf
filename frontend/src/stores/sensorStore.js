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

const tasks = {
  realtime: {
    loading: ref(false),
    inflight: null,
    key: '',
    seq: 0
  },
  overview: {
    loading: ref(false),
    inflight: null,
    key: '',
    seq: 0
  },
  sync: {
    loading: ref(false),
    inflight: null,
    key: '',
    seq: 0
  }
}

// 缓存有效期（毫秒）
const CACHE_DURATION = 30000 // 30秒

// 检查缓存是否有效
function isCacheValid() {
  if (!cache.timestamp.value) return false
  const now = Date.now()
  return (now - cache.timestamp.value) < CACHE_DURATION
}

function _recomputeGlobalLoading() {
  cache.loading.value = Boolean(
    tasks.realtime.loading.value ||
    tasks.overview.loading.value ||
    tasks.sync.loading.value
  )
}

function runTask(name, fn, options = {}) {
  const { taskKey = '' } = options
  const task = tasks[name]
  if (!task) {
    throw new Error(`Unknown task: ${name}`)
  }
  if (task.inflight && task.key === taskKey) {
    return task.inflight
  }
  task.seq += 1
  task.key = taskKey
  task.loading.value = true
  _recomputeGlobalLoading()

  const promise = Promise.resolve().then(fn)
  task.inflight = promise
  return promise.finally(() => {
    if (task.inflight === promise) {
      task.inflight = null
      task.loading.value = false
      _recomputeGlobalLoading()
    }
  })
}

// 获取实时数据（带缓存）
async function getRealtimeData(fetchFn, forceRefresh = false, options = {}) {
  const { checkUpdate = false, taskKey = '' } = options
  const hasCacheData = cache.sensors.value.length > 0
  const cacheValid = isCacheValid()
  // 如果有有效缓存且不强制刷新，直接返回缓存
  if (!forceRefresh && !checkUpdate && cacheValid && hasCacheData) {
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

  // 同一参数请求在进行中时，复用 inflight promise，避免重复请求
  if (tasks.realtime.inflight && tasks.realtime.key === taskKey) {
    return tasks.realtime.inflight
  }

  tasks.realtime.seq += 1
  const seq = tasks.realtime.seq
  tasks.realtime.key = taskKey

  tasks.realtime.loading.value = true
  _recomputeGlobalLoading()

  const promise = (async () => {
    const result = await fetchFn(cache.dataVersion.value)
    // 若期间已发起新请求，则不覆盖缓存（但仍返回本次结果给调用方）
    if (seq !== tasks.realtime.seq) return result

    if (result?.code === 200) {
      const changed = result.data?.changed !== false
      const dataVersion = result.data?.data_version || cache.dataVersion.value
      if (!changed && hasCacheData) {
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
  })()

  tasks.realtime.inflight = promise
  return promise.finally(() => {
    if (tasks.realtime.inflight === promise) {
      tasks.realtime.inflight = null
      tasks.realtime.loading.value = false
      _recomputeGlobalLoading()
    }
  })
}

// 获取概览数据（带缓存）
async function getOverviewData(fetchFn, forceRefresh = false, options = {}) {
  const { taskKey = '' } = options
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

  if (tasks.overview.inflight && tasks.overview.key === taskKey) {
    return tasks.overview.inflight
  }

  tasks.overview.seq += 1
  const seq = tasks.overview.seq
  tasks.overview.key = taskKey
  tasks.overview.loading.value = true
  _recomputeGlobalLoading()

  const promise = (async () => {
    const result = await fetchFn()
    if (seq !== tasks.overview.seq) return result
    if (result?.code === 200) {
      cache.overview.value = result.data?.summary || result.data || {}
      cache.timestamp.value = Date.now()
    }
    return result
  })()

  tasks.overview.inflight = promise
  return promise.finally(() => {
    if (tasks.overview.inflight === promise) {
      tasks.overview.inflight = null
      tasks.overview.loading.value = false
      _recomputeGlobalLoading()
    }
  })
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
  tasks,
  runTask,
  getRealtimeData,
  getOverviewData,
  clearCache,
  isCacheValid
}
