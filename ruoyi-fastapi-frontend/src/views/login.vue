<template>
  <div class="login">
    <!-- 赛博动态背景（节点 + 穿梭光） -->
    <div class="login-bg">
      <cyber-background />
    </div>
    <div class="login-panel">
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
import useUserStore from '@/store/modules/user'
import defaultSettings from '@/settings'
import CyberBackground from '@/components/CyberBackground/index.vue'

const title = "智慧金融分析平台";
const footerContent = defaultSettings.footerContent
const userStore = useUserStore();
const route = useRoute();
const router = useRouter();
const { proxy } = getCurrentInstance();

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
  background:
    radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.35) 0%, transparent 45%),
    radial-gradient(circle at 90% 80%, rgba(147, 51, 234, 0.32) 0%, transparent 45%),
    radial-gradient(circle at 50% 50%, rgba(16, 185, 129, 0.18) 0%, transparent 60%),
    #020617;
}

/* 动态赛博背景：保持高可见度 */
.login-bg {
  position: absolute;
  inset: 0;
  opacity: 1;
  pointer-events: none;
  z-index: 0;
}

/* 主面板：玻璃拟态 */
.login-panel {
  position: relative;
  z-index: 1;
  display: flex;
  border-radius: 18px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
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
  color: #e2e8f0;

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
    color: #f8fafc;
  }

  p {
    margin: 0;
    font-size: 13px;
    letter-spacing: 1px;
    color: #38bdf8;
  }
}

.title {
  margin: 0 0 8px;
  text-align: left;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: 1px;
  color: #f1f5f9;
}

.subtitle {
  margin: 0 0 26px;
  font-size: 13px;
  color: #94a3b8;
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
    background: rgba(15, 23, 42, 0.55);
    box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.35) inset;
    border-radius: 10px;

    &.is-focus {
      box-shadow: 0 0 0 1px #38bdf8 inset;
    }
  }

  :deep(.el-input__inner) {
    color: #e2e8f0;
  }

  :deep(.el-checkbox__label) {
    color: #94a3b8;
  }

  :deep(.el-input__inner) {
    color: #303133;

    &::placeholder {
      color: #a8abb2;
    }
  }

  :deep(.el-checkbox__label) {
    color: #606266;
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
    color: #909399;
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
  color: rgba(148, 163, 184, 0.9);
  font-family: Arial;
  z-index: 2;
  font-size: 12px;
  letter-spacing: 1px;
  z-index: 1;
}

.login-code-img {
  height: 42px;
  padding-left: 12px;
}

/* 窄屏适配：隐藏品牌栏 */
@media (max-width: 820px) {
  .login-brand {
    display: none;
  }
}
</style>
