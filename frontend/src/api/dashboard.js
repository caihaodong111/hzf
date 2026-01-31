import request from './index'

/**
 * 获取看板概览数据
 */
export function getDashboardOverview() {
  return request({
    url: '/dashboard/overview/',
    method: 'get'
  })
}
