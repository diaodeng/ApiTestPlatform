import { ref, reactive } from 'vue';
import {
  getTicketLogPullStorageConfig,
  saveTicketLogPullStorageConfig,
} from '@/api/ticket/logPull';

/**
 * 日志拉取存储与资源限制配置管理 composable。
 * 承载「日志拉取配置」tab 下的存储方式、目录、FTP 以及轮询/下载/入库/搜索资源护栏。
 * 独立于 useSyncConfig.js（工单同步配置）与 useLogPullExternalConfig.js（外部接口分组）。
 *
 * @param {Object} proxy - 当前组件实例代理，用于 $modal 消息提示
 */
export function useLogPullStorageConfig(proxy) {
  const loading = ref(false);
  const saving = ref(false);

  /** 版本提取正则编辑文本（JSON 数组格式，与后端 versionExtractPatterns 对齐）。 */
  const versionExtractPatternsText = ref('[]');

  /** 存储与资源限制配置表单，字段与后端 TicketLogPullStorageConfigModel 对齐（camelCase）。 */
  const storage = reactive(createDefaultStorage());

  /**
   * 构建默认存储配置，字段缺失时前端也能正常渲染。
   * @returns {object} 默认存储配置对象
   */
  function createDefaultStorage() {
    return {
      mode: 'local',
      localDirectory: '',
      ftp: {
        host: '',
        port: 21,
        username: '',
        password: '',
        baseDir: '',
        passive: true,
        timeoutSec: 15,
        encoding: 'utf-8',
      },
      effectiveLocalDirectory: '',
      maxWorkers: 2,
      pollIntervalSec: 20,
      pollTimeoutSec: 1800,
      downloadTimeoutSec: 300,
      maxContentChars: 500000,
      maxExtractSeconds: 300,
      maxExtractFileCount: 2000,
      maxExtractTotalBytes: 2147483648,
      maxSearchSeconds: 30,
      maxSearchFileCount: 1000,
      maxPythonSearchBytes: 268435456,
      maxConcurrentSearches: 2,
      maxSearchLineBytes: 524288,
      postDownloadExtractEnabled: false,
      postDownloadVersionExtractEnabled: false,
      postDownloadIndexEnabled: false,
    };
  }

  /**
   * 将后端返回的存储配置应用到本地表单，只映射后端明确存在的字段，缺失项保留默认值。
   * @param {object} payload 后端返回的存储配置
   * @returns {void}
   */
  function applyStorageConfig(payload = {}) {
    const config = payload || {};
    const ftp = config.ftp || {};
    storage.mode = ['local', 'ftp', 'oss'].includes(String(config.mode || '').trim().toLowerCase())
      ? String(config.mode).trim().toLowerCase()
      : 'local';
    storage.localDirectory = String(config.localDirectory || '').trim();
    storage.ftp = {
      host: String(ftp.host || '').trim(),
      port: Number(ftp.port || 21),
      username: String(ftp.username || '').trim(),
      password: String(ftp.password || ''),
      baseDir: String(ftp.baseDir || '').trim(),
      passive: Boolean(ftp.passive),
      timeoutSec: Number(ftp.timeoutSec || 15),
      encoding: String(ftp.encoding || 'utf-8').trim() || 'utf-8',
    };
    storage.effectiveLocalDirectory = String(config.effectiveLocalDirectory || '');
    storage.maxWorkers = Number(config.maxWorkers || 2);
    storage.pollIntervalSec = Number(config.pollIntervalSec || 20);
    storage.pollTimeoutSec = Number(config.pollTimeoutSec || 1800);
    storage.downloadTimeoutSec = Number(config.downloadTimeoutSec || 300);
    storage.maxContentChars = Number(config.maxContentChars || 500000);
    storage.maxExtractSeconds = Number(config.maxExtractSeconds || 300);
    storage.maxExtractFileCount = Number(config.maxExtractFileCount || 2000);
    storage.maxExtractTotalBytes = Number(config.maxExtractTotalBytes || 2147483648);
    storage.maxSearchSeconds = Number(config.maxSearchSeconds || 30);
    storage.maxSearchFileCount = Number(config.maxSearchFileCount || 1000);
    storage.maxPythonSearchBytes = Number(config.maxPythonSearchBytes || 268435456);
    storage.maxConcurrentSearches = Number(config.maxConcurrentSearches || 2);
    storage.maxSearchLineBytes = Number(config.maxSearchLineBytes || 524288);
    storage.postDownloadExtractEnabled = Boolean(config.postDownloadExtractEnabled);
    storage.postDownloadVersionExtractEnabled = Boolean(config.postDownloadVersionExtractEnabled);
    storage.postDownloadIndexEnabled = Boolean(config.postDownloadIndexEnabled);
    versionExtractPatternsText.value = JSON.stringify(normalizePatternArray(config.versionExtractPatterns), null, 2);
  }

  /**
   * 归一化正则数组：过滤空串并保留原始顺序，后端负责合法性与去重校验。
   * @param {any} raw 后端返回的正则配置
   * @returns {string[]} 正则字符串数组
   */
  function normalizePatternArray(raw) {
    if (!Array.isArray(raw)) {
      return [];
    }
    return raw.map(item => String(item || '').trim()).filter(Boolean);
  }

  /**
   * 解析版本提取正则编辑文本为 JSON 数组，解析失败时抛出错误并返回 null。
   * @returns {string[]|null} 正则数组；格式非法时返回 null
   */
  function parseVersionExtractPatterns() {
    const rawText = String(versionExtractPatternsText.value || '').trim();
    if (!rawText) {
      return [];
    }
    try {
      const parsed = JSON.parse(rawText);
      if (!Array.isArray(parsed)) {
        proxy?.$modal?.msgError?.('版本提取正则必须是 JSON 数组，例如 ["正则1", "正则2"]');
        return null;
      }
      return parsed.map(item => String(item || '').trim()).filter(Boolean);
    } catch (err) {
      proxy?.$modal?.msgError?.('版本提取正则不是合法的 JSON 数组: ' + (err?.message || err));
      return null;
    }
  }

  /**
   * 构建保存载荷，仅提交后端可写入的字段（排除 effectiveLocalDirectory 等派生字段）。
   * @returns {object|null} 存储配置保存载荷；正则格式非法时返回 null
   */
  function buildSavePayload() {
    const versionExtractPatterns = parseVersionExtractPatterns();
    if (versionExtractPatterns === null) {
      return null;
    }
    return {
      mode: storage.mode,
      localDirectory: storage.localDirectory,
      ftp: {
        host: storage.ftp.host,
        port: Number(storage.ftp.port || 21),
        username: storage.ftp.username,
        password: storage.ftp.password,
        baseDir: storage.ftp.baseDir,
        passive: Boolean(storage.ftp.passive),
        timeoutSec: Number(storage.ftp.timeoutSec || 15),
        encoding: String(storage.ftp.encoding || 'utf-8'),
      },
      maxWorkers: Number(storage.maxWorkers || 2),
      pollIntervalSec: Number(storage.pollIntervalSec || 20),
      pollTimeoutSec: Number(storage.pollTimeoutSec || 1800),
      downloadTimeoutSec: Number(storage.downloadTimeoutSec || 300),
      maxContentChars: Number(storage.maxContentChars || 500000),
      maxExtractSeconds: Number(storage.maxExtractSeconds || 300),
      maxExtractFileCount: Number(storage.maxExtractFileCount || 2000),
      maxExtractTotalBytes: Number(storage.maxExtractTotalBytes || 2147483648),
      maxSearchSeconds: Number(storage.maxSearchSeconds || 30),
      maxSearchFileCount: Number(storage.maxSearchFileCount || 1000),
      maxPythonSearchBytes: Number(storage.maxPythonSearchBytes || 268435456),
      maxConcurrentSearches: Number(storage.maxConcurrentSearches || 2),
      maxSearchLineBytes: Number(storage.maxSearchLineBytes || 524288),
      postDownloadExtractEnabled: Boolean(storage.postDownloadExtractEnabled),
      postDownloadVersionExtractEnabled: Boolean(storage.postDownloadVersionExtractEnabled),
      postDownloadIndexEnabled: Boolean(storage.postDownloadIndexEnabled),
      versionExtractPatterns,
    };
  }

  /**
   * 加载日志拉取存储与资源限制配置。
   * @returns {Promise<void>}
   */
  function loadConfig() {
    loading.value = true;
    return getTicketLogPullStorageConfig()
      .then(res => {
        applyStorageConfig(res?.data || {});
      })
      .catch(err => {
        console.error('加载日志拉取存储配置失败:', err);
        proxy?.$modal?.msgError?.('加载日志拉取存储配置失败: ' + (err?.msg || err?.message || '未知错误'));
      })
      .finally(() => {
        loading.value = false;
      });
  }

  /**
   * 保存日志拉取存储与资源限制配置。
   * @returns {Promise<void>}
   */
  function handleSave() {
    const payload = buildSavePayload();
    if (!payload) {
      return Promise.reject(new Error('版本提取正则格式非法'));
    }
    saving.value = true;
    return saveTicketLogPullStorageConfig(payload)
      .then(() => {
        proxy?.$modal?.msgSuccess?.('日志拉取存储与资源限制配置已保存');
      })
      .catch(err => {
        proxy?.$modal?.msgError?.('保存失败: ' + (err?.msg || err?.message || '未知错误'));
        return Promise.reject(err);
      })
      .finally(() => {
        saving.value = false;
      });
  }

  return {
    loading,
    saving,
    storage,
    versionExtractPatternsText,
    loadConfig,
    handleSave,
  };
}
