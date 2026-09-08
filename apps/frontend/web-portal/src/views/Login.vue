<template>
  <div class="login-page">
    <CyberBackground />
    <div class="top-bar">
      <ThemeSwitcher />
    </div>

    <div class="glass-login-box glass-panel">
      <div class="login-header">
        <h1 class="glow-title">智慧金融</h1>
        <p class="subtitle">行情 · 舆情 · 量化 · 交易</p>
      </div>

      <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" class="login-form" @keyup.enter="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="loginForm.username" placeholder="账号" size="large" :prefix-icon="User" class="cyber-input" clearable />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="loginForm.password" type="password" placeholder="密码" size="large" :prefix-icon="Lock" class="cyber-input" show-password clearable />
        </el-form-item>
        <el-form-item v-if="captchaEnabled" prop="code">
          <div class="captcha-row">
            <el-input v-model="loginForm.code" placeholder="验证码" size="large" class="cyber-input" />
            <img v-if="codeUrl" :src="codeUrl" class="login-code-img" alt="captcha" @click="getCode" />
            <el-button v-else size="large" @click="getCode">刷新</el-button>
          </div>
        </el-form-item>
        <div class="form-tools">
          <el-checkbox v-model="rememberMe">记住账号</el-checkbox>
          <button type="button" class="endpoint-toggle" @click="enterDemo">演示模式</button>
        </div>
        <el-form-item>
          <el-button type="primary" size="large" class="login-button cyber-btn" :loading="loading" @click="handleLogin">
            系统登录
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-footer">
        <p>对齐长桥 web-portal 玻璃主题 · 旧前端仍保留</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import Cookies from 'js-cookie'
import ThemeSwitcher from '@/components/layout/ThemeSwitcher.vue'
import CyberBackground from '@/components/layout/CyberBackground.vue'
import { getCodeImg } from '@/api/auth'
import { useUserStore } from '@/store/user'
import { useTheme } from '@/composables/useTheme'

const { applyTheme } = useTheme()
const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const loginFormRef = ref(null)
const loading = ref(false)
const rememberMe = ref(false)
const captchaEnabled = ref(false)
const codeUrl = ref('')
const loginForm = reactive({
  username: '',
  password: '',
  code: '',
  uuid: ''
})

const loginRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function getCode() {
  try {
    const res = await getCodeImg()
    const enabled = res.captchaEnabled
    captchaEnabled.value = enabled === undefined ? false : !!enabled
    if (captchaEnabled.value) {
      codeUrl.value = res.img ? `data:image/gif;base64,${res.img}` : ''
      loginForm.uuid = res.uuid || ''
    }
  } catch {
    captchaEnabled.value = false
  }
}

async function handleLogin() {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate()
  loading.value = true
  try {
    await userStore.login(loginForm)
    if (rememberMe.value) {
      Cookies.set('username', loginForm.username, { expires: 30 })
    } else {
      Cookies.remove('username')
    }
    ElMessage.success('登录成功')
    router.replace(route.query.redirect || '/index')
  } catch (error) {
    if (captchaEnabled.value) getCode()
    ElMessage.error(error?.message || '登录失败，可使用演示模式预览新门户')
  } finally {
    loading.value = false
  }
}

function enterDemo() {
  userStore.enterDemoSession()
  ElMessage.success('已进入演示会话（标注为 stub 数据）')
  router.replace('/index')
}

onMounted(() => {
  applyTheme()
  const saved = Cookies.get('username')
  if (saved) {
    loginForm.username = saved
    rememberMe.value = true
  }
  getCode()
})
</script>

<style scoped lang="scss">
.login-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  overflow: hidden;
}

.top-bar {
  position: absolute;
  top: 24px;
  right: 24px;
  z-index: 10;
}

.glass-login-box {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 440px;
  padding: 48px 40px;
}

.login-header {
  text-align: center;
  margin-bottom: 36px;
}

.glow-title {
  font-size: 2.1rem;
  margin: 0 0 10px;
  font-weight: 800;
  color: var(--text-emphasis);
  letter-spacing: 4px;
}

.subtitle {
  font-size: 0.8rem;
  color: var(--text-secondary);
  letter-spacing: 5px;
}

.captcha-row {
  display: flex;
  gap: 10px;
  width: 100%;
}

.login-code-img {
  height: 40px;
  border-radius: 8px;
  cursor: pointer;
}

.form-tools {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 22px;
}

.endpoint-toggle {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: 0.85rem;
}

.login-button.cyber-btn {
  width: 100%;
  height: 48px;
  letter-spacing: 4px;
  font-weight: 700;
}

.login-footer {
  margin-top: 24px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

:deep(.cyber-input .el-input__wrapper) {
  background-color: var(--surface-soft) !important;
  border-radius: 8px;
}
</style>
