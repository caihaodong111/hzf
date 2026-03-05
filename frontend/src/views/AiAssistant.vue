<template>
  <div class="ai-page">
    <div class="ai-bg"></div>

    <div class="ai-content">
      <header class="ai-header">
        <div>
          <h1>AI 智能分析</h1>
          <p>结合实时水质数据输出风险研判与运维建议</p>
        </div>
        <button class="ghost-btn" type="button" @click="loadOverview" :disabled="loadingOverview">
          {{ loadingOverview ? '刷新中...' : '刷新数据' }}
        </button>
      </header>

      <section class="ai-grid">
        <div class="panel glass-card">
          <div class="panel-title">问题输入</div>
          <div class="quick-tags">
            <button
              v-for="item in quickPrompts"
              :key="item"
              type="button"
              class="tag-btn"
              @click="applyPrompt(item)"
            >
              {{ item }}
            </button>
          </div>

          <textarea
            v-model="question"
            class="question-input"
            rows="6"
            placeholder="例如：请基于当前水质数据，给出风险点位与增氧建议。"
          ></textarea>

          <div class="panel-actions">
            <button class="primary-btn" type="button" @click="askAi" :disabled="loading">
              {{ loading ? '分析中...' : '生成分析' }}
            </button>
            <span class="helper-text" v-if="overviewTimestamp">
              数据时间：{{ overviewTimestamp }}
            </span>
          </div>

          <div class="context-summary">
            <div class="summary-card">
              <span>监测断面</span>
              <strong>{{ summary.total_devices || 0 }}</strong>
            </div>
            <div class="summary-card">
              <span>在线监测</span>
              <strong>{{ summary.online_devices || 0 }}</strong>
            </div>
            <div class="summary-card">
              <span>未恢复告警</span>
              <strong>{{ summary.alert_count || 0 }}</strong>
            </div>
          </div>
        </div>

        <div class="panel glass-card">
          <div class="panel-title">AI 洞察结果</div>
          <div class="answer-box" v-if="answer">
            <pre>{{ answer }}</pre>
          </div>
          <div class="answer-placeholder" v-else>
            <p>等待 AI 输出分析建议。</p>
            <p class="subtle">建议先刷新数据，再选择问题模板生成分析。</p>
          </div>
        </div>
      </section>

      <section class="data-preview glass-card">
        <div class="panel-title">上下文数据预览</div>
        <div class="preview-grid">
          <div class="preview-card" v-for="item in compactSensors" :key="item.station_id">
            <div class="preview-header">
              <h4>{{ item.station_name || item.station_id }}</h4>
              <span class="badge">{{ item.water_quality || '未知' }}</span>
            </div>
            <div class="preview-body">
              <span>水温 {{ formatValue(item.temperature, '°C') }}</span>
              <span>pH {{ formatValue(item.ph) }}</span>
              <span>溶解氧 {{ formatValue(item.dissolved_oxygen, 'mg/L') }}</span>
              <span>电导率 {{ formatValue(item.conductivity, 'μS/cm') }}</span>
              <span>浊度 {{ formatValue(item.turbidity, 'NTU') }}</span>
            </div>
            <div class="preview-footer">
              <span>{{ item.province || '未知省份' }}</span>
              <span>{{ item.river_basin || '未知流域' }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getDashboardOverview, getAiInsight } from '@/api/dashboard'

const overview = ref({})
const loading = ref(false)
const loadingOverview = ref(false)
const question = ref('请基于当前水质数据，给出异常点位与处理建议。')
const answer = ref('')

const quickPrompts = [
  '请基于当前水质数据，给出风险点位与增氧建议。',
  '从水质指标看，哪些断面需要优先处理？请给出原因。',
  '请生成今日水质运行日报，包含异常说明与建议。',
  '请判断是否存在富营养化风险，并给出治理措施。'
]

const summary = computed(() => overview.value?.summary || {})
const overviewTimestamp = computed(() => overview.value?.timestamp || '')
const sensors = computed(() => overview.value?.sensors || [])
const compactSensors = computed(() =>
  sensors.value.slice(0, 6).map(item => ({
    station_id: item.station_id,
    station_name: item.station_name,
    province: item.province,
    river_basin: item.river_basin,
    temperature: item.temperature,
    ph: item.ph,
    dissolved_oxygen: item.dissolved_oxygen,
    conductivity: item.conductivity,
    turbidity: item.turbidity,
    water_quality: item.water_quality,
    timestamp: item.timestamp
  }))
)

const loadOverview = async () => {
  loadingOverview.value = true
  try {
    const res = await getDashboardOverview()
    overview.value = res.data || {}
  } catch (error) {
    overview.value = {}
  } finally {
    loadingOverview.value = false
  }
}

const applyPrompt = (text) => {
  question.value = text
}

const askAi = async () => {
  const trimmed = question.value.trim()
  if (!trimmed) {
    ElMessage.warning('请输入问题后再生成分析')
    return
  }

  loading.value = true
  answer.value = ''
  try {
    const context = {
      summary: summary.value,
      sensors: compactSensors.value,
      data_source: overview.value?.data_source,
      timestamp: overview.value?.timestamp
    }
    const res = await getAiInsight(trimmed, context)
    answer.value = res?.data?.answer || '未获取到 AI 回复'
  } catch (error) {
    answer.value = 'AI 分析失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

const formatValue = (value, unit = '') => {
  if (value === null || value === undefined || value === '') return '--'
  const formatted = Number.isFinite(Number(value)) ? Number(value).toFixed(2) : value
  return unit ? `${formatted} ${unit}` : formatted
}

onMounted(() => {
  loadOverview()
})
</script>

<style scoped lang="scss">
.ai-page {
  min-height: 100vh;
  position: relative;
  padding: 32px 36px 48px;
  overflow: hidden;
}

.ai-bg {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 20% 20%, rgba(52, 211, 153, 0.2), transparent 45%),
    radial-gradient(circle at 80% 10%, rgba(94, 234, 212, 0.18), transparent 40%),
    radial-gradient(circle at 20% 80%, rgba(59, 130, 246, 0.12), transparent 45%),
    linear-gradient(120deg, #f7f9fc 0%, #eef5fb 45%, #f8fafc 100%);
  z-index: 0;
}

.ai-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

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

.ghost-btn {
  border: 1px solid rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.08);
  color: #1d4ed8;
  padding: 10px 18px;
  border-radius: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ghost-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ghost-btn:not(:disabled):hover {
  background: rgba(59, 130, 246, 0.14);
}

.ai-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
}

.glass-card {
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
  border-radius: 18px;
  padding: 22px;
  backdrop-filter: blur(18px);
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 14px;
}

.quick-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 14px;
}

.tag-btn {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255, 255, 255, 0.7);
  color: #334155;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tag-btn:hover {
  border-color: rgba(59, 130, 246, 0.4);
  color: #1d4ed8;
}

.question-input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 14px;
  padding: 14px 16px;
  font-size: 14px;
  resize: vertical;
  background: rgba(255, 255, 255, 0.85);
  color: #0f172a;
}

.panel-actions {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.primary-btn {
  background: linear-gradient(120deg, #2563eb, #38bdf8);
  border: none;
  color: white;
  padding: 10px 18px;
  border-radius: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.primary-btn:not(:disabled):hover {
  transform: translateY(-1px);
}

.helper-text {
  font-size: 12px;
  color: #64748b;
}

.context-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.summary-card {
  background: rgba(255, 255, 255, 0.8);
  border-radius: 14px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #0f172a;

  span {
    font-size: 12px;
    color: #64748b;
  }

  strong {
    font-size: 18px;
  }
}

.answer-box {
  background: rgba(15, 23, 42, 0.06);
  border-radius: 16px;
  padding: 16px;
  max-height: 420px;
  overflow: auto;

  pre {
    margin: 0;
    font-size: 13px;
    line-height: 1.7;
    color: #0f172a;
    white-space: pre-wrap;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  }
}

.answer-placeholder {
  border: 1px dashed rgba(148, 163, 184, 0.5);
  border-radius: 16px;
  padding: 18px;
  color: #64748b;
  font-size: 14px;
}

.answer-placeholder .subtle {
  font-size: 12px;
  margin-top: 6px;
}

.data-preview {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}

.preview-card {
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 16px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  h4 {
    font-size: 14px;
    color: #0f172a;
    margin: 0;
  }
}

.badge {
  font-size: 11px;
  color: #0f172a;
  background: rgba(59, 130, 246, 0.16);
  padding: 2px 8px;
  border-radius: 999px;
}

.preview-body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 10px;
  font-size: 12px;
  color: #334155;
}

.preview-footer {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #64748b;
}

@media (max-width: 768px) {
  .ai-page {
    padding: 24px 18px 32px;
  }

  .ai-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
