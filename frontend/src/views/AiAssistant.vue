<template>
  <div class="ai-page">
    <div class="ai-bg"></div>

    <div class="ai-content">
      <header class="ai-header">
        <div>
          <h1>AI 智能分析</h1>
          <p>基于最新水质快照输出风险研判与建议</p>
        </div>
        <div class="header-actions">
          <div class="update-tag" v-if="overviewTimestamp">
            <span class="dot" :class="{ active: !loadingOverview }"></span>
            <span>更新于 {{ overviewTimestamp }}</span>
          </div>
          <button class="refresh-btn" type="button" @click="loadOverview" :disabled="loadingOverview">
            <span class="icon">↻</span> {{ loadingOverview ? '更新中' : '刷新' }}
          </button>
        </div>
      </header>

      <main class="ai-main">
      <aside class="side-panel">
        <div class="stat-group">
          <div class="stat-card" v-for="(val, label) in summaryMap" :key="label">
            <span class="label">{{ label }}</span>
            <span class="value">{{ val }}</span>
          </div>
        </div>

        <div class="side-tip">
          提示：选择下方推荐问题可一键提问。
        </div>
      </aside>

      <section class="chat-section">
        <div class="chat-header">
          <h2>对话研判</h2>
          <button class="clear-btn" @click="clearChat" v-if="messages.length > 0">清空</button>
        </div>

        <div class="chat-viewport" ref="chatBodyRef">
          <div v-if="messages.length === 0" class="welcome-view">
            <div class="ai-avatar">AI</div>
            <h3>您好，我是水质分析助手</h3>
            <p>您可以询问关于水质异常、断面风险或周报建议等问题。</p>

            <div class="suggestion-grid">
              <button
                v-for="item in quickPrompts"
                :key="item"
                @click="applyPrompt(item)"
                class="suggest-item"
                type="button"
              >
                {{ item }}
              </button>
            </div>
          </div>

          <div v-else class="message-list">
            <div v-for="(msg, idx) in messages" :key="idx" :class="['msg-wrapper', msg.role]">
              <div class="msg-bubble">
                <div class="msg-content">{{ msg.content }}</div>
                <div class="msg-time" v-if="msg.time">{{ msg.time }}</div>
              </div>
            </div>

            <div v-if="loading" class="msg-wrapper assistant">
              <div class="msg-bubble loading-bubble">
                <div class="typing-dots">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <footer class="input-area">
          <div class="input-wrapper">
            <textarea
              v-model="question"
              placeholder="输入水质分析相关问题..."
              @keydown.enter.exact.prevent="handleSendClick"
              rows="1"
              ref="inputRef"
            ></textarea>
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
          <p class="input-tip">Shift + Enter 换行</p>
        </footer>
      </section>
    </main>
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

const quickPrompts = [
  '分析当前水质风险点与增氧建议',
  '哪些断面需要优先处理？',
  '生成今日水质运行日报',
  '判断是否存在富营养化风险'
]

const summaryMap = computed(() => ({
  监测断面: overview.value?.summary?.total_devices || 0,
  未恢复告警: overview.value?.summary?.alert_count || 0
}))

const overviewTimestamp = computed(() => overview.value?.timestamp || '')

const scrollToBottom = async () => {
  await nextTick()
  if (chatBodyRef.value) {
    chatBodyRef.value.scrollTo({
      top: chatBodyRef.value.scrollHeight,
      behavior: 'smooth'
    })
  }
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

const applyPrompt = (text) => {
  aiAssistantStore.setDraft(text)
  inputRef.value?.focus?.()
}

const clearChat = () => {
  aiAssistantStore.clearChat()
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
    await aiAssistantStore.ask({ question: trimmed, context, model: 'glm-4.7' })
  } catch (error) {
    // store 内部已处理展示
  } finally {
    await scrollToBottom()
  }
}

watch(
  () => messages.value.length,
  async () => {
    await scrollToBottom()
  }
)

onMounted(() => {
  aiAssistantStore.loadFromStorage()
  loadOverview()
  scrollToBottom()
})
</script>

<style scoped lang="scss">
.ai-page {
  min-height: 100vh;
  position: relative;
  padding: 32px 36px 48px;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.ai-bg {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 20% 20%, rgba(52, 211, 153, 0.18), transparent 45%),
    radial-gradient(circle at 80% 10%, rgba(94, 234, 212, 0.16), transparent 40%),
    radial-gradient(circle at 20% 80%, rgba(59, 130, 246, 0.1), transparent 45%),
    linear-gradient(120deg, #f7f9fc 0%, #eef5fb 45%, #f8fafc 100%);
  pointer-events: none;
}

.ai-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;

  h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 700;
    color: #0f172a;
  }

  p {
    margin: 6px 0 0;
    color: #64748b;
    font-size: 14px;
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.update-tag {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.6);
  color: #334155;
  font-size: 12px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.8);
}

.dot.active {
  background: rgba(34, 197, 94, 0.9);
}

.ai-main {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  height: calc(100vh - 220px);
  min-height: 640px;
  display: flex;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 24px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.05);
  z-index: 1;
}

/* 左侧面板 */
.side-panel {
  width: 280px;
  border-right: 1px solid rgba(0, 0, 0, 0.05);
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
}

.stat-card {
  background: white;
  padding: 16px;
  border-radius: 16px;
  margin-bottom: 12px;
  border: 1px solid rgba(0, 0, 0, 0.03);

  .label {
    font-size: 12px;
    color: #64748b;
    display: block;
    margin-bottom: 4px;
  }

  .value {
    font-size: 20px;
    font-weight: 700;
    color: #0f172a;
  }
}

.side-tip {
  margin-top: auto;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.refresh-btn {
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.82);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: #f1f5f9;
  }
}

/* 右侧对话区 */
.chat-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background: rgba(255, 255, 255, 0.3);
}

.chat-header {
  padding: 20px 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;

  h2 {
    font-size: 16px;
    margin: 0;
    color: #334155;
  }

  .clear-btn {
    font-size: 13px;
    color: #94a3b8;
    border: none;
    background: none;
    cursor: pointer;
  }
}

.chat-viewport {
  flex: 1;
  overflow-y: auto;
  padding: 0 32px;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: #e2e8f0;
    border-radius: 10px;
  }
}

/* 欢迎页 */
.welcome-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;

  .ai-avatar {
    width: 64px;
    height: 64px;
    background: #eff6ff;
    color: #3b82f6;
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    font-weight: 800;
    margin-bottom: 24px;
  }

  h3 {
    font-size: 24px;
    color: #1e293b;
    margin-bottom: 8px;
  }

  p {
    color: #64748b;
    margin-bottom: 32px;
  }
}

.suggestion-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  max-width: 500px;
}

.suggest-item {
  padding: 14px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;

  &:hover {
    border-color: #3b82f6;
    background: #eff6ff;
    color: #2563eb;
  }
}

/* 消息气泡 */
.msg-wrapper {
  display: flex;
  margin-bottom: 24px;

  &.user {
    justify-content: flex-end;
  }
}

.msg-bubble {
  max-width: 80%;
  padding: 14px 18px;
  border-radius: 18px;
  position: relative;
  line-height: 1.6;
  font-size: 14px;
}

.msg-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.user .msg-bubble {
  background: #3b82f6;
  color: white;
  border-bottom-right-radius: 4px;
}

.assistant .msg-bubble {
  background: white;
  color: #1e293b;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 15px rgba(0, 0, 0, 0.03);
}

.msg-time {
  font-size: 10px;
  opacity: 0.6;
  margin-top: 6px;
}

/* 输入框 */
.input-area {
  padding: 24px 32px 32px;
}

.input-wrapper {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 8px 12px;
  display: flex;
  align-items: flex-end;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05);
  transition: border-color 0.2s;

  &:focus-within {
    border-color: #3b82f6;
  }

  textarea {
    flex: 1;
    border: none;
    outline: none;
    padding: 10px;
    resize: none;
    font-size: 14px;
    max-height: 150px;

    &::placeholder {
      color: #94a3b8;
    }
  }
}

.send-btn {
  background: #3b82f6;
  color: white;
  border: none;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  margin-bottom: 4px;
  transition: opacity 0.2s;

  &:disabled {
    background: #e2e8f0;
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

.send-btn.cancel:hover {
  opacity: 0.92;
}

.input-tip {
  font-size: 11px;
  color: #94a3b8;
  margin: 8px 0 0 12px;
}

/* 动画效果 */
.typing-dots {
  display: flex;
  gap: 4px;
  padding: 4px;

  span {
    width: 6px;
    height: 6px;
    background: #cbd5e1;
    border-radius: 50%;
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
    opacity: 0.2;
  }

  40% {
    opacity: 1;
  }
}

@media (max-width: 900px) {
  .ai-main {
    width: 96%;
    height: calc(100vh - 220px);
  }

  .side-panel {
    width: 240px;
    padding: 24px 18px;
  }
}

@media (max-width: 768px) {
  .ai-page {
    padding: 24px 18px 32px;
  }

  .ai-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .ai-main {
    width: 100%;
    height: calc(100vh - 220px);
    flex-direction: column;
  }

  .side-panel {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid rgba(0, 0, 0, 0.05);
    flex-direction: row;
    align-items: center;
    gap: 12px;
  }

  .stat-group {
    display: flex;
    gap: 10px;
    overflow: auto;
  }

  .stat-card {
    min-width: 120px;
    margin-bottom: 0;
  }

  .refresh-btn {
    margin-left: auto;
  }

  .chat-header,
  .chat-viewport,
  .input-area {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
