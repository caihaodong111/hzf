<template>
  <div class="login-container">
    <!-- 动态背景 -->
    <div class="animated-grid-bg"></div>

    <!-- 登录卡片 -->
    <div class="login-card glass-card">
      <!-- Logo区域 -->
      <div class="login-logo">
        <div class="logo-icon">
          <svg viewBox="0 0 100 100">
            <!-- 水波纹图标 -->
            <circle cx="50" cy="50" r="40" fill="rgba(24, 144, 255, 0.1)" />
            <circle cx="50" cy="50" r="30" fill="rgba(24, 144, 255, 0.2)" />
            <circle cx="50" cy="50" r="20" fill="rgba(24, 144, 255, 0.3)" />
          </svg>
        </div>
        <h1 class="login-title">智慧渔业监控系统</h1>
        <p class="login-subtitle">Smart Aquaculture Monitoring System</p>
      </div>

      <!-- 登录表单 -->
      <el-form :model="loginForm" class="login-form">
        <el-form-item>
          <el-input
            v-model="loginForm.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>

        <el-form-item>
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            class="login-btn"
            size="large"
            :loading="loading"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 底部装饰 -->
      <div class="login-footer">
        <p>智慧渔业 · 科技养殖</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '@/api/auth'

const router = useRouter()
const loading = ref(false)

const loginForm = ref({
  username: 'admin',
  password: 'admin123'
})

const handleLogin = async () => {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  loading.value = true

  try {
    const response = await login(loginForm.value.username, loginForm.value.password)

    if (response.success) {
      // 保存 token 和用户信息
      localStorage.setItem('token', response.data.token)
      localStorage.setItem('user', JSON.stringify(response.data.user))

      ElMessage.success('登录成功')
      // 跳转到首页
      router.push('/')
    } else {
      ElMessage.error(response.message || '登录失败')
    }
  } catch (error) {
    console.error('登录错误:', error)
    ElMessage.error(error.response?.data?.message || '登录失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.login-card {
  width: 420px;
  padding: 48px;
  animation: cardFadeIn 0.6s ease-out;
}

@keyframes cardFadeIn {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.login-logo {
  text-align: center;
  margin-bottom: 40px;
}

.logo-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
  animation: logoFloat 3s ease-in-out infinite;
}

@keyframes logoFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

.login-title {
  font-size: 28px;
  font-weight: 600;
  color: #1F2937;
  margin-bottom: 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.login-subtitle {
  font-size: 14px;
  color: #6B7280;
  font-weight: 400;
  letter-spacing: 1px;
}

.login-form {
  margin-top: 32px;
}

.login-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 500;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.login-footer {
  text-align: center;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid rgba(24, 144, 255, 0.1);

  p {
    font-size: 12px;
    color: #6B7280;
    opacity: 0.8;
  }
}
</style>
