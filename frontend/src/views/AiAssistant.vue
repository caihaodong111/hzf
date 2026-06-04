<template>
  <div class="chatgpt-page">
    <div class="chatgpt-shell">
      <aside class="workspace-sidebar">
        <div class="sidebar-head">
          <div class="brand-pill">
            <span class="brand-dot"></span>
            <span>AI 智能分析</span>
          </div>

          <button class="new-chat-btn" type="button" @click="startNewChat">
            <span class="plus">+</span>
            <span>新对话</span>
          </button>

          <button class="refresh-side-btn" type="button" @click="loadOverview" :disabled="loadingOverview">
            {{ loadingOverview ? '同步中...' : '刷新快照' }}
          </button>
        </div>

        <div class="sidebar-scroll">
          <section class="sidebar-section">
            <div class="section-label">本次会话</div>

            <button
              v-if="sessionQuestions.length === 0"
              class="thread-item placeholder"
              type="button"
              @click="focusComposer"
            >
              从下方输入框开始提问
            </button>

            <button
              v-for="item in sessionQuestions"
              :key="item.key"
              class="thread-item"
              type="button"
              @click="applyPrompt(item.full)"
            >
              {{ item.label }}
            </button>
          </section>

          <section class="sidebar-section">
            <div class="section-label">快捷问题</div>

            <button
              v-for="item in quickPrompts.slice(0, 4)"
              :key="item"
              class="thread-item soft"
              type="button"
              @click="applyPrompt(item)"
            >
              {{ item }}
            </button>
          </section>
        </div>

        <div class="snapshot-card">
          <div class="snapshot-header">
            <span class="snapshot-title">最新水质快照</span>
            <span class="snapshot-source">{{ dataSourceLabel }}</span>
          </div>

          <div class="snapshot-time">{{ overviewTimestampLabel || '尚未同步快照' }}</div>

          <div class="snapshot-metrics">
            <div v-for="item in sidebarMetrics" :key="item.label" class="metric-row">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </div>
      </aside>

      <section class="chat-stage">
        <header class="stage-header">
          <div class="header-main">
            <div class="app-badge">AI 智能分析</div>
            <h1>水质风险研判助手</h1>
            <p>{{ headerDescription }}</p>
          </div>

          <div class="header-status">
            <span class="status-pill" :class="{ loading: loadingOverview }">
              <span class="status-dot"></span>
              <span>{{ statusLine }}</span>
            </span>

            <button v-if="hasMessages" class="link-btn" type="button" @click="startNewChat">
              清空对话
            </button>
          </div>
        </header>

        <main class="conversation-body" ref="chatBodyRef">
          <section v-if="!hasMessages" class="welcome-panel">
            <h2>今天想分析什么？</h2>
            <p>{{ welcomeCaption }}</p>

            <div class="hero-stats">
              <div v-for="item in heroStats" :key="item.label" class="hero-stat">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>

            <div class="suggestion-grid">
              <button
                v-for="item in quickPrompts"
                :key="item"
                class="suggestion-card"
                type="button"
                @click="applyPrompt(item)"
              >
                <span class="suggestion-title">{{ item }}</span>
                <span class="suggestion-meta">基于最新快照生成分析</span>
              </button>
            </div>
          </section>

          <section v-else class="message-stream">
            <div class="context-bar">
              <span v-for="item in contextBadges" :key="item" class="context-chip">
                {{ item }}
              </span>
            </div>

            <div v-for="(msg, idx) in messages" :key="idx" :class="['message-row', msg.role]">
              <div class="message-avatar">
                {{ msg.role === 'assistant' ? 'AI' : '你' }}
              </div>

              <div class="message-column">
                <div class="message-role">
                  {{ msg.role === 'assistant' ? '水质风险研判助手' : '你' }}
                </div>

                <div class="message-bubble" :class="{ streaming: msg.streaming }">
                  <div class="message-content">
                    {{ msg.streaming && !msg.content ? '正在分析...' : msg.content }}
                  </div>
                  <div class="message-time" v-if="msg.time">{{ msg.time }}</div>
                </div>
              </div>
            </div>

            <div v-if="loading && !hasStreamingMessage" class="message-row assistant">
              <div class="message-avatar">AI</div>

              <div class="message-column">
                <div class="message-role">水质风险研判助手</div>

                <div class="loading-shell">
                  <div class="typing-dots">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </main>

        <footer class="composer-panel">
          <div class="composer">
            <textarea
              v-model="question"
              ref="inputRef"
              rows="1"
              placeholder="给水质快照下指令，例如：输出高风险断面和处置建议"
              @input="syncTextareaHeight"
              @keydown.enter.exact.prevent="handleSendClick"
            ></textarea>

            <div class="composer-bottom">
              <div class="composer-tags">
                <span v-for="item in composerTags" :key="item" class="composer-tag">
                  {{ item }}
                </span>
              </div>

              <button
                class="send-btn"
                :class="{ cancel: loading }"
                :disabled="!question.trim() && !loading"
                :title="loading ? '取消' : '发送'"
                @click="handleSendClick"
                type="button"
              >
                <svg v-if="!loading" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <p class="composer-note">AI 仅基于最新快照提供辅助判断，不替代人工决策。</p>
        </footer>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getDashboardOverview } from '@/api/dashboard'
import aiAssistantStore from '@/stores/aiAssistantStore'

const overview = ref({})
const loadingOverview = ref(false)
const loading = aiAssistantStore.loading
const question = aiAssistantStore.draft
const messages = aiAssistantStore.messages
const chatBodyRef = ref(null)
const inputRef = ref(null)

const SOURCE_LABELS = {
  national: '国家水质',
  huawei: '华为云',
  database: '数据库',
  manual: '手动入库',
  auto: '自动模式',
  none: '暂无快照'
}

const quickPrompts = [
  '输出当前水质风险研判结论',
  '哪些断面需要优先处理？',
  '生成今日水质运行简报',
  '判断是否存在富营养化风险',
  '给出夜间增氧建议',
  '解释当前 pH 异常点'
]

const summary = computed(() => overview.value?.summary || {})
const hasMessages = computed(() => messages.value.length > 0)
const hasStreamingMessage = computed(() => messages.value.some((msg) => msg?.streaming))
const dataSourceLabel = computed(() => SOURCE_LABELS[overview.value?.data_source] || '最新快照')

const formatNumber = (value, digits = 0, suffix = '') => {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return `${num.toFixed(digits)}${suffix}`
}

const formatTimestamp = (value) => {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString('zh-CN', {
      hour12: false,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch (error) {
    return String(value)
  }
}

const truncate = (value, max = 28) => {
  const text = String(value || '').trim()
  if (!text) return '新的分析对话'
  if (text.length <= max) return text
  return `${text.slice(0, max - 3)}...`
}

const overviewTimestampLabel = computed(() => formatTimestamp(overview.value?.timestamp))

const sessionQuestions = computed(() => {
  return messages.value
    .filter((msg) => msg.role === 'user')
    .map((msg, index) => ({
      key: `${index}-${msg.time || ''}`,
      label: truncate(msg.content),
      full: msg.content || ''
    }))
    .reverse()
    .slice(0, 8)
})

const sidebarMetrics = computed(() => ([
  { label: '监测断面', value: `${summary.value.total_devices ?? 0} 个` },
  { label: '关注信号', value: `${summary.value.alert_count ?? 0} 项` },
  { label: '平均 DO', value: formatNumber(summary.value.avg_dissolved_oxygen, 2, ' mg/L') },
  { label: '平均 pH', value: formatNumber(summary.value.avg_ph, 2) }
]))

const heroStats = computed(() => ([
  { label: '监测断面', value: `${summary.value.total_devices ?? 0}` },
  { label: '在线断面', value: `${summary.value.online_devices ?? 0}` },
  { label: '关注信号', value: `${summary.value.alert_count ?? 0}` },
  { label: '平均 DO', value: formatNumber(summary.value.avg_dissolved_oxygen, 2) }
]))

const composerTags = computed(() => {
  const tags = [dataSourceLabel.value]
  if (overviewTimestampLabel.value) {
    tags.push(`快照 ${overviewTimestampLabel.value}`)
  }
  tags.push(`断面 ${summary.value.total_devices ?? 0}`)
  tags.push(`预警 ${summary.value.alert_count ?? 0}`)
  return tags
})

const contextBadges = computed(() => {
  const tags = [`数据源 ${dataSourceLabel.value}`]
  if (overviewTimestampLabel.value) {
    tags.push(`快照 ${overviewTimestampLabel.value}`)
  }
  tags.push(`断面 ${summary.value.total_devices ?? 0} 个`)
  tags.push(`预警 ${summary.value.alert_count ?? 0} 项`)
  return tags
})

const statusLine = computed(() => {
  if (loadingOverview.value) return '正在同步最新水质快照'
  if (overviewTimestampLabel.value) return `快照更新于 ${overviewTimestampLabel.value}`
  return '刷新后获取最新水质快照'
})

const headerDescription = computed(() => {
  if (overviewTimestampLabel.value) {
    return `基于 ${overviewTimestampLabel.value} 的最新水质快照输出风险解释和处置建议。`
  }
  return '基于最新水质快照输出风险解释和处置建议。'
})

const welcomeCaption = computed(() => {
  const total = summary.value.total_devices ?? 0
  const alerts = summary.value.alert_count ?? 0

  if (loadingOverview.value) {
    return '正在同步快照，完成后即可基于当前断面状态发起对话。'
  }
  if (total <= 0) {
    return '当前暂无可用快照，刷新数据后可生成风险结论、简报和处置建议。'
  }
  if (alerts > 0) {
    return `当前快照覆盖 ${total} 个断面，已识别 ${alerts} 个需重点关注的风险信号。`
  }
  return `当前快照覆盖 ${total} 个断面，可继续追问风险排序、日报摘要或处置建议。`
})

const syncTextareaHeight = () => {
  const el = inputRef.value
  if (!el) return
  el.style.height = '0px'
  const nextHeight = Math.min(Math.max(el.scrollHeight, 56), 180)
  el.style.height = `${nextHeight}px`
}

const focusComposer = async () => {
  await nextTick()
  syncTextareaHeight()
  inputRef.value?.focus?.()
}

const scrollToBottom = async () => {
  await nextTick()
  if (!chatBodyRef.value) return

  chatBodyRef.value.scrollTo({
    top: chatBodyRef.value.scrollHeight,
    behavior: 'smooth'
  })
}

const loadOverview = async () => {
  loadingOverview.value = true
  try {
    const res = await getDashboardOverview()
    overview.value = res.data || {}
  } catch (error) {
    overview.value = {}
    ElMessage.error('获取实时数据失败')
  } finally {
    loadingOverview.value = false
  }
}

const applyPrompt = async (text) => {
  aiAssistantStore.setDraft(text)
  await focusComposer()
}

const startNewChat = async () => {
  if (loading.value) {
    aiAssistantStore.cancel()
  }
  aiAssistantStore.clearChat()
  aiAssistantStore.setDraft('')
  await focusComposer()
}

const handleSendClick = () => {
  if (loading.value) {
    aiAssistantStore.cancel()
    return
  }
  askAi()
}

const askAi = async () => {
  const trimmed = question.value.trim()
  if (!trimmed || loading.value) return

  try {
    const context = {
      summary: overview.value?.summary,
      sensors: (overview.value?.sensors || []).slice(0, 6),
      data_source: overview.value?.data_source,
      timestamp: overview.value?.timestamp
    }
    await aiAssistantStore.ask({ question: trimmed, context, model: 'deepseek-ai/DeepSeek-V4-Pro' })
  } catch (error) {
    // store 内部已处理展示
  } finally {
    await scrollToBottom()
    await nextTick()
    syncTextareaHeight()
  }
}

watch(question, async () => {
  await nextTick()
  syncTextareaHeight()
})

watch(
  () => messages.value.map((msg) => `${msg.role}:${msg.content?.length || 0}:${msg.streaming ? 1 : 0}`).join('|'),
  async () => {
    await scrollToBottom()
  }
)

onMounted(async () => {
  aiAssistantStore.loadFromStorage()
  await loadOverview()
  await nextTick()
  syncTextareaHeight()
  await scrollToBottom()
})
</script>

<style scoped lang="scss">
.chatgpt-page {
  height: 100vh;
  padding: 20px;
  overflow: hidden;
  background: linear-gradient(180deg, #f4f4f5 0%, #ececf1 100%);
}

.chatgpt-shell {
  height: calc(100vh - 40px);
  max-height: calc(100vh - 40px);
  display: flex;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 26px;
  overflow: hidden;
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.08);
}

.workspace-sidebar {
  width: 280px;
  flex-shrink: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 14px 12px;
  background: #f7f7f8;
  border-right: 1px solid #ececf0;
}

.sidebar-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.brand-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: #ffffff;
  border: 1px solid #ececf0;
  color: #111827;
  font-size: 13px;
  font-weight: 600;
}

.brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #111827;
}

.new-chat-btn,
.refresh-side-btn,
.thread-item,
.suggestion-card,
.link-btn {
  border: none;
  background: none;
  cursor: pointer;
  font: inherit;
}

.new-chat-btn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  min-height: 42px;
  border-radius: 14px;
  background: #111827;
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  transition: opacity 0.2s ease, transform 0.2s ease;

  &:hover {
    opacity: 0.94;
    transform: translateY(-1px);
  }
}

.plus {
  font-size: 18px;
  line-height: 1;
}

.refresh-side-btn {
  min-height: 38px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #ececf0;
  color: #4b5563;
  font-size: 13px;
  transition: background 0.2s ease, color 0.2s ease;

  &:hover:not(:disabled) {
    background: #f0f0f2;
    color: #111827;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.sidebar-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(156, 163, 175, 0.36);
    border-radius: 999px;
  }
}

.sidebar-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  padding: 0 6px;
  color: #8e8ea0;
  font-size: 12px;
}

.thread-item {
  width: 100%;
  padding: 11px 12px;
  text-align: left;
  border-radius: 12px;
  color: #374151;
  font-size: 13px;
  line-height: 1.45;
  transition: background 0.2s ease, color 0.2s ease;

  &:hover {
    background: #ececf1;
    color: #111827;
  }
}

.thread-item.soft {
  background: #ffffff;
  border: 1px solid #ececf0;
}

.thread-item.placeholder {
  color: #6b7280;
}

.snapshot-card {
  padding: 14px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #ececf0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.snapshot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.snapshot-title {
  color: #111827;
  font-size: 13px;
  font-weight: 600;
}

.snapshot-source {
  padding: 4px 8px;
  border-radius: 999px;
  background: #f4f4f5;
  color: #6b7280;
  font-size: 11px;
}

.snapshot-time {
  color: #8e8ea0;
  font-size: 12px;
  line-height: 1.5;
}

.snapshot-metrics {
  display: grid;
  gap: 8px;
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #6b7280;
  font-size: 12px;

  strong {
    color: #111827;
    font-size: 13px;
  }
}

.chat-stage {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #ffffff;
}

.stage-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 32px 14px;
  border-bottom: 1px solid #f0f0f0;
}

.header-main {
  display: flex;
  flex-direction: column;
  gap: 8px;

  h1 {
    margin: 0;
    color: #111827;
    font-size: 26px;
    line-height: 1.2;
    font-weight: 700;
  }

  p {
    margin: 0;
    color: #6b7280;
    font-size: 14px;
    line-height: 1.6;
  }
}

.app-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f4f4f5;
  color: #4b5563;
  font-size: 12px;
}

.header-status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  background: #f7f7f8;
  border: 1px solid #ececf0;
  color: #4b5563;
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.12);
}

.status-pill.loading .status-dot {
  animation: pulse 1.4s ease-in-out infinite;
}

.link-btn {
  color: #6b7280;
  font-size: 13px;
  transition: color 0.2s ease;

  &:hover {
    color: #111827;
  }
}

.conversation-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 28px 32px;

  &::-webkit-scrollbar {
    width: 8px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(156, 163, 175, 0.32);
    border-radius: 999px;
  }
}

.welcome-panel {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;

  h2 {
    margin: 0;
    color: #111827;
    font-size: clamp(32px, 5vw, 42px);
    line-height: 1.15;
    letter-spacing: -0.03em;
  }

  p {
    margin: 14px 0 0;
    max-width: 720px;
    color: #6b7280;
    font-size: 16px;
    line-height: 1.75;
  }
}

.hero-stats {
  margin-top: 26px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  width: min(760px, 100%);
}

.hero-stat {
  padding: 16px;
  border-radius: 16px;
  background: #f7f7f8;
  border: 1px solid #ececf0;
  display: flex;
  flex-direction: column;
  gap: 8px;

  span {
    color: #8e8ea0;
    font-size: 12px;
  }

  strong {
    color: #111827;
    font-size: 22px;
    font-weight: 700;
  }
}

.suggestion-grid {
  margin-top: 30px;
  width: min(800px, 100%);
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.suggestion-card {
  padding: 16px;
  border-radius: 18px;
  background: #f7f7f8;
  border: 1px solid #ececf0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  text-align: left;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;

  &:hover {
    background: #ffffff;
    border-color: #d8d8dd;
    transform: translateY(-1px);
  }
}

.suggestion-title {
  color: #111827;
  font-size: 15px;
  line-height: 1.5;
  font-weight: 600;
}

.suggestion-meta {
  color: #8e8ea0;
  font-size: 12px;
}

.message-stream {
  width: min(860px, 100%);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 26px;
}

.context-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.context-chip {
  padding: 7px 12px;
  border-radius: 999px;
  background: #f7f7f8;
  border: 1px solid #ececf0;
  color: #6b7280;
  font-size: 12px;
}

.message-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.user .message-avatar {
  order: 2;
  background: #111827;
  color: #ffffff;
}

.message-row.user .message-column {
  align-items: flex-end;
}

.message-row.assistant .message-bubble {
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  box-shadow: none;
}

.message-avatar {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #f4f4f5;
  color: #111827;
  font-size: 12px;
  font-weight: 700;
}

.message-column {
  max-width: min(760px, calc(100% - 44px));
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.message-role {
  color: #8e8ea0;
  font-size: 12px;
}

.message-bubble {
  padding: 14px 16px;
  border-radius: 18px;
  background: #f7f7f8;
  border: 1px solid #ececf0;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.04);
}

.message-row.assistant .message-content {
  color: #1f2937;
  font-size: 15px;
  line-height: 1.8;
}

.message-row.user .message-content {
  color: #111827;
  font-size: 15px;
  line-height: 1.68;
}

.message-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.message-time {
  margin-top: 10px;
  color: #9ca3af;
  font-size: 11px;
}

.loading-shell {
  min-width: 94px;
  padding: 12px 14px;
  border-radius: 18px;
  background: #f7f7f8;
  border: 1px solid #ececf0;
}

.composer-panel {
  position: sticky;
  bottom: 0;
  z-index: 4;
  flex-shrink: 0;
  padding: 18px 24px 24px;
  border-top: 1px solid #f0f0f0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.84) 0%, #ffffff 38%);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.composer {
  width: min(880px, 100%);
  margin: 0 auto;
  padding: 16px 18px 14px;
  border-radius: 28px;
  background: #ffffff;
  border: 1px solid #d9d9de;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
}

.composer textarea {
  width: 100%;
  min-height: 56px;
  max-height: 180px;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: #111827;
  font-size: 16px;
  line-height: 1.7;

  &::placeholder {
    color: #9ca3af;
  }
}

.composer-bottom {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-top: 8px;
}

.composer-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.composer-tag {
  padding: 6px 10px;
  border-radius: 999px;
  background: #f7f7f8;
  border: 1px solid #ececf0;
  color: #6b7280;
  font-size: 12px;
}

.send-btn {
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  border: none;
  border-radius: 14px;
  background: #111827;
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: opacity 0.2s ease, transform 0.2s ease;

  &:hover:not(:disabled) {
    opacity: 0.94;
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  svg {
    width: 18px;
    height: 18px;
  }
}

.send-btn.cancel {
  background: #ef4444;
}

.composer-note {
  margin: 10px 0 0;
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
}

.typing-dots {
  display: flex;
  gap: 6px;

  span {
    width: 7px;
    height: 7px;
    border-radius: 999px;
    background: rgba(107, 114, 128, 0.7);
    animation: blink 1.4s infinite both;

    &:nth-child(2) {
      animation-delay: 0.2s;
    }

    &:nth-child(3) {
      animation-delay: 0.4s;
    }
  }
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.24;
    transform: translateY(0);
  }

  40% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.12);
  }

  50% {
    transform: scale(1.08);
    box-shadow: 0 0 0 9px rgba(34, 197, 94, 0.08);
  }
}

@media (max-width: 1180px) {
  .chatgpt-page {
    padding: 14px;
  }

  .chatgpt-shell {
    height: calc(100vh - 28px);
    max-height: calc(100vh - 28px);
  }

  .workspace-sidebar {
    width: 252px;
  }
}

@media (max-width: 900px) {
  .chatgpt-page {
    height: 100vh;
    padding: 0;
  }

  .chatgpt-shell {
    height: 100vh;
    max-height: 100vh;
    border-radius: 0;
    border-left: none;
    border-right: none;
  }

  .workspace-sidebar {
    display: none;
  }

  .stage-header {
    padding: 18px 16px 12px;
    flex-direction: column;
  }

  .header-status {
    width: 100%;
    align-items: flex-start;
  }

  .conversation-body {
    padding: 22px 16px;
  }

  .hero-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .suggestion-grid {
    grid-template-columns: 1fr;
  }

  .composer-panel {
    padding: 14px 12px 18px;
  }

  .composer {
    padding: 14px 14px 12px;
    border-radius: 24px;
  }

  .composer-bottom {
    flex-direction: column;
    align-items: stretch;
  }

  .send-btn {
    width: 100%;
    height: 44px;
  }
}

@media (max-width: 640px) {
  .header-main h1 {
    font-size: 22px;
  }

  .welcome-panel h2 {
    font-size: 30px;
  }

  .hero-stats {
    grid-template-columns: 1fr;
  }

  .message-row {
    gap: 10px;
  }

  .message-column {
    max-width: calc(100% - 42px);
  }
}
</style>
