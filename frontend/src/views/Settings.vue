<template>
  <div class="settings-page">
    <div class="ambient-bg"></div>

    <header class="settings-header">
      <div>
        <h1>数据源设置</h1>
        <p>在国家水质平台与华为云之间切换</p>
      </div>
      <div class="status-pills">
        <span class="pill" :class="availability.national_enabled ? 'ok' : 'off'">
          国家平台 {{ availability.national_enabled ? '可用' : '未启用' }}
        </span>
        <span class="pill" :class="availability.huawei_enabled ? 'ok' : 'off'">
          华为云 {{ availability.huawei_enabled ? '可用' : '未启用' }}
        </span>
      </div>
    </header>

    <section class="settings-body">
      <div class="mode-card">
        <div class="card-title">数据源模式</div>
        <div class="mode-options">
          <label class="mode-option" :class="{ active: mode === 'auto' }">
            <input type="radio" value="auto" v-model="mode" />
            <div class="option-content">
              <div class="option-title">自动</div>
              <div class="option-subtitle">优先国家水质平台，必要时回退至华为云</div>
              <div class="option-detail">适合日常监测与全域覆盖</div>
            </div>
          </label>
          <label class="mode-option" :class="{ active: mode === 'manual' }">
            <input type="radio" value="manual" v-model="mode" />
            <div class="option-content">
              <div class="option-title">手动</div>
              <div class="option-subtitle">优先华为云数据源</div>
              <div class="option-detail">适合使用华为云稳定接入</div>
            </div>
          </label>
        </div>
        <div class="action-row">
          <button class="save-btn" type="button" @click="handleSave" :disabled="saving || loading">
            {{ saving ? '保存中...' : '保存设置' }}
          </button>
          <span class="hint" v-if="loading">正在读取配置...</span>
        </div>
      </div>

      <div class="tips-card">
        <div class="card-title">提示</div>
        <ul>
          <li>自动模式适合国家水质平台稳定接入场景。</li>
          <li>手动模式会优先调用华为云数据源。</li>
          <li>如果华为云未启用，请先在后端配置相关参数。</li>
        </ul>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDataSourceSettings, updateDataSourceSettings } from '@/api/settings'

const mode = ref('auto')
const loading = ref(false)
const saving = ref(false)
const availability = ref({
  national_enabled: false,
  huawei_enabled: false
})

const loadSettings = async () => {
  loading.value = true
  try {
    const res = await getDataSourceSettings()
    mode.value = res?.data?.mode || 'auto'
    availability.value = res?.data?.availability || availability.value
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    const res = await updateDataSourceSettings(mode.value)
    availability.value = res?.data?.availability || availability.value
    ElMessage.success('数据源设置已更新')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadSettings()
})
</script>

<style scoped lang="scss">
.settings-page {
  min-height: 100vh;
  padding: 30px;
  position: relative;
  overflow: hidden;
  font-family: "Space Grotesk", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #0f172a;
  background:
    radial-gradient(circle at 12% 10%, rgba(59, 130, 246, 0.18), transparent 45%),
    radial-gradient(circle at 85% 20%, rgba(16, 185, 129, 0.2), transparent 50%),
    linear-gradient(160deg, #f5f7fb 0%, #eef2f7 45%, #f8fafc 100%);
}

.ambient-bg {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 60% 30%, rgba(15, 118, 110, 0.12), transparent 55%);
  pointer-events: none;
  animation: float-bg 12s ease-in-out infinite;
}

.settings-header {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;

  h1 {
    margin: 0;
    font-size: 28px;
  }

  p {
    margin: 6px 0 0;
    color: #64748b;
  }
}

.status-pills {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.pill {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.4);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.pill.ok {
  border-color: rgba(16, 185, 129, 0.5);
  color: #0f766e;
}

.pill.off {
  border-color: rgba(239, 68, 68, 0.4);
  color: #b91c1c;
}

.settings-body {
  margin-top: 28px;
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 20px;
  position: relative;
  z-index: 1;
}

.mode-card,
.tips-card {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(226, 232, 240, 0.8);
  border-radius: 20px;
  padding: 22px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(10px);
}

.card-title {
  font-weight: 600;
  font-size: 16px;
  margin-bottom: 16px;
}

.mode-options {
  display: grid;
  gap: 14px;
}

.mode-option {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: #fff;
  cursor: pointer;
  transition: all 0.25s ease;

  input {
    width: 18px;
    height: 18px;
    accent-color: #0ea5e9;
  }

  &:hover {
    border-color: rgba(14, 165, 233, 0.4);
    box-shadow: 0 10px 24px rgba(14, 165, 233, 0.18);
    transform: translateY(-1px);
  }
}

.mode-option.active {
  border-color: rgba(14, 165, 233, 0.5);
  box-shadow: 0 14px 28px rgba(14, 165, 233, 0.2);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(14, 116, 144, 0.05));
}

.option-title {
  font-size: 16px;
  font-weight: 600;
}

.option-subtitle {
  font-size: 13px;
  color: #475569;
  margin-top: 6px;
}

.option-detail {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.action-row {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.save-btn {
  padding: 10px 20px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, #0ea5e9, #22c55e);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 12px 24px rgba(14, 165, 233, 0.2);
  transition: transform 0.2s ease, opacity 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.hint {
  font-size: 12px;
  color: #64748b;
}

.tips-card ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 13px;
  line-height: 1.8;
}

@keyframes float-bg {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-12px);
  }
}

@media (max-width: 1024px) {
  .settings-body {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .settings-page {
    padding: 20px;
  }

  .settings-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
