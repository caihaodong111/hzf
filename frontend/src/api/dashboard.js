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
export function getAiInsight(question, context, model = 'deepseek-ai/DeepSeek-V4-Pro', config = {}) {
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

function _buildApiUrl(path) {
  const baseUrl = String(request.defaults?.baseURL || '').replace(/\/$/, '')
  return `${baseUrl}${path}`
}

function _createHttpError(response, payload) {
  const error = new Error(payload?.message || response.statusText || '请求失败')
  error.response = {
    status: response.status,
    data: payload || { message: error.message }
  }
  return error
}

function _emitSseBlock(block, onEvent) {
  const normalized = String(block || '').replace(/\r/g, '')
  if (!normalized.trim()) return

  let event = 'message'
  const dataLines = []
  for (const line of normalized.split('\n')) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      event = line.slice(6).trim() || 'message'
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }

  if (dataLines.length === 0) return

  const raw = dataLines.join('\n')
  let data = raw
  try {
    data = JSON.parse(raw)
  } catch {
    // ignore invalid json chunks
  }
  onEvent?.({ event, data })
}

async function _consumeSseStream(stream, onEvent) {
  const reader = stream.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true }).replace(/\r/g, '')
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      _emitSseBlock(block, onEvent)
    }
  }

  buffer += decoder.decode().replace(/\r/g, '')
  if (buffer.trim()) {
    _emitSseBlock(buffer, onEvent)
  }
}

export async function streamAiInsight(question, context, model = 'deepseek-ai/DeepSeek-V4-Pro', options = {}) {
  const { signal, onEvent } = options
  const response = await fetch(_buildApiUrl('/dashboard/ai-insight/'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream, application/json'
    },
    credentials: 'same-origin',
    signal,
    body: JSON.stringify({
      question,
      context,
      model,
      stream: true
    })
  })

  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('text/event-stream')) {
    let payload = null
    try {
      payload = await response.json()
    } catch {
      payload = { message: await response.text() || '请求失败' }
    }
    throw _createHttpError(response, payload)
  }

  if (!response.body) {
    throw _createHttpError(response, { message: '浏览器不支持流式读取响应' })
  }

  let finalData = null
  let streamError = null
  await _consumeSseStream(response.body, (evt) => {
    if (evt.event === 'error') {
      streamError = typeof evt.data === 'object'
        ? evt.data
        : { message: String(evt.data || '分析失败，请稍后重试。') }
      return
    }
    if (evt.event === 'done') {
      finalData = typeof evt.data === 'object' ? evt.data : { answer: String(evt.data || '') }
    }
    onEvent?.(evt)
  })

  if (streamError) {
    throw _createHttpError(response, streamError)
  }
  if (!finalData) {
    throw _createHttpError(response, { message: 'AI服务未返回结束事件' })
  }

  return { data: finalData }
}
