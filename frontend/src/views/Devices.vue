<template>
  <div class="devices-container">
    <div class="animated-grid-bg"></div>

    <!-- 导航栏 -->
    <header class="glass-nav">
      <div class="nav-content">
        <div class="logo">智慧渔业监控平台</div>
        <nav class="nav-menu">
          <router-link to="/" class="nav-item">实时监控</router-link>
          <router-link to="/analysis" class="nav-item">数据分析</router-link>
          <router-link to="/devices" class="nav-item active">设备管理</router-link>
          <router-link to="/alerts" class="nav-item">预警中心</router-link>
        </nav>
        <div class="user-profile">
          <el-avatar :size="36">管</el-avatar>
          <span class="username">管理员</span>
          <el-button type="danger" size="small" text @click="handleLogout">退出</el-button>
        </div>
      </div>
    </header>

    <!-- 主内容 -->
    <main class="main-content">
      <div class="page-header">
        <h2>设备管理</h2>
        <p>查看和管理所有监测设备</p>
      </div>

      <!-- 统计信息 -->
      <div class="stats-grid">
        <div class="stat-card glass-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)">
            <el-icon><icon-monitor /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ totalDevices }}</div>
            <div class="stat-label">设备总数</div>
          </div>
        </div>
        <div class="stat-card glass-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)">
            <el-icon><icon-circle-check /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ onlineDevices }}</div>
            <div class="stat-label">在线设备</div>
          </div>
        </div>
        <div class="stat-card glass-card">
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
      <div class="devices-list glass-card">
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
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getDeviceList } from '@/api/sensors'

const router = useRouter()
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

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}

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
.devices-container {
  min-height: 100vh;
  position: relative;
}

.nav-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  height: 64px;
}

.logo {
  font-size: 20px;
  font-weight: 600;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.nav-menu {
  display: flex;
  gap: 8px;
}

.nav-item {
  padding: 8px 16px;
  border-radius: 8px;
  color: #6B7280;
  text-decoration: none;
  transition: all 0.3s ease;

  &:hover {
    color: #1890FF;
    background: rgba(24, 144, 255, 0.1);
  }

  &.active {
    color: #1890FF;
    background: rgba(24, 144, 255, 0.15);
  }
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  font-size: 14px;
  color: #1F2937;
}

.main-content {
  padding: 24px 32px;
}

.page-header {
  margin-bottom: 24px;

  h2 {
    font-size: 28px;
    font-weight: 600;
    color: #1F2937;
    margin-bottom: 8px;
  }

  p {
    font-size: 14px;
    color: #6B7280;
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
  color: #1F2937;
  line-height: 1;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #6B7280;
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
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .nav-menu {
    display: none;
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
