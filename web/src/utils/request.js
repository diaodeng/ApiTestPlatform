import axios from 'axios'
import { ElNotification , ElMessageBox, ElMessage, ElLoading } from 'element-plus'
import { getToken } from '@/utils/auth'
import errorCode from '@/utils/errorCode'
import { tansParams, blobValidate } from '@/utils/ruoyi'
import cache from '@/plugins/cache'
import { saveAs } from 'file-saver'
import useUserStore from '@/store/modules/user'

let downloadLoadingInstance;
// 是否显示重新登录
export let isRelogin = { show: false };

/**
 * 将接口返回或异常对象转换为可展示的错误文本。
 * @param {unknown} value 接口 msg、异常对象或响应数据
 * @param {string} fallback 未提取到有效文本时使用的兜底提示
 * @returns {string} 可直接展示给用户的错误文本
 */
const normalizeErrorMessage = (value, fallback = errorCode['default']) => {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value === 'string') return value
  if (value instanceof Error && value.message) return value.message
  if (typeof value === 'object') {
    const source = value
    const candidates = [
      source.msg,
      source.message,
      source.errorMessage,
      source.detail,
      source.data?.msg,
      source.data?.message,
      source.response?.data?.msg,
      source.response?.data?.message,
      source.response?.data?.detail
    ]
    for (const candidate of candidates) {
      const normalized = normalizeErrorMessage(candidate, '')
      if (normalized) return normalized
    }
    try {
      const text = JSON.stringify(value)
      return text && text !== '{}' ? text : fallback
    } catch (_error) {
      return fallback
    }
  }
  return String(value)
}

/**
 * 判断请求是否禁用全局错误提示（ElMessage）。
 * @param {import('axios').AxiosRequestConfig | undefined} config 请求配置
 * @returns {boolean} true=显示全局提示，false=静默
 */
const shouldUseGlobalMessage = (config) => {
  const headers = (config && config.headers) || {}
  const headerValue = headers.showErrorMessage
  const configValue = config && config.showErrorMessage
  const explicitValue = headerValue !== undefined ? headerValue : configValue
  if (explicitValue === false || explicitValue === 0 || explicitValue === '0') return false
  if (typeof explicitValue === 'string' && explicitValue.toLowerCase() === 'false') return false
  return true
}

/**
 * 判断请求是否禁用全局通知提示（ElNotification）。
 * @param {import('axios').AxiosRequestConfig | undefined} config 请求配置
 * @returns {boolean} true=显示全局通知，false=静默
 */
const shouldUseGlobalNotification = (config) => {
  const headers = (config && config.headers) || {}
  const headerValue = headers.showErrorNotification
  const configValue = config && config.showErrorNotification
  const explicitValue = headerValue !== undefined ? headerValue : configValue
  if (explicitValue === undefined) return shouldUseGlobalMessage(config)
  if (explicitValue === false || explicitValue === 0 || explicitValue === '0') return false
  if (typeof explicitValue === 'string' && explicitValue.toLowerCase() === 'false') return false
  return true
}

axios.defaults.headers['Content-Type'] = 'application/json;charset=utf-8'
// 创建axios实例
const service = axios.create({
  // axios中请求配置有baseURL选项，表示请求URL公共部分
  // baseURL: window.BASE_API,
  // 超时
  timeout: 10*60*1000
})

// request拦截器
service.interceptors.request.use(config => {
  config.baseURL =
    window.__APP_CONFIG__?.BASE_API ||
    import.meta.env.VITE_APP_BASE_API ||
    ""
  // 是否需要设置 token
  const isToken = (config.headers || {}).isToken === false
  // 是否需要防止数据重复提交
  const isRepeatSubmit = (config.headers || {}).repeatSubmit === false
  if (getToken() && !isToken) {
    config.headers['Authorization'] = 'Bearer ' + getToken() // 让每个请求携带自定义token 请根据实际情况自行修改
  }
  // get请求映射params参数
  if (config.method === 'get' && config.params) {
    let url = config.url + '?' + tansParams(config.params);
    url = url.slice(0, -1);
    config.params = {};
    config.url = url;
  }
  if (!isRepeatSubmit && (config.method === 'post' || config.method === 'put')) {
    const requestObj = {
      url: config.url,
      data: typeof config.data === 'object' ? JSON.stringify(config.data) : config.data,
      time: new Date().getTime()
    }
    const requestSize = Object.keys(JSON.stringify(requestObj)).length; // 请求数据大小
    const limitSize = 5 * 1024 * 1024; // 限制存放数据5M
    if (requestSize >= limitSize) {
      console.warn(`[${config.url}]: ` + '请求数据大小超出允许的5M限制，无法进行防重复提交验证。')
      return config;
    }
    const sessionObj = cache.session.getJSON('sessionObj')
    if (sessionObj === undefined || sessionObj === null || sessionObj === '') {
      cache.session.setJSON('sessionObj', requestObj)
    } else {
      const s_url = sessionObj.url;                // 请求地址
      const s_data = sessionObj.data;              // 请求数据
      const s_time = sessionObj.time;              // 请求时间
      const interval = 1000;                       // 间隔时间(ms)，小于此时间视为重复提交
      if (s_data === requestObj.data && requestObj.time - s_time < interval && s_url === requestObj.url) {
        const message = '数据正在处理，请勿重复提交';
        console.warn(`[${s_url}]: ` + message)
        return Promise.reject(new Error(message))
      } else {
        cache.session.setJSON('sessionObj', requestObj)
      }
    }
  }
  return config
}, error => {
    console.log(error)
    Promise.reject(error)
})

// 响应拦截器
service.interceptors.response.use(res => {
    // 未设置状态码则默认成功状态
    const code = res.data.code || 200;
    // 获取错误信息
    const msg = normalizeErrorMessage(errorCode[code] || res.data.msg || res.data, errorCode['default'])
    // 二进制数据则直接返回
    if (res.request.responseType ===  'blob' || res.request.responseType ===  'arraybuffer') {
      return res.data
    }
    if (code === 401) {
      if (!isRelogin.show) {
        isRelogin.show = true;
        ElMessageBox.confirm('登录状态已过期，您可以继续留在该页面，或者重新登录', '系统提示', { confirmButtonText: '重新登录', cancelButtonText: '取消', type: 'warning' }).then(() => {
          isRelogin.show = false;
          useUserStore().logOut().then(() => {
            location.href = '/#/index';
          })
      }).catch(() => {
        isRelogin.show = false;
      });
    }
      return Promise.reject('无效的会话，或者会话已过期，请重新登录。')
    } else if (code === 500) {
      if (shouldUseGlobalMessage(res.config)) {
        ElMessage({ message: msg, type: 'error' })
      }
      return Promise.reject(new Error(msg))
    } else if (code === 601) {
      if (shouldUseGlobalMessage(res.config)) {
        ElMessage({ message: msg, type: 'warning' })
      }
      return Promise.reject(new Error(msg))
    } else if (code !== 200) {
      if (shouldUseGlobalNotification(res.config)) {
        ElNotification.error({ title: msg })
      }
      return Promise.reject('error')
    } else {
      return  Promise.resolve(res.data)
    }
  },
  error => {
    console.log('err' + error)
    let message = normalizeErrorMessage(error, errorCode['default']);
    if (message == "Network Error") {
      message = "后端接口连接异常";
    } else if (message.includes("timeout")) {
      message = "系统接口请求超时";
    } else if (message.includes("Request failed with status code")) {
      if (!error.response){
        message = "系统接口" + message.substr(message.length - 3) + "异常";
      } else if (error.response.status == 422) {
          message = normalizeErrorMessage(error.response.data, '请求参数校验失败');
      } else {
          message = "系统接口" + error.response.status + "异常";}

    }
    if (shouldUseGlobalMessage(error.config)) {
      ElMessage({ message: message, type: 'error', duration: 5 * 1000 })
    }
    return Promise.reject(error)
  }
)

// 通用下载方法
export function download(url, params, filename, config) {
  downloadLoadingInstance = ElLoading.service({ text: "正在下载数据，请稍候", background: "rgba(0, 0, 0, 0.7)", })
  return service.post(url, params, {
    transformRequest: [(params) => { return tansParams(params) }],
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    responseType: 'blob',
    ...config
  }).then(async (data) => {
    const isBlob = blobValidate(data);
    if (isBlob) {
      const blob = new Blob([data])
      saveAs(blob, filename)
    } else {
      const resText = await data.text();
      const rspObj = JSON.parse(resText);
      const errMsg = errorCode[rspObj.code] || rspObj.msg || errorCode['default']
      ElMessage.error(errMsg);
    }
    downloadLoadingInstance.close();
  }).catch((r) => {
    console.error(r)
    ElMessage.error('下载文件出现错误，请联系管理员！')
    downloadLoadingInstance.close();
  })
}

export default service
