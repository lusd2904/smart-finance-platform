<template>
  <div class="login" :data-theme="themeKey">
    <!-- 赛博动态背景（节点 + 穿梭光），颜色跟随 settingsStore.isDark -->
    <div class="login-bg">
      <cyber-background />
    </div>

    <div class="login-top-bar">
      <div class="logo">
        <h2 class="glow-title">智慧金融 · NEXUS</h2>
        <span class="logo-sub">QUANT · SENTIMENT · MARKET</span>
      </div>
      <div class="skin-switcher glass-panel" role="group" aria-label="界面皮肤">
        <button
          type="button"
          class="skin-option"
          :class="{ active: !isDark }"
          @click="selectSkin(false)"
        >
          <el-icon><Sunny /></el-icon>
          <span>浅色</span>
        </button>
        <button
          type="button"
          class="skin-option"
          :class="{ active: isDark }"
          @click="selectSkin(true)"
        >
          <el-icon><Moon /></el-icon>
          <span>深色</span>
        </button>
      </div>
    </div>

    <div class="login-panel glass-panel">
      <!-- 左侧品牌区（极简，避免营销文案噪音） -->
      <div class="login-brand">
        <div class="brand-logo">
          <svg-icon icon-class="chart" class="brand-icon" />
        </div>
        <h2>智慧金融分析平台</h2>
        <p>行情 · 舆情 · 量化</p>
      </div>
      <!-- 右侧表单区 -->
      <el-form ref="loginRef" :model="loginForm" :rules="loginRules" class="login-form">
        <h3 class="title">{{ title }}</h3>
        <p class="subtitle">欢迎登录，请输入您的账号信息</p>
      <el-form-item prop="username">
        <el-input
          v-model="loginForm.username"
          type="text"
          size="large"
          auto-complete="off"
          placeholder="账号"
        >
          <template #prefix><svg-icon icon-class="user" class="el-input__icon input-icon" /></template>
        </el-input>
      </el-form-item>
      <el-form-item prop="password">
        <el-input
          v-model="loginForm.password"
          type="password"
          size="large"
          auto-complete="off"
          placeholder="密码"
          @keyup.enter="handleLogin"
        >
          <template #prefix><svg-icon icon-class="password" class="el-input__icon input-icon" /></template>
        </el-input>
      </el-form-item>
      <el-form-item prop="code" v-if="captchaEnabled">
        <el-input
          v-model="loginForm.code"
          size="large"
          auto-complete="off"
          placeholder="验证码"
          style="width: 63%"
          @keyup.enter="handleLogin"
        >
          <template #prefix><svg-icon icon-class="validCode" class="el-input__icon input-icon" /></template>
        </el-input>
        <div class="login-code">
          <img :src="codeUrl" @click="getCode" class="login-code-img"/>
        </div>
      </el-form-item>
      <el-checkbox v-model="loginForm.rememberMe" style="margin:0px 0px 25px 0px;">记住密码</el-checkbox>
      <el-form-item style="width:100%;">
        <el-button
          :loading="loading"
          size="large"
          type="primary"
          style="width:100%;"
          @click.prevent="handleLogin"
        >
          <span v-if="!loading">登 录</span>
          <span v-else>登 录 中...</span>
        </el-button>
        <div style="float: right;" v-if="register">
          <router-link class="link-type" :to="'/register'">立即注册</router-link>
        </div>
      </el-form-item>
      </el-form>
    </div>
    <!--  底部  -->
    <div class="el-login-footer">
      <span>{{ footerContent }}</span>
    </div>
  </div>
</template>

<script setup>
import { getCodeImg } from "@/api/login";
import Cookies from "js-cookie";
import { encrypt, decrypt } from "@/utils/jsencrypt";
import { Sunny, Moon } from '@element-plus/icons-vue'
import useUserStore from '@/store/modules/user'
import useSettingsStore from '@/store/modules/settings'
import defaultSettings from '@/settings'
import CyberBackground from '@/components/CyberBackground/index.vue'

const title = "智慧金融分析平台";
const footerContent = defaultSettings.footerContent
const userStore = useUserStore();
const settingsStore = useSettingsStore()
const route = useRoute();
const router = useRouter();
const { proxy } = getCurrentInstance();

const isDark = computed(() => settingsStore.isDark)
const themeKey = computed(() => settingsStore.themeKey)

const loginForm = ref({
  username: "",
  password: "",
  rememberMe: false,
  code: "",
  uuid: ""
});

const loginRules = ref({
  username: [{ required: true, trigger: "blur", message: "请输入您的账号" }],
  password: [{ required: true, trigger: "blur", message: "请输入您的密码" }]
});

const codeUrl = ref("");
const loading = ref(false);
// 验证码开关
const captchaEnabled = ref(true);
// 注册开关
const register = ref(false);
const redirect = ref(undefined);

watch(route, (newRoute) => {
    redirect.value = newRoute.query && newRoute.query.redirect;
}, { immediate: true });

function selectSkin(dark) {
  settingsStore.setDark(dark)
}

function handleLogin() {
  proxy.$refs.loginRef.validate(valid => {
    if (valid) {
      loading.value = true;
      // 勾选了需要记住密码设置在 cookie 中设置记住用户名和密码
      if (loginForm.value.rememberMe) {
        Cookies.set("username", loginForm.value.username, { expires: 30 });
        Cookies.set("password", encrypt(loginForm.value.password), { expires: 30 });
        Cookies.set("rememberMe", loginForm.value.rememberMe, { expires: 30 });
      } else {
        // 否则移除
        Cookies.remove("username");
        Cookies.remove("password");
        Cookies.remove("rememberMe");
      }
      // 调用action的登录方法
      userStore.login(loginForm.value).then(() => {
        const query = route.query;
        const otherQueryParams = Object.keys(query).reduce((acc, cur) => {
          if (cur !== "redirect") {
            acc[cur] = query[cur];
          }
          return acc;
        }, {});
        router.push({ path: redirect.value || "/portal", query: otherQueryParams });
      }).catch(() => {
        loading.value = false;
        // 重新获取验证码
        if (captchaEnabled.value) {
          getCode();
        }
      });
    }
  });
}

function getCode() {
  getCodeImg().then(res => {
    // 兼容 boolean / 字符串；接口异常时默认展示验证码
    const enabled = res.captchaEnabled;
    if (enabled === undefined || enabled === null) {
      captchaEnabled.value = true;
    } else if (typeof enabled === 'string') {
      captchaEnabled.value = !['false', '0', 'no', 'off'].includes(enabled.toLowerCase());
    } else {
      captchaEnabled.value = !!enabled;
    }
    register.value = res.registerEnabled === undefined ? false : !!res.registerEnabled;
    if (captchaEnabled.value) {
      codeUrl.value = res.img ? ("data:image/gif;base64," + res.img) : "";
      loginForm.value.uuid = res.uuid || "";
    }
  }).catch(() => {
    // 拉取失败仍展示验证码输入框，避免用户误以为系统关闭了验证码
    captchaEnabled.value = true;
    codeUrl.value = "";
  });
}

function getCookie() {
  const username = Cookies.get("username");
  const password = Cookies.get("password");
  const rememberMe = Cookies.get("rememberMe");
  loginForm.value = {
    username: username === undefined ? loginForm.value.username : username,
    password: password === undefined ? loginForm.value.password : decrypt(password),
    rememberMe: rememberMe === undefined ? false : Boolean(rememberMe)
  };
}

onMounted(() => {
  settingsStore.applyTheme()
})

getCode();
getCookie();
</script>

<style lang='scss' scoped>
.login {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  overflow: hidden;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.login[data-theme='glass-dark'] {
  background:
    radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.42) 0%, transparent 45%),
    radial-gradient(circle at 90% 80%, rgba(147, 51, 234, 0.4) 0%, transparent 45%),
    radial-gradient(circle at 50% 50%, rgba(16, 185, 129, 0.22) 0%, transparent 60%),
    #020617;
  color: #e2e8f0;
}

.login[data-theme='glass-light'] {
  background:
    radial-gradient(circle at 10% 20%, rgba(96, 165, 250, 0.55) 0%, transparent 45%),
    radial-gradient(circle at 90% 80%, rgba(192, 132, 252, 0.5) 0%, transparent 45%),
    radial-gradient(circle at 50% 50%, rgba(52, 211, 153, 0.35) 0%, transparent 60%),
    #e2e8f0;
  color: #0f172a;
}

/* 动态赛博背景：保持高可见度 */
.login-bg {
  position: absolute;
  inset: 0;
  opacity: 1;
  pointer-events: none;
  z-index: 0;
}

.login-top-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 22px 40px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 10;
}

.logo {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.glow-title {
  margin: 0;
  font-size: 1.45rem;
  font-weight: 800;
  letter-spacing: 2px;
  background: linear-gradient(90deg, #38bdf8, #a78bfa, #34d399);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 0 18px rgba(56, 189, 248, 0.35));
}

.logo-sub {
  font-size: 11px;
  letter-spacing: 2px;
  opacity: 0.65;
}

.skin-switcher {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border-radius: 999px !important;
}

.skin-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 7px 14px;
  border-radius: 999px;
  font-size: 13px;
  color: inherit;
  opacity: 0.7;
  transition: all 0.2s ease;
}

.skin-option.active {
  opacity: 1;
  background: rgba(56, 189, 248, 0.18);
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.28) inset;
}

.login[data-theme='glass-light'] .skin-option.active {
  background: rgba(37, 99, 235, 0.12);
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.22) inset;
}

/* 主面板：玻璃拟态 */
.login-panel {
  position: relative;
  z-index: 1;
  display: flex;
  border-radius: 18px;
  overflow: hidden;
}

.glass-panel {
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.28);
}

.login[data-theme='glass-light'] .glass-panel {
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.08);
}

/* 左侧品牌区 */
.login-brand {
  width: 360px;
  padding: 48px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: linear-gradient(150deg, rgba(56, 189, 248, 0.12), rgba(99, 102, 241, 0.18));
  border-right: 1px solid rgba(255, 255, 255, 0.1);

  .brand-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 16px;
    background: linear-gradient(135deg, #00c3ff, #6366f1);
    box-shadow: 0 6px 22px rgba(0, 195, 255, 0.35);
    margin-bottom: 26px;

    .brand-icon {
      width: 28px;
      height: 28px;
      color: #fff;
    }
  }

  h2 {
    margin: 0 0 10px;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 2px;
  }

  p {
    margin: 0;
    font-size: 13px;
    letter-spacing: 1px;
    color: #38bdf8;
  }
}

.login[data-theme='glass-light'] .login-brand {
  background: linear-gradient(150deg, rgba(96, 165, 250, 0.18), rgba(192, 132, 252, 0.16));
  border-right: 1px solid rgba(15, 23, 42, 0.08);

  h2 {
    color: #0f172a;
  }

  p {
    color: #2563eb;
  }
}

.login[data-theme='glass-dark'] .login-brand {
  color: #e2e8f0;

  h2 {
    color: #f8fafc;
  }
}

.title {
  margin: 0 0 8px;
  text-align: left;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: 1px;
}

.subtitle {
  margin: 0 0 26px;
  font-size: 13px;
  opacity: 0.72;
}

.login[data-theme='glass-dark'] .title {
  color: #f1f5f9;
}

.login[data-theme='glass-dark'] .subtitle {
  color: #94a3b8;
}

.login[data-theme='glass-light'] .title {
  color: #0f172a;
}

.login[data-theme='glass-light'] .subtitle {
  color: #475569;
}

/* 右侧表单区 */
.login-form {
  width: 380px;
  padding: 48px 40px 30px;
  background: transparent;

  .el-input {
    height: 42px;
    input {
      height: 42px;
    }
  }

  :deep(.el-input__wrapper) {
    border-radius: 10px;
  }

  :deep(.el-button--primary) {
    height: 42px;
    border-radius: 10px;
    background: #6366f1;
    border: none;
    letter-spacing: 6px;
    font-size: 15px;

    &:hover {
      background: #4f46e5;
    }
  }

  .link-type {
    color: #6366f1;
  }

  .input-icon {
    height: 39px;
    width: 14px;
    margin-left: 0px;
  }
}

.login[data-theme='glass-dark'] .login-form {
  :deep(.el-input__wrapper) {
    background: rgba(15, 23, 42, 0.55);
    box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.35) inset;

    &.is-focus {
      box-shadow: 0 0 0 1px #38bdf8 inset;
    }
  }

  :deep(.el-input__inner) {
    color: #e2e8f0;

    &::placeholder {
      color: #94a3b8;
    }
  }

  :deep(.el-checkbox__label) {
    color: #94a3b8;
  }

  .input-icon {
    color: #94a3b8;
  }
}

.login[data-theme='glass-light'] .login-form {
  :deep(.el-input__wrapper) {
    background: rgba(255, 255, 255, 0.78);
    box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.12) inset;

    &.is-focus {
      box-shadow: 0 0 0 1px #2563eb inset;
    }
  }

  :deep(.el-input__inner) {
    color: #0f172a;

    &::placeholder {
      color: #64748b;
    }
  }

  :deep(.el-checkbox__label) {
    color: #475569;
  }

  .input-icon {
    color: #64748b;
  }

  .link-type {
    color: #2563eb;
  }
}

.login-tip {
  font-size: 13px;
  text-align: center;
  color: #bfbfbf;
}

.login-code {
  width: 33%;
  height: 42px;
  float: right;

  img {
    cursor: pointer;
    vertical-align: middle;
    border-radius: 8px;
  }
}

.el-login-footer {
  height: 40px;
  line-height: 40px;
  position: fixed;
  bottom: 0;
  width: 100%;
  text-align: center;
  font-family: Arial;
  z-index: 2;
  font-size: 12px;
  letter-spacing: 1px;
  opacity: 0.75;
}

.login[data-theme='glass-dark'] .el-login-footer {
  color: rgba(148, 163, 184, 0.9);
}

.login[data-theme='glass-light'] .el-login-footer {
  color: rgba(15, 23, 42, 0.55);
}

.login-code-img {
  height: 42px;
  padding-left: 12px;
}

@media (max-width: 900px) {
  .login-top-bar {
    padding: 16px;
  }
}

/* 窄屏适配：隐藏品牌栏 */
@media (max-width: 820px) {
  .login-brand {
    display: none;
  }
}
</style>
