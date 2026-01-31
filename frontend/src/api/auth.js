import request from './index'

/**
 * 用户登录
 * @param {string} username - 用户名
 * @param {string} password - 密码
 */
export const login = (username, password) => {
  return request({
    url: '/users/login/',
    method: 'post',
    data: { username, password }
  })
}

/**
 * 用户登出
 */
export const logout = () => {
  return request({
    url: '/users/logout/',
    method: 'post'
  })
}

/**
 * 获取当前用户信息
 */
export const getUserProfile = () => {
  return request({
    url: '/users/profile/',
    method: 'get'
  })
}

/**
 * 用户注册
 * @param {object} data - 注册数据
 */
export const register = (data) => {
  return request({
    url: '/users/register/',
    method: 'post',
    data
  })
}
