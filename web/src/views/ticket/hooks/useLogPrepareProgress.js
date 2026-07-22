/**
 * 工单日志准备下载进度 composable。
 *
 * 仅在后端确认进入远程下载阶段后暴露进度数据，调用方可据此把查看日志按钮替换为圆形进度条。
 */
import { onBeforeUnmount, ref } from 'vue';
import { getTicketLogPrepareProgress } from '@/api/ticket/ticket';

/**
 * 管理工单日志准备请求及其远程下载进度。
 * @returns {object} 日志准备请求包装器和按记录查询的下载进度。
 */
export function useLogPrepareProgress() {
  const downloadProgressByRecord = ref({});
  const requestByRecord = new Map();
  const timerByRecord = new Map();

  /**
   * 包装日志准备请求，并在请求期间轮询后端下载进度。
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
    const requestPromise = Promise.resolve()
      .then(() => prepareRequest())
      .finally(() => {
        requestByRecord.delete(key);
        stopPolling(key);
      });
    requestByRecord.set(key, requestPromise);
    startPolling(ticketId, recordId);
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
   * 启动指定日志记录的进度轮询。
   * @param {number|string} ticketId 工单ID。
   * @param {number|string} recordId 日志拉取记录ID。
   * @returns {void} 无返回值。
   */
  function startPolling(ticketId, recordId) {
    const key = buildRecordKey(ticketId, recordId);
    if (timerByRecord.has(key)) return;
    const poll = () => {
      getTicketLogPrepareProgress(ticketId, recordId)
        .then((response) => {
          const progress = response?.data || {};
          if (progress.downloading) {
            downloadProgressByRecord.value = {
              ...downloadProgressByRecord.value,
              [key]: {
                percentage: Number(progress.percentage || 0),
                message: progress.message || '正在下载日志',
              },
            };
          } else {
            removeDownloadProgress(key);
          }
        })
        .finally(() => {
          if (requestByRecord.has(key)) {
            timerByRecord.set(key, window.setTimeout(poll, 400));
          }
        });
    };
    poll();
  }

  /**
   * 停止日志准备进度轮询并清理页面状态。
   * @param {string} key 工单和日志记录组成的进度键。
   * @returns {void} 无返回值。
   */
  function stopPolling(key) {
    const timer = timerByRecord.get(key);
    if (timer) {
      window.clearTimeout(timer);
    }
    timerByRecord.delete(key);
    removeDownloadProgress(key);
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

  onBeforeUnmount(() => {
    timerByRecord.forEach((timer) => window.clearTimeout(timer));
    timerByRecord.clear();
    requestByRecord.clear();
  });

  return {
    prepareWithDownloadProgress,
    getDownloadProgress,
  };
}
