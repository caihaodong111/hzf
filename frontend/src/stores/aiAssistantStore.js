import { ref } from 'vue'
import { streamAiInsight } from '@/api/dashboard'

const STORAGE_KEY = 'ai_assistant_chat_v1'

const messages = ref([])
const draft = ref('')
const loading = ref(false)
let inflight = null
let abortController = null

function _sanitizeAssistantContent(content) {
  const raw = String(content || '')
  return raw
    .replace(/<(think|analysis|reasoning)>[\s\S]*?<\/\1>/gi, '')
    .replace(/<\|[^>\n]+\|>/gi, '')
    .replace(/\{\{[^{}\n]{1,80}\}\}/g, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function _nowTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function _save() {
  try {
    const payload = {
      messages: messages.value,
      draft: draft.value
    }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // ignore
  }
}

function _setMessage(index, patch) {
  const current = messages.value[index]
  if (!current) return
  messages.value[index] = {
    ...current,
    ...patch
  }
}

function loadFromStorage() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed?.messages)) {
      messages.value = parsed.messages.map((message) => {
        if (message?.role !== 'assistant') return message
        return {
          ...message,
          streaming: false,
          content: _sanitizeAssistantContent(message.content) || '未获取到 AI 回复'
        }
      })
    }
    if (typeof parsed?.draft === 'string') draft.value = parsed.draft
  } catch {
    // ignore
  }
}

function clearChat() {
  messages.value = []
  _save()
}

function setDraft(value) {
  draft.value = value
  _save()
}

function cancel() {
  if (!loading.value) return
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  const lastIndex = messages.value.length - 1
  const lastMessage = messages.value[lastIndex]
  if (lastMessage?.role === 'assistant' && lastMessage?.streaming) {
    _setMessage(lastIndex, {
      streaming: false,
      content: lastMessage.content || '已取消本次请求。'
    })
  } else {
    messages.value.push({ role: 'assistant', content: '已取消本次请求。', time: _nowTime() })
  }
  inflight = null
  loading.value = false
  _save()
}

async function ask({ question, context, model = 'deepseek-ai/DeepSeek-V4-Pro' }) {
  const trimmed = (question || '').trim()
  if (!trimmed || loading.value) return

  messages.value.push({ role: 'user', content: trimmed, time: _nowTime() })
  draft.value = ''
  _save()

  loading.value = true
  abortController = new AbortController()
  const controller = abortController
  const assistantIndex = messages.value.push({
    role: 'assistant',
    content: '',
    time: _nowTime(),
    streaming: true
  }) - 1
  let streamedRawContent = ''

  const promise = (async () => {
    try {
      const res = await streamAiInsight(trimmed, context, model, {
        signal: controller.signal,
        onEvent: ({ event, data }) => {
          if (event === 'chunk') {
            streamedRawContent += String(data?.delta || '')
            _setMessage(assistantIndex, {
              content: _sanitizeAssistantContent(streamedRawContent),
              streaming: true
            })
            _save()
            return
          }
          if (event === 'done') {
            const finalAnswer = _sanitizeAssistantContent(data?.answer || streamedRawContent || '未获取到 AI 回复')
            _setMessage(assistantIndex, {
              content: finalAnswer || '未获取到 AI 回复',
              streaming: false
            })
            _save()
          }
        }
      })
      _setMessage(assistantIndex, {
        content: _sanitizeAssistantContent(res?.data?.answer || streamedRawContent || '未获取到 AI 回复') || '未获取到 AI 回复',
        streaming: false
      })
    } catch (error) {
      const canceled = error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError' || error?.name === 'AbortError'
      if (canceled) return
      const backendMessage = error?.response?.data?.message || error?.message
      const partialContent = _sanitizeAssistantContent(messages.value[assistantIndex]?.content || streamedRawContent)
      _setMessage(assistantIndex, {
        content: partialContent
          ? `${partialContent}\n\n生成中断：${backendMessage || '请稍后重试。'}`
          : (backendMessage ? `分析失败：${backendMessage}` : '分析失败，请稍后重试。'),
        streaming: false
      })
    } finally {
      if (abortController === controller) {
        abortController = null
      }
      inflight = null
      loading.value = false
      _save()
    }
  })()

  inflight = promise
  return promise
}

export default {
  messages,
  draft,
  loading,
  inflight: () => inflight,
  loadFromStorage,
  setDraft,
  clearChat,
  ask,
  cancel
}
