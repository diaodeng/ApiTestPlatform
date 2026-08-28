/**
 * 工单日志准备下载进度 composable。
 *
 * 仅在后端确认进入准备或远程下载阶段后暴露进度数据，调用方可据此把查看日志按钮替换为圆形进度条。
 */
import { ref } from 'vue';
import { getTicketLogPrepareProgress } from '@/api/ticket/ticket';

const downloadProgressByRecord = ref({});
const requestByRecord = new Map();
const requestRecordByKey = new Map();
const observedRecordByKey = new Map();
const progressRequestByRecord = new Map();
const timerByRecord = new Map();

/**
 * 管理工单日志准备请求及其远程下载进度。
 * @returns {object} 日志准备请求包装器和按记录查询的下载进度。
 */
export function useLogPrepareProgress() {
  /**
   * 包装日志准备请求，并复用已有准备请求或后端正在执行的任务。
   * @param {number|string} ticketId 工单ID。
   * @param {number|string} recordId 日志拉取记录ID。
   * @param {Function} prepareRequest 发起日志准备的请求函数。
   * @returns {Promise<object>} 日志准备接口响应。
   */
  function prepareWithDownloadProgress(ticketId, recordId, prepareRequest) {
    const key = buildRecordKey(ticketId, recordId);
    if (requestByRecord.has(key)) {
      return requestByRecord.get(key);
    }
    const requestPromise = requestProgressSnapshot(ticketId, recordId)
      .catch(() => null)
      .then((response) => {
        const progress = updateProgress(ticketId, recordId, response?.data || {});
        if (isPreparing(progress)) {
          observedRecordByKey.set(key, { ticketId, recordId });
          return waitForPrepareCompletion(ticketId, recordId);
        }
        const preparePromise = prepareRequest();
        schedulePolling(ticketId, recordId);
        return preparePromise;
      })
      .finally(() => {
        requestByRecord.delete(key);
        requestRecordByKey.delete(key);
        removeDownloadProgress(key);
        observedRecordByKey.delete(key);
      });
    requestByRecord.set(key, requestPromise);
    requestRecordByKey.set(key, { ticketId, recordId });
    return requestPromise;
  }

  /**
   * 获取指定列表行当前可展示的下载进度。
   * @param {number|string} ticketId 工单ID。
   * @param {number|string} recordId 日志拉取记录ID。
   * @returns {object|null} 正在下载时返回进度数据，否则返回 null。
   */
  function getDownloadProgress(ticketId, recordId) {
    return downloadProgressByRecord.value[buildRecordKey(ticketId, recordId)] || null;
  }

  /**
   * 在列表重新加载时恢复指定日志记录的后端进度观察。
   * @param {number|string} ticketId 工单ID。
   * @param {number|string} recordId 日志拉取记录ID。
   * @returns {void} 无返回值。
   */
  function observeDownloadProgress(ticketId, recordId) {
    const key = buildRecordKey(ticketId, recordId);
    if (!ticketId || !recordId) return;
    observedRecordByKey.set(key, { ticketId, recordId });
    if (requestByRecord.has(key)) return;
    schedulePolling(ticketId, recordId);
  }

  /**
   * 轮询指定日志记录的后端准备进度。
   * @param {number|string} ticketId 工单ID。
   * @param {number|string} recordId 日志拉取记录ID。
   * @returns {void} 无返回值。
   */
  function pollProgress(ticketId, recordId) {
    const key = buildRecordKey(ticketId, recordId);
    timerByRecord.delete(key);
    requestProgressSnapshot(ticketId, recordId)
      .then((response) => {
        const progress = updateProgress(ticketId, recordId, response?.data || {});
        if (!isPreparing(progress) && !requestByRecord.has(key)) {
          observedRecordByKey.delete(key);
        }
      })
      .catch(() => {
        if (!requestByRecord.has(key)) {
          observedRecordByKey.delete(key);
          removeDownloadProgress(key);
        }
      })
      .finally(() => {
        schedulePollingIfObserved(key);
      });
  }

  /**
   * 复用同一记录正在执行的进度查询，避免弹窗、列表和等待器并发请求同一接口。
   * @param {number|string} ticketId 工单ID。
   * @param {number|string} recordId 日志拉取记录ID。
   * @returns {Promise<object>} 后端进度接口响应。
   */
  function requestProgressSnapshot(ticketId, recordId) {
    const key = buildRecordKey(ticketId, recordId);
    if (progressRequestByRecord.has(key)) {
      return progressRequestByRecord.get(key);
    }
    const requestPromise = getTicketLogPrepareProgress(ticketId, recordId).finally(() => {
      progressRequestByRecord.delete(key);
    });
    progressRequestByRecord.set(key, requestPromise);
    return requestPromise;
  }

  /**
   * 安排下一次进度查询，避免同一条记录并发发起多个查询。
   * @param {number|string} ticketId 工单ID。
   * @param {number|string} recordId 日志拉取记录ID。
   * @returns {void} 无返回值。
   */
  function schedulePolling(ticketId, recordId) {
    const key = buildRecordKey(ticketId, recordId);
    if (timerByRecord.has(key)) return;
    timerByRecord.set(key, window.setTimeout(() => pollProgress(ticketId, recordId), 400));
  }

  /**
   * 根据请求或列表观察状态继续安排进度查询。
   * @param {string} key 工单和日志记录组成的进度键。
   * @returns {void} 无返回值。
   */
  function schedulePollingIfObserved(key) {
    const observed = observedRecordByKey.get(key);
    if (!observed && !requestByRecord.has(key)) return;
    const record = observed || requestRecordByKey.get(key);
    if (!record || timerByRecord.has(key)) return;
    schedulePolling(record.ticketId, record.recordId);
  }

  /**
   * 将后端进度快照同步到共享响应式状态。
   * @param {number|string} ticketId 工单ID。
   * @param {number|string} recordId 日志拉取记录ID。
   * @param {object} progress 后端进度快照。
   * @returns {object} 归一化后的进度快照。
   */
  function updateProgress(ticketId, recordId, progress = {}) {
    const key = buildRecordKey(ticketId, recordId);
    const normalizedProgress = {
      stage: progress.stage || 'idle',
      downloading: Boolean(progress.downloading),
      percentage: Number(progress.percentage || 0),
      message: progress.message || '正在准备日志',
    };
    if (normalizedProgress.downloading || normalizedProgress.stage === 'preparing') {
      downloadProgressByRecord.value = {
        ...downloadProgressByRecord.value,
        [key]: normalizedProgress,
      };
    } else {
      removeDownloadProgress(key);
    }
    return normalizedProgress;
  }

  /**
   * 判断后端准备任务是否仍可能在执行。
   * @param {object} progress 后端进度快照。
   * @returns {boolean} 仍在准备或下载时返回 true。
   */
  function isPreparing(progress = {}) {
    return Boolean(progress.downloading) || progress.stage === 'preparing';
  }

  /**
   * 等待浏览器之外已存在的日志准备任务完成。
   * @param {number|string} ticketId 工单ID。
   * @param {number|string} recordId 日志拉取记录ID。
   * @returns {Promise<object>} 与准备接口兼容的完成结果。
   */
  function waitForPrepareCompletion(ticketId, recordId) {
    return new Promise((resolve, reject) => {
      const poll = () => {
        requestProgressSnapshot(ticketId, recordId)
          .then((response) => {
            const progress = updateProgress(ticketId, recordId, response?.data || {});
            if (isPreparing(progress)) {
              window.setTimeout(poll, 400);
              return;
            }
            if (progress.stage === 'failed') {
              reject(new Error(progress.message || '日志准备失败'));
              return;
            }
            resolve({ data: { prepared: true, message: progress.message || '' } });
          })
          .catch(() => window.setTimeout(poll, 1000));
      };
      poll();
    });
  }

  /**
   * 从响应式进度集合中移除已结束的记录。
   * @param {string} key 工单和日志记录组成的进度键。
   * @returns {void} 无返回值。
   */
  function removeDownloadProgress(key) {
    if (!downloadProgressByRecord.value[key]) return;
    const nextProgress = { ...downloadProgressByRecord.value };
    delete nextProgress[key];
    downloadProgressByRecord.value = nextProgress;
  }

  /**
   * 构造工单与日志记录的稳定进度键。
   * @param {number|string} ticketId 工单ID。
   * @param {number|string} recordId 日志拉取记录ID。
   * @returns {string} 可用于映射表的组合键。
   */
  function buildRecordKey(ticketId, recordId) {
    return `${ticketId || 0}:${recordId || 0}`;
  }

  return {
    prepareWithDownloadProgress,
    getDownloadProgress,
    observeDownloadProgress,
  };
}
