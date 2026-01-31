import request from './index'

/**
 * 获取告警列表
 */
export function getAlertList(params) {
  return request({
    url: '/alerts/list_fake/',
    method: 'get',
    params
  })
}

/**
 * 获取未解决告警
 */
export function getUnresolvedAlerts() {
  return request({
    url: '/alerts/list_fake/',
    method: 'get',
    params: { count: 10 }
  })
}
