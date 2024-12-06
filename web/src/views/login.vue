<template>
  <div class="login">
    <el-form ref="loginRef" :model="loginForm" :rules="loginRules" class="login-form">
      <div class="title-container">
        <img src="../assets/images/login-logo.png" alt="" style="width: 210px; margin-bottom: 10px">
        <h3 class="title">T-Runner 自动化测试平台</h3>
      </div>
      <el-form-item prop="username">
        <el-input
            v-model="loginForm.username"
            type="text"
            size="large"
            auto-complete="off"
            placeholder="账号"
            :style="{background: 'transparent'}"
        >
          <template #prefix>
            <svg-icon icon-class="user" class="el-input__icon input-icon"/>
          </template>
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
          <template #prefix>
            <svg-icon icon-class="password" class="el-input__icon input-icon"/>
          </template>
        </el-input>
      </el-form-item>
      <el-form-item prop="code" v-if="captchaEnabled">
        <el-input
            v-model="loginForm.code"
            size="large"
            auto-complete="off"
            placeholder="验证码"
            style="width: 67%"
            @keyup.enter="handleLogin"
        >
          <template #prefix>
            <svg-icon icon-class="validCode" class="el-input__icon input-icon"/>
          </template>
        </el-input>
        <div class="login-code">
          <img :src="codeUrl" @click="getCode" class="login-code-img"/>
        </div>
      </el-form-item>
      <div style="display: flex;">
        <el-checkbox v-model="loginForm.rememberMe" style="margin:0px 0px 25px 0px;">记住密码</el-checkbox>
        <div style="flex-grow: 1"></div>
        <div style="margin:0px 0px 25px 0px;" v-if="register" class="register-link">
          <router-link class="link-type" :to="'/register'">立即注册</router-link>
        </div>
      </div>
      <el-form-item style="width:100%;">
        <el-button class="hover-button"
                   :loading="loading"
                   size="large"
                   type="info"
                   @click.prevent="handleLogin"
        >
          <span v-if="!loading">登 录</span>
          <span v-else>登 录 中...</span>
        </el-button>
      </el-form-item>
    </el-form>
    <!--  底部  -->
    <div class="el-login-footer">
<!--      <span>Copyright © 2024 insistence.tech All Rights Reserved.</span>-->
    </div>
  </div>
</template>

<script setup>
import {getCodeImg} from "@/api/login";
import Cookies from "js-cookie";
import {encrypt, decrypt} from "@/utils/jsencrypt";
import useUserStore from '@/store/modules/user'

const userStore = useUserStore()
const route = useRoute();
const router = useRouter();
const {proxy} = getCurrentInstance();

const loginForm = ref({
  username: "",
  password: "",
  rememberMe: false,
  code: "",
  uuid: ""
});

const loginRules = {
  username: [{required: true, trigger: "blur", message: "请输入您的账号"}],
  password: [{required: true, trigger: "blur", message: "请输入您的密码"}],
  code: [{required: true, trigger: "change", message: "请输入验证码"}]
};

const codeUrl = ref("");
const loading = ref(false);
// 验证码开关
const captchaEnabled = ref(true);
// 注册开关
const register = ref(false);
const redirect = ref(undefined);

watch(route, (newRoute) => {
  redirect.value = newRoute.query && newRoute.query.redirect;
}, {immediate: true});

function handleLogin() {
  proxy.$refs.loginRef.validate(valid => {
    if (valid) {
      loading.value = true;
      // 勾选了需要记住密码设置在 cookie 中设置记住用户名和密码
      if (loginForm.value.rememberMe) {
        Cookies.set("username", loginForm.value.username, {expires: 30});
        Cookies.set("password", encrypt(loginForm.value.password), {expires: 30});
        Cookies.set("rememberMe", loginForm.value.rememberMe, {expires: 30});
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
        router.push({path: redirect.value || "/", query: otherQueryParams});
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
    captchaEnabled.value = res.captchaEnabled === undefined ? true : res.captchaEnabled;
    register.value = res.registerEnabled === undefined ? false : res.registerEnabled;
    if (captchaEnabled.value) {
      codeUrl.value = "data:image/gif;base64," + res.img;
      loginForm.value.uuid = res.uuid;
    }
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
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  background-image: url("../assets/images/login-background.jpg");
  background-size: cover;

  :deep(.el-input__inner) {
    background: transparent !important;
    color: #ffffff;
  }

  :deep(.el-input__wrapper) {
    background: transparent !important;
    color: #454545;
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1);
  }

  .register-link {
    padding-top: 9px;
    font-size: 13px;
  }
  :deep(input:-webkit-autofill) {
	  box-shadow: 0 0 0 1000px transparent  !important;
	  /* 浏览器记住密码的底色的颜色 */
	  -webkit-text-fill-color: #fff !important;
	  /* 浏览器记住密码的字的颜色 */
	  transition: background-color 300000s ease-in-out 0s;
	  /* 通过延时渲染背景色变相去除背景颜色 */
	}
}

.hover-button:hover, .hover-button:focus {
  color: #ffffff;
  background: #5c5c59;
  border-color: #5c5c59;
}

.hover-button {
  width: 100%;
  background: #333330;
  border-color: #333330;

}


.login-form {
  border-radius: 6px;
  background: transparent;
  width: 450px;
  padding: 25px 25px 5px 25px;
  border: 0;

  .el-input {
    height: 47px;
    background: transparent !important;

    input {
      background: transparent;
      border: 0;
      -webkit-appearance: none;
      border-radius: 0;
      padding: 12px 5px 12px 15px;
      color: #fff;
      height: 47px;
      caret-color: #fff;
    }

    div.el-input__wrapper {
      background: transparent !important;
    }
  }
}

.input-icon {
  height: 39px;
  width: 14px;
  margin-left: 0px;
}


.el-form-item {
  border: 1px solid rgba(255, 255, 255, 0.1);
  //background: rgba(0, 0, 0, 0.1);
  border-radius: 5px;
  color: #454545;
}

.login-tip {
  font-size: 13px;
  text-align: center;
  color: #bfbfbf;
}

.login-code {
  width: 33%;
  height: 47px;
  float: right;
  align-content: center;

  img {
    cursor: pointer;
    vertical-align: middle;
  }
}

.el-login-footer {
  height: 40px;
  line-height: 40px;
  position: fixed;
  bottom: 0;
  width: 100%;
  text-align: center;
  color: #fff;
  font-family: Arial;
  font-size: 12px;
  letter-spacing: 1px;
}

.login-code-img {
  height: 47px;
  padding-left: 5px;
}

.title-container {
  text-align: center;

  .title {
    font-size: 30px;
    color: #fff;
    margin: 10px auto 40px 10px;
    text-align: center;
    font-weight: bold;
  }
}
</style>
