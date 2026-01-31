import request from './index'

/**
 * 获取实时数据
 */
export function getRealtimeData() {
  return request({
    url: '/sensors/data/realtime/',
    method: 'get'
  })
}

/**
 * 获取历史数据
 * @param {string} deviceId - 设备ID
 * @param {number} hours - 小时数
 */
export function getHistoricalData(deviceId, hours = 24) {
  return request({
    url: '/sensors/data/history/',
    method: 'get',
    params: { device_id: deviceId, hours }
  })
}

/**
 * 获取设备列表
 */
export function getDeviceList() {
  return request({
    url: '/devices/',
    method: 'get'
  })
}
