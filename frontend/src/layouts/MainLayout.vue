<template>
  <div class="main-layout">
    <!-- 动态背景 -->
    <div class="animated-grid-bg"></div>

    <!-- 侧边栏触发检测区（屏幕左边缘） -->
    <div
      class="sidebar-trigger-zone"
      @mouseenter="handleMouseEnter"
    ></div>

    <!-- 左侧隐藏式导航栏 -->
    <aside
      class="sidebar"
      :class="{ 'sidebar-expanded': isExpanded }"
      @mouseleave="handleMouseLeave"
    >
      <!-- 侧边栏内容 -->
      <div class="sidebar-content">
        <!-- Logo区域 -->
        <div class="sidebar-logo">
          <div class="logo-icon">
            <el-icon><icon-monitor /></el-icon>
          </div>
          <transition name="fade-slide">
            <div class="logo-text" v-show="isExpanded">
              <div class="logo-title">智慧渔业</div>
              <div class="logo-subtitle">监控平台</div>
            </div>
          </transition>
        </div>

        <!-- 导航菜单 -->
        <nav class="sidebar-nav">
          <router-link
            v-for="item in menuItems"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
          >
            <div class="nav-icon">
              <el-icon>
                <component :is="item.icon" />
              </el-icon>
            </div>
            <transition name="fade-slide">
              <div class="nav-content" v-show="isExpanded">
                <div class="nav-title">{{ item.title }}</div>
                <div class="nav-subtitle">{{ item.subtitle }}</div>
              </div>
            </transition>
          </router-link>
        </nav>

        <!-- 用户信息 -->
        <div class="sidebar-user">
          <div class="user-avatar">
            <el-avatar :size="40">管</el-avatar>
          </div>
          <transition name="fade-slide">
            <div class="user-info" v-show="isExpanded">
              <div class="user-name">管理员</div>
              <el-button type="danger" size="small" text @click="handleLogout">退出</el-button>
            </div>
          </transition>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" :key="route.fullPath" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Monitor, TrendCharts, Setting, Bell } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

const isExpanded = ref(false)
const iconMonitor = Monitor
let expandTimer = null
let collapseTimer = null

// 菜单项配置
const menuItems = [
  {
    path: '/',
    title: '实时监控',
    subtitle: 'Dashboard',
    icon: Monitor
  },
  {
    path: '/analysis',
    title: '数据分析',
    subtitle: 'Analysis',
    icon: TrendCharts
  },
  {
    path: '/devices',
    title: '设备管理',
    subtitle: 'Devices',
    icon: Setting
  },
  {
    path: '/alerts',
    title: '预警中心',
    subtitle: 'Alerts',
    icon: Bell
  }
]

// 判断当前路由是否激活
const isActive = (path) => {
  return route.path === path
}

// 鼠标进入触发区
const handleMouseEnter = () => {
  clearTimeout(collapseTimer)
  expandTimer = setTimeout(() => {
    isExpanded.value = true
  }, 100)
}

// 鼠标离开侧边栏
const handleMouseLeave = () => {
  clearTimeout(expandTimer)
  collapseTimer = setTimeout(() => {
    isExpanded.value = false
  }, 150)
}

// 退出登录
const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.push('/login')
}
</script>

<style scoped lang="scss">
.main-layout {
  min-height: 100vh;
  position: relative;
  display: flex;
}

// 侧边栏触发检测区（屏幕左边缘10px）
.sidebar-trigger-zone {
  position: fixed;
  left: 0;
  top: 0;
  width: 10px;
  height: 100vh;
  z-index: 1001;
  cursor: default;
}

// 侧边栏 - 默认完全隐藏在左侧
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  height: 100vh;
  width: 240px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-right: 1px solid rgba(24, 144, 255, 0.1);
  box-shadow: 4px 0 30px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  overflow: hidden;

  // 默认状态：完全隐藏在左侧屏幕外
  transform: translateX(-100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  // 展开状态：滑入屏幕
  &.sidebar-expanded {
    transform: translateX(0);
  }
}

// 侧边栏内容
.sidebar-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px 0;
  width: 240px;
}

// Logo区域
.sidebar-logo {
  display: flex;
  align-items: center;
  padding: 0 16px;
  margin-bottom: 32px;
  gap: 12px;

  .logo-icon {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 20px;
    flex-shrink: 0;
  }

  .logo-text {
    flex: 1;
    min-width: 0;

    .logo-title {
      font-size: 16px;
      font-weight: 600;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .logo-subtitle {
      font-size: 12px;
      color: #6B7280;
      margin-top: 2px;
    }
  }
}

// 导航菜单
.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 12px;
  overflow-y: auto;
  overflow-x: hidden;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(24, 144, 255, 0.2);
    border-radius: 2px;
  }
}

// 导航项
.nav-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 12px;
  color: #6B7280;
  text-decoration: none;
  transition: all 0.3s ease;
  cursor: pointer;
  white-space: nowrap;
  gap: 12px;

  &:hover {
    background: rgba(24, 144, 255, 0.1);
    color: #1890FF;

    .nav-icon {
      transform: scale(1.1);
    }
  }

  &.active {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
    color: #667eea;

    .nav-icon {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }
  }

  .nav-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
    transition: all 0.3s ease;
  }

  .nav-content {
    flex: 1;
    min-width: 0;

    .nav-title {
      font-size: 14px;
      font-weight: 500;
    }

    .nav-subtitle {
      font-size: 11px;
      color: #9CA3AF;
      margin-top: 2px;
    }
  }
}

// 用户信息
.sidebar-user {
  display: flex;
  align-items: center;
  padding: 16px;
  margin-top: auto;
  border-top: 1px solid rgba(24, 144, 255, 0.1);
  gap: 12px;

  .user-avatar {
    flex-shrink: 0;
  }

  .user-info {
    flex: 1;
    min-width: 0;

    .user-name {
      font-size: 14px;
      font-weight: 500;
      color: #1F2937;
      margin-bottom: 4px;
    }
  }
}

// 主内容区 - 参考国家平台设计，固定高度布局
.main-content {
  flex: 1;
  width: 100%;
  height: 100vh;
  overflow: hidden; // 禁用主内容区滚动，由内部页面处理
}

// 内容淡入滑出动画
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}

// 页面切换动画
.page-enter-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.page-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 1, 1);
}

.page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

// 响应式
@media (max-width: 768px) {
  .sidebar {
    width: 200px;
  }

  .sidebar-content {
    width: 200px;
  }

  .sidebar-logo {
    margin-bottom: 20px;
    padding: 0 12px;
  }

  .sidebar-nav {
    padding: 0 8px;
  }

  .nav-item {
    padding: 10px;
  }

  .nav-icon {
    width: 36px;
    height: 36px;
    font-size: 18px;
  }
}
</style>
