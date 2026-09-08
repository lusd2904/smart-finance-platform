<template>
  <div class="login-page">
    <CyberBackground quiet />
    <div class="top-bar">
      <ThemeSwitcher />
    </div>

    <div class="glass-login-box glass-panel">
      <div class="login-header">
        <h1 class="glow-title">智慧金融</h1>
      </div>

      <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" class="login-form" @keyup.enter="handleLogin">
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="账号"
            size="large"
            :prefix-icon="User"
            class="cyber-input"
            autocomplete="username"
            clearable
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            size="large"
            :prefix-icon="Lock"
            class="cyber-input"
            autocomplete="current-password"
            show-password
            clearable
          />
        </el-form-item>
        <el-form-item v-if="captchaEnabled" prop="code">
          <div class="captcha-row">
            <el-input
              v-model="loginForm.code"
              placeholder="验证码"
              size="large"
              class="cyber-input"
              autocomplete="off"
            />
            <button type="button" class="captcha-fetch" :disabled="captchaLoading" @click="getCode">
              <img v-if="codeUrl" :src="codeUrl" class="login-code-img" alt="验证码" />
              <span v-else>{{ captchaLoading ? '获取中…' : captchaHint }}</span>
            </button>
          </div>
        </el-form-item>
        <div class="form-tools">
          <el-checkbox v-model="rememberMe">记住密码</el-checkbox>
        </div>
        <el-form-item>
          <el-button type="primary" size="large" class="login-button cyber-btn" :loading="loading" @click="handleLogin">
            {{ loading ? '登 录 中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-footer">
        <button type="button" class="demo-link" @click="enterDemo">演示</button>
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
const captchaEnabled = ref(true)
const captchaLoading = ref(false)
const captchaHint = ref('点击获取')
const codeUrl = ref('')
const loginForm = reactive({
  username: '',
  password: '',
  code: '',
  uuid: ''
})

const loginRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  code: [
    {
      validator: (_rule, value, callback) => {
        if (captchaEnabled.value && !value) {
          callback(new Error('请输入验证码'))
          return
        }
        callback()
      },
      trigger: 'blur'
    }
  ]
}

async function getCode() {
  captchaLoading.value = true
  captchaHint.value = '获取中…'
  try {
    const res = await getCodeImg()
    const enabled = res.captchaEnabled
    captchaEnabled.value = enabled === undefined ? true : !!enabled
    if (captchaEnabled.value) {
      codeUrl.value = res.img ? `data:image/gif;base64,${res.img}` : ''
      loginForm.uuid = res.uuid || ''
      captchaHint.value = codeUrl.value ? '点击刷新' : '点击获取'
    } else {
      codeUrl.value = ''
      loginForm.uuid = ''
      loginForm.code = ''
    }
  } catch {
    codeUrl.value = ''
    captchaHint.value = '点击重试'
    ElMessage.warning('验证码获取失败，请点击重试')
  } finally {
    captchaLoading.value = false
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
    if (captchaEnabled.value) {
      codeUrl.value = ''
      captchaHint.value = '点击获取'
    }
    ElMessage.error(error?.message || '登录失败')
  } finally {
    loading.value = false
  }
}

function enterDemo() {
  userStore.enterDemoSession()
  ElMessage.success('已进入演示')
  router.replace('/index')
}

onMounted(() => {
  applyTheme()
  const saved = Cookies.get('username')
  if (saved) {
    loginForm.username = saved
    rememberMe.value = true
  }
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
  padding: 50px 40px;
  display: flex;
  flex-direction: column;
  transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

.glass-login-box:hover {
  transform: translateY(-5px);
  border-color: color-mix(in srgb, var(--accent) 30%, transparent) !important;
  box-shadow: 0 10px 50px color-mix(in srgb, var(--accent) 10%, transparent) !important;
}

.login-header {
  text-align: center;
  margin-bottom: 36px;
}

.glow-title {
  font-size: 2.1rem;
  margin: 0;
  font-weight: 800;
  color: var(--text-emphasis);
  letter-spacing: 4px;
}

.captcha-row {
  display: flex;
  gap: 10px;
  width: 100%;
}

.captcha-fetch {
  flex: 0 0 112px;
  min-height: 40px;
  padding: 0 10px;
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--border-soft));
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-soft));
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.captcha-fetch:disabled {
  opacity: 0.7;
  cursor: wait;
}

.login-code-img {
  height: 36px;
  max-width: 100px;
  border-radius: 6px;
  display: block;
}

.form-tools {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  margin-bottom: 22px;
}

.login-button.cyber-btn {
  width: 100%;
  height: 50px;
  letter-spacing: 8px;
  font-weight: 700;
  font-size: 1rem;
  border-radius: 25px;
  color: var(--accent-ink) !important;
}

.login-footer {
  margin-top: 24px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  display: grid;
  gap: 8px;
}

.demo-link {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.demo-link:hover {
  color: var(--text-secondary);
}

:deep(.cyber-input .el-input__wrapper) {
  background-color: var(--surface-soft) !important;
  box-shadow: none !important;
  border-bottom: 2px solid var(--border-soft) !important;
  border-radius: 6px 6px 0 0;
}

:deep(.cyber-input .el-input__wrapper.is-focus) {
  border-bottom: 2px solid var(--accent) !important;
  background-color: color-mix(in srgb, var(--accent) 5%, var(--surface-soft)) !important;
}
</style>
