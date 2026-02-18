import { createRouter, createWebHistory } from 'vue-router'

// 使用静态导入，避免懒加载延迟
import Dashboard from '@/views/Dashboard.vue'
import Analysis from '@/views/Analysis.vue'
import AiAssistant from '@/views/AiAssistant.vue'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard
  },
  {
    path: '/analysis',
    name: 'Analysis',
    component: Analysis
  },
  {
    path: '/ai',
    name: 'AiAssistant',
    component: AiAssistant
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
