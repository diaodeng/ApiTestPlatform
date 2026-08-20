import { ref } from 'vue'
import { listAiProviderModelOptions } from '@/api/system/aiprovider'

/**
 * 管理工单页面按 Provider 加载模型下拉选项。
 * @returns {{ modelOptions: import('vue').Ref<Array>, loadModelOptions: Function }} 模型选项和加载方法。
 */
export function useAiProviderModelOptions() {
  const modelOptions = ref([])
  let requestVersion = 0

  /**
   * 加载指定 Provider 的启用模型，并忽略已经过期的响应。
   * @param {string} providerCode Provider 编码。
   * @returns {Promise<Array>} 当前请求返回的模型列表。
   */
  function loadModelOptions(providerCode) {
    const normalizedProviderCode = String(providerCode || '').trim()
    const version = ++requestVersion
    modelOptions.value = []
    if (!normalizedProviderCode) {
      return Promise.resolve([])
    }

    return listAiProviderModelOptions(normalizedProviderCode)
      .then((response) => {
        if (version !== requestVersion) return []
        const rows = Array.isArray(response.data) ? response.data : []
        modelOptions.value = rows
        return rows
      })
      .catch(() => {
        if (version === requestVersion) modelOptions.value = []
        return []
      })
  }

  function clearModelOptions() {
    requestVersion += 1
    modelOptions.value = []
  }

  return { modelOptions, loadModelOptions, clearModelOptions }
}
