<template>
  <div class="dashboard-page">
    <div class="fluid-bg"></div>
    <div class="dashboard-content">
    <div class="page-header">
      <h2>预警中心</h2>
      <p>实时监控和处理系统告警</p>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card glass">
        <div class="stat-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)">
          <el-icon><icon-bell /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ totalAlerts }}</div>
          <div class="stat-label">总告警数</div>
        </div>
      </div>
      <div class="stat-card glass">
        <div class="stat-icon" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%)">
          <el-icon><icon-warning /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ criticalAlerts }}</div>
          <div class="stat-label">严重告警</div>
        </div>
      </div>
      <div class="stat-card glass">
        <div class="stat-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)">
          <el-icon><icon-warning-filled /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ warningAlerts }}</div>
          <div class="stat-label">警告告警</div>
        </div>
      </div>
      <div class="stat-card glass">
        <div class="stat-icon" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)">
          <el-icon><icon-circle-check /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ resolvedAlerts }}</div>
          <div class="stat-label">已解决</div>
        </div>
      </div>
    </div>

    <!-- 告警列表 -->
    <div class="alerts-list glass">
      <div class="list-header">
        <h3>告警列表</h3>
        <el-button type="primary" size="small" @click="loadAlerts">刷新</el-button>
      </div>

      <el-table :data="alerts" style="width: 100%" v-loading="loading">
        <el-table-column prop="device_id" label="设备ID" width="120" />
        <el-table-column prop="alert_type" label="告警类型" width="120" />
        <el-table-column prop="alert_level" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="getAlertType(row.alert_level)">
              {{ getAlertLabel(row.alert_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="告警消息" />
        <el-table-column prop="value" label="触发值" width="100" />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="resolved" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.resolved ? 'success' : 'danger'">
              {{ row.resolved ? '已解决' : '未解决' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.resolved"
              type="primary"
              size="small"
              text
              @click="resolveAlert(row)"
            >
              解决
            </el-button>
            <span v-else style="color: #67C23A;">已完成</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getAlertList } from '@/api/alerts'
import { ElMessage } from 'element-plus'

const alerts = ref([])
const loading = ref(false)

const totalAlerts = computed(() => alerts.value.length)
const criticalAlerts = computed(() => alerts.value.filter(a => a.alert_level === 'critical').length)
const warningAlerts = computed(() => alerts.value.filter(a => a.alert_level === 'warning').length)
const resolvedAlerts = computed(() => alerts.value.filter(a => a.resolved).length)

const loadAlerts = async () => {
  loading.value = true
  try {
    const res = await getAlertList({ count: 20 })
    if (res.code === 200) {
      alerts.value = res.data.alerts
    }
  } catch (error) {
    console.error('加载告警失败:', error)
  } finally {
    loading.value = false
  }
}

const getAlertType = (level) => {
  const types = {
    'info': 'info',
    'warning': 'warning',
    'critical': 'danger'
  }
  return types[level] || 'info'
}

const getAlertLabel = (level) => {
  const labels = {
    'info': '信息',
    'warning': '警告',
    'critical': '严重'
  }
  return labels[level] || level
}

const formatTime = (time) => {
  return new Date(time).toLocaleString('zh-CN')
}

const resolveAlert = (alert) => {
  alert.resolved = true
  alert.resolved_at = new Date().toISOString()
  ElMessage.success('告警已标记为已解决')
}

onMounted(() => {
  loadAlerts()
})
</script>

<style scoped lang="scss">
$bg-gradient: linear-gradient(135deg, #e0e7ff 0%, #f5f7fb 100%);
$glass-bg: rgba(255, 255, 255, 0.5);
$glass-border: rgba(255, 255, 255, 0.55);
$text-main: #1f2937;
$text-sub: #64748b;

.dashboard-page {
  min-height: 100%;
  background: $bg-gradient;
  color: $text-main;
  font-family: "Sora", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  position: relative;
  overflow: hidden;
}

.fluid-bg {
  position: absolute;
  width: 100%;
  height: 100%;
  background:
    radial-gradient(circle at 0% 0%, rgba(79, 172, 254, 0.15) 0%, transparent 40%),
    radial-gradient(circle at 100% 100%, rgba(99, 102, 241, 0.12) 0%, transparent 40%);
  z-index: 0;
}

.dashboard-content {
  padding: 36px 40px 48px;
  position: relative;
  z-index: 1;
}

.glass {
  background: $glass-bg;
  backdrop-filter: blur(16px);
  border: 1px solid $glass-border;
  border-radius: 24px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04);
}

.page-header {
  margin-bottom: 24px;

  h2 {
    font-size: 28px;
    font-weight: 600;
    color: $text-main;
    margin-bottom: 8px;
  }

  p {
    font-size: 14px;
    color: $text-sub;
  }
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 28px;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: $text-main;
  line-height: 1;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: $text-sub;
}

.alerts-list {
  padding: 24px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  h3 {
    font-size: 18px;
    font-weight: 600;
    color: $text-main;
    margin: 0;
  }
}

@media (max-width: 1024px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .dashboard-content {
    padding: 24px 18px 32px;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
