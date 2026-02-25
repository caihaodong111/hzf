import request from './index'

export function getDataSourceSettings() {
  return request({
    url: '/dashboard/settings/data-source/',
    method: 'get'
  })
}

export function updateDataSourceSettings(mode) {
  return request({
    url: '/dashboard/settings/data-source/',
    method: 'post',
    data: { mode }
  })
}
