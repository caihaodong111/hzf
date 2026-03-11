import request from './index'

/**
 * 获取实时数据
 * @param {number} count - 返回数量
 * @param {string} areaId - 区域ID（省份）
 * @param {string} riverId - 流域ID
 * @param {string} searchName - 断面名称搜索
 * @param {string} cityName - 城市名称
 * @param {boolean} forceRefresh - 是否强制刷新缓存
 * @param {string} lastVersion - 上次数据版本
 */
export function getRealtimeData(
  count = 10,
  areaId = '',
  riverId = '',
  searchName = '',
  cityName = '',
  forceRefresh = true,
  lastVersion = ''
) {
  return request({
    url: '/sensors/data/realtime/',
    method: 'get',
    params: {
      count,
      area_id: areaId,
      river_id: riverId,
      search_name: searchName,
      city_name: cityName,
      force_refresh: forceRefresh ? 1 : 0,
      last_version: lastVersion
    }
  })
}

/**
 * 获取历史数据
 * @param {string} stationId - 站点ID
 * @param {number} hours - 小时数
 */
export function getHistoricalData(stationId, hours = 24) {
  return request({
    url: '/sensors/data/history/',
    method: 'get',
    params: { station_id: stationId, hours }
  })
}

/**
 * 获取仪表板概览数据
 */
export function getDashboardOverview(hours = 24, count = 10) {
  return request({
    url: '/dashboard/overview/',
    method: 'get',
    params: { hours, count }
  })
}

/**
 * 获取详细统计数据
 */
export function getDashboardStatistics(hours = 24) {
  return request({
    url: '/dashboard/statistics/',
    method: 'get',
    params: { hours }
  })
}

/**
 * 手动触发实时数据入库
 * @param {string} source - 指定数据源
 * @param {number} count - 拉取数量
 * @param {boolean} manual - 是否标记为手动数据
 * @param {boolean} withCity - 国家水质按城市抓取（补 city 字段）
 */
export function syncRealtimeData(source = '', count = 1000, manual = true, withCity = false) {
  return request({
    url: '/sensors/data/sync_realtime/',
    method: 'post',
    // 国家水质按城市抓取可能较慢，单独放宽超时时间
    timeout: 600000,
    data: {
      source,
      count,
      manual,
      with_city: withCity
    }
  })
}
