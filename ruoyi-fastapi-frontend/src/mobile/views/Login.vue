<template>
  <div class="m-app m-login">
    <div class="m-login__brand">
      <div class="m-login__mark">智</div>
      <h1>智慧金融</h1>
      <p>行情 · 舆情 · 交易</p>
    </div>
    <form class="m-login__form" @submit.prevent="handleLogin">
      <label>
        <span>账号</span>
        <input v-model.trim="form.username" autocomplete="username" placeholder="用户名" />
      </label>
      <label>
        <span>密码</span>
        <input v-model="form.password" type="password" autocomplete="current-password" placeholder="密码" />
      </label>
      <label v-if="captchaEnabled" class="m-login__captcha">
        <span>验证码</span>
        <div class="m-login__captcha-row">
          <input v-model.trim="form.code" autocomplete="off" placeholder="验证码" />
          <button type="button" class="m-login__img" @click="loadCaptcha">
            <img v-if="codeUrl" :src="codeUrl" alt="验证码" />
            <span v-else>点击获取</span>
          </button>
        </div>
      </label>
      <p v-if="error" class="m-login__err">{{ error }}</p>
      <button type="submit" class="m-login__btn" :disabled="loading">{{ loading ? '登录中…' : '登录' }}</button>
    </form>
  </div>
</template>

<script setup>
import Cookies from 'js-cookie'
import { getCodeImg } from '@/api/login'
import useUserStore from '@/store/modules/user'

const userStore = useUserStore()
const route = useRoute()
const router = useRouter()

const form = reactive({
  username: Cookies.get('username') || '',
  password: '',
  code: '',
  uuid: ''
})
const captchaEnabled = ref(true)
const codeUrl = ref('')
const loading = ref(false)
const error = ref('')

function loadCaptcha() {
  getCodeImg().then((res) => {
    const enabled = res.captchaEnabled
    if (enabled === undefined || enabled === null) {
      captchaEnabled.value = true
    } else if (typeof enabled === 'string') {
      captchaEnabled.value = !['false', '0', 'no', 'off'].includes(enabled.toLowerCase())
    } else {
      captchaEnabled.value = !!enabled
    }
    if (captchaEnabled.value) {
      codeUrl.value = res.img ? ('data:image/gif;base64,' + res.img) : ''
      form.uuid = res.uuid || ''
    }
  }).catch(() => {
    captchaEnabled.value = true
    codeUrl.value = ''
    error.value = '验证码加载失败，点击重试'
  })
}

async function handleLogin() {
  error.value = ''
  if (!form.username || !form.password) {
    error.value = '请输入账号和密码'
    return
  }
  if (captchaEnabled.value && !form.code) {
    error.value = '请输入验证码'
    return
  }
  loading.value = true
  try {
    Cookies.set('username', form.username, { expires: 30 })
    await userStore.login(form)
    const redirect = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/m')
      ? route.query.redirect
      : '/m'
    await router.replace(redirect)
  } catch (e) {
    error.value = (e && e.message) || '登录失败'
    if (captchaEnabled.value) loadCaptcha()
  } finally {
    loading.value = false
  }
}

loadCaptcha()
</script>

<style scoped lang="scss">
.m-login {
  min-height: 100dvh;
  padding: 48px 24px 32px;
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 40%, #f4f5f7 40%);
}
.m-login__brand {
  color: #fff;
  text-align: center;
  margin-bottom: 28px;
}
.m-login__mark {
  width: 56px;
  height: 56px;
  margin: 0 auto 12px;
  border-radius: 16px;
  background: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 800;
}
.m-login__brand h1 {
  margin: 0;
  font-size: 22px;
}
.m-login__brand p {
  margin: 6px 0 0;
  opacity: 0.7;
  font-size: 13px;
}
.m-login__form {
  background: #fff;
  border-radius: 16px;
  padding: 20px 16px 24px;
}
.m-login__form label {
  display: block;
  margin-bottom: 12px;
}
.m-login__form span {
  display: block;
  margin-bottom: 6px;
  color: #6b7280;
  font-size: 12px;
}
.m-login__form input {
  width: 100%;
  height: 44px;
  padding: 0 12px;
  border: 1px solid #ececef;
  border-radius: 10px;
  font-size: 16px;
}
.m-login__captcha-row {
  display: flex;
  gap: 8px;
}
.m-login__captcha-row input { flex: 1; }
.m-login__img {
  width: 110px;
  height: 44px;
  border: 1px solid #ececef;
  border-radius: 10px;
  padding: 0;
  background: #f9fafb;
  overflow: hidden;
}
.m-login__img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.m-login__err {
  color: #e5484d;
  font-size: 13px;
  margin: 0 0 10px;
}
.m-login__btn {
  width: 100%;
  height: 46px;
  border: 0;
  border-radius: 10px;
  background: #111827;
  color: #fff;
  font-size: 16px;
  font-weight: 700;
}
.m-login__btn:disabled { opacity: 0.6; }
</style>
