import { ref } from 'vue'
import { getAiInsight } from '@/api/dashboard'

const STORAGE_KEY = 'ai_assistant_chat_v1'

const messages = ref([])
const draft = ref('')
const loading = ref(false)
let inflight = null
let abortController = null

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

function loadFromStorage() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed?.messages)) messages.value = parsed.messages
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
  inflight = null
  loading.value = false
  messages.value.push({ role: 'assistant', content: '已取消本次请求。', time: _nowTime() })
  _save()
}

async function ask({ question, context, model = 'glm-4.7' }) {
  const trimmed = (question || '').trim()
  if (!trimmed || loading.value) return

  messages.value.push({ role: 'user', content: trimmed, time: _nowTime() })
  draft.value = ''
  _save()

  loading.value = true
  abortController = new AbortController()
  const controller = abortController

  const promise = (async () => {
    try {
      const res = await getAiInsight(trimmed, context, model, { signal: controller.signal })
      messages.value.push({
        role: 'assistant',
        content: res?.data?.answer || '未获取到 AI 回复',
        time: _nowTime()
      })
    } catch (error) {
      const canceled = error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError'
      if (canceled) return
      const backendMessage = error?.response?.data?.message
      messages.value.push({
        role: 'assistant',
        content: backendMessage ? `分析失败：${backendMessage}` : '分析失败，请稍后重试。',
        time: _nowTime()
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

