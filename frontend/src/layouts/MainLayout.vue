<template>
  <div class="main-layout">
    <!-- 动态背景 -->
    <div class="animated-grid-bg"></div>

    <!-- 侧边栏导航 -->
    <aside class="sidebar">
      <!-- 侧边栏内容 -->
      <div class="sidebar-content">
        <div class="sidebar-logo">
          <div class="logo-dot"></div>
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
            <el-icon>
              <component :is="item.icon" />
            </el-icon>
          </router-link>
        </nav>

        <!-- 用户信息 -->
        <div class="sidebar-user">
          <el-avatar :size="36">管</el-avatar>
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
import { useRoute } from 'vue-router'
import { Monitor, TrendCharts, ChatLineRound } from '@element-plus/icons-vue'

const route = useRoute()

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
    path: '/ai',
    title: 'AI助理',
    subtitle: 'AI',
    icon: ChatLineRound
  }
]

// 判断当前路由是否激活
const isActive = (path) => {
  return route.path === path
}

</script>

<style scoped lang="scss">
.main-layout {
  min-height: 100vh;
  position: relative;
  display: flex;
}

// 侧边栏导航
.sidebar {
  position: relative;
  height: 100vh;
  width: 84px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border-right: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: 6px 0 24px rgba(15, 23, 42, 0.08);
  z-index: 10;
  overflow: hidden;
}

// 侧边栏内容
.sidebar-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24px 0;
}

// Logo区域
.sidebar-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 40px;

  .logo-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #4facfe;
    box-shadow: 0 0 14px rgba(79, 172, 254, 0.9);
  }
}

// 导航菜单
.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 28px;
  align-items: center;

  .nav-item {
    width: 44px;
    height: 44px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    color: #94a3b8;
    transition: all 0.3s ease;

    &:hover {
      color: #4facfe;
      background: rgba(79, 172, 254, 0.12);
    }

    &.active {
      color: #4facfe;
      background: rgba(79, 172, 254, 0.18);
      box-shadow: 0 8px 20px rgba(79, 172, 254, 0.2);
    }
  }
}

// 用户信息
.sidebar-user {
  display: flex;
  justify-content: center;
  padding: 20px 0;
  margin-top: auto;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}

// 主内容区 - 参考国家平台设计，固定高度布局
.main-content {
  flex: 1;
  width: 100%;
  height: 100vh;
  overflow: auto;
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
@media (max-width: 900px) {
  .sidebar {
    display: none;
  }
}
</style>
