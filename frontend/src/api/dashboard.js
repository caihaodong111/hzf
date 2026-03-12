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

/**
 * 获取 AI 智能洞察
 */
export function getAiInsight(question, context, model = 'glm-4.7', config = {}) {
  return request({
    url: '/dashboard/ai-insight/',
    method: 'post',
    ...config,
    data: {
      question,
      context,
      model
    }
  })
}
