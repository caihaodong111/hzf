<template>
  <div class="dashboard-page">
    <div class="fluid-bg"></div>
    <div class="dashboard-content">
    <div class="page-header">
      <h2>设备管理</h2>
      <p>查看和管理所有监测设备</p>
    </div>

    <!-- 统计信息 -->
    <div class="stats-grid">
      <div class="stat-card glass">
        <div class="stat-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)">
          <el-icon><icon-monitor /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ totalDevices }}</div>
          <div class="stat-label">设备总数</div>
        </div>
      </div>
      <div class="stat-card glass">
        <div class="stat-icon" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)">
          <el-icon><icon-circle-check /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ onlineDevices }}</div>
          <div class="stat-label">在线设备</div>
        </div>
      </div>
      <div class="stat-card glass">
        <div class="stat-icon" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%)">
          <el-icon><icon-circle-close /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ offlineDevices }}</div>
          <div class="stat-label">离线设备</div>
        </div>
      </div>
    </div>

    <!-- 设备列表 -->
    <div class="devices-list glass">
      <div class="list-header">
        <h3>设备列表</h3>
        <div class="filters">
          <el-select v-model="filterType" placeholder="设备类型" style="width: 150px" @change="loadDevices">
            <el-option label="全部" value="" />
            <el-option label="传感器" value="sensor" />
            <el-option label="控制器" value="controller" />
          </el-select>
          <el-button type="primary" @click="loadDevices">刷新</el-button>
        </div>
      </div>

      <el-table :data="filteredDevices" style="width: 100%" v-loading="loading">
        <el-table-column prop="device_id" label="设备ID" width="120" />
        <el-table-column prop="device_name" label="设备名称" />
        <el-table-column prop="device_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.device_type === 'sensor' ? 'primary' : 'success'">
              {{ row.device_type === 'sensor' ? '传感器' : '控制器' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="位置" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'online' ? 'success' : 'info'">
              {{ row.status === 'online' ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleDateString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" text>查看</el-button>
            <el-button type="danger" size="small" text>配置</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getDeviceList } from '@/api/sensors'

const devices = ref([])
const loading = ref(false)
const filterType = ref('')

const totalDevices = computed(() => devices.value.length)
const onlineDevices = computed(() => devices.value.filter(d => d.status === 'online').length)
const offlineDevices = computed(() => devices.value.filter(d => d.status === 'offline').length)

const filteredDevices = computed(() => {
  if (!filterType.value) return devices.value
  return devices.value.filter(d => d.device_type === filterType.value)
})

const loadDevices = async () => {
  loading.value = true
  try {
    const res = await getDeviceList()
    if (res.code === 200) {
      devices.value = res.data.devices
    }
  } catch (error) {
    console.error('加载设备列表失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadDevices()
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
  grid-template-columns: repeat(3, 1fr);
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

.devices-list {
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
    color: #1F2937;
    margin: 0;
  }

  .filters {
    display: flex;
    gap: 12px;
  }
}

@media (max-width: 768px) {
  .dashboard-content {
    padding: 24px 18px 32px;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .list-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;

    .filters {
      width: 100%;
      flex-direction: column;

      .el-select {
        width: 100% !important;
      }
    }
  }
}
</style>
