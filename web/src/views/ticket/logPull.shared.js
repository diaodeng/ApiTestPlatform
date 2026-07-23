function hasText(value) {
  return String(value ?? '').trim() !== '';
}

function parseDateTime(value) {
  return hasText(value) ? new Date(value) : null;
}

export function createDefaultLogPullNotifyConfig() {
  return {
    allowPush: 0,
    pushIds: [],
    success: {
      push: true,
      reminder: 1,
    },
    failed: {
      push: true,
      reminder: 1,
    },
  };
}

/**
 * 创建日志拉取表单默认值，供新增/编辑工单和详情发起日志拉取复用。
 * @returns {object} 日志拉取表单默认值
 */
export function createDefaultLogPullForm() {
  return {
    environment: '',
    vendorId: undefined,
    storeId: undefined,
    posNo: undefined,
    commandDataType: 1,
    pullMethod: 'time',
    modifyTime: undefined,
    path: '',
    cutLogEnabled: false,
    timeRangeMode: 'between',
    fileMaxSize: 500,
    zipMaxSize: 500,
    logBeginTime: undefined,
    logEndTime: undefined,
    logPointTime: undefined,
    rangeBeforeMinutes: 30,
    rangeAfterMinutes: 30,
    storageMode: 'local',
    autoAiEnabled: false,
    aiAgentCode: '',
    aiProviderCode: '',
    notifyConfig: createDefaultLogPullNotifyConfig(),
  };
}

export function normalizeLogPullNotifyConfig(config) {
  const source = config || {};
  const allowPush = source.allowPush ?? source.allow_push ?? 0;
  const enabled = allowPush === 1 || allowPush === '1' || allowPush === true;
  if (!enabled) {
    return createDefaultLogPullNotifyConfig();
  }
  return {
    allowPush: 1,
    pushIds: Array.isArray(source.pushIds || source.push_ids)
      ? source.pushIds || source.push_ids
      : [],
    success: {
      push: source.success?.push !== false,
      reminder: source.success?.reminder ?? 1,
    },
    failed: {
      push: source.failed?.push !== false,
      reminder: source.failed?.reminder ?? 1,
    },
  };
}

export function hasLogPullTimeRange(config) {
  return (
    hasText(config?.logBeginTime) ||
    hasText(config?.logEndTime) ||
    hasText(config?.logPointTime) ||
    config?.rangeBeforeMinutes !== undefined ||
    config?.rangeAfterMinutes !== undefined
  );
}

export function getOptionalLogPullTimeRangeError(form) {
  if (!form?.cutLogEnabled) {
    return '';
  }
  const hasBegin = hasText(form?.logBeginTime);
  const hasEnd = hasText(form?.logEndTime);
  const hasPoint = hasText(form?.logPointTime);

  if (hasBegin || hasEnd) {
    if (!hasBegin || !hasEnd) {
      return '开始时间和结束时间需要同时填写';
    }
    const begin = parseDateTime(form.logBeginTime);
    const end = parseDateTime(form.logEndTime);
    if (begin && end && begin > end) {
      return '开始时间不能晚于结束时间';
    }
    return '';
  }

  if (hasPoint) {
    const beforeMinutes = Number(form?.rangeBeforeMinutes ?? 0);
    const afterMinutes = Number(form?.rangeAfterMinutes ?? 0);
    if (beforeMinutes < 0 || afterMinutes < 0) {
      return '时间点前后范围不能为负数';
    }
    if (!beforeMinutes && !afterMinutes) {
      return '时间点前后范围至少需要一侧大于 0';
    }
  }

  return '';
}

/**
 * 构造提交给后端的日志拉取配置，移除当前模式不需要的字段。
 * @param {object} source 表单中的日志拉取配置
 * @returns {object} 清洗后的日志拉取配置
 */
export function buildCleanLogPullConfig(source) {
  const config = { ...(source || {}) };
  config.notifyConfig = normalizeLogPullNotifyConfig(config.notifyConfig);
  if (config.pullMethod === 'path') {
    delete config.modifyTime;
  } else {
    delete config.path;
  }
  if (!config.cutLogEnabled) {
    delete config.timeRangeMode;
    delete config.logBeginTime;
    delete config.logEndTime;
    delete config.logPointTime;
    delete config.rangeBeforeMinutes;
    delete config.rangeAfterMinutes;
  } else if (config.timeRangeMode === 'between') {
    delete config.logPointTime;
    delete config.rangeBeforeMinutes;
    delete config.rangeAfterMinutes;
  } else if (config.timeRangeMode === 'point') {
    delete config.logBeginTime;
    delete config.logEndTime;
  }
  delete config.cutLogEnabled;
  if (!config.autoAiEnabled) {
    config.aiAgentCode = '';
    config.aiProviderCode = '';
  }
  return config;
}

export function buildOptionalLogPullTimeRangePayload(form) {
  const payload = {};
  if (!form?.cutLogEnabled) {
    return payload;
  }
  const hasBegin = hasText(form?.logBeginTime);
  const hasEnd = hasText(form?.logEndTime);
  const hasPoint = hasText(form?.logPointTime);

  if (hasBegin || hasEnd) {
    payload.timeRangeMode = 'between';
    payload.logBeginTime = form.logBeginTime;
    payload.logEndTime = form.logEndTime;
    return payload;
  }

  if (hasPoint) {
    payload.timeRangeMode = 'point';
    payload.logPointTime = form.logPointTime;
    payload.rangeBeforeMinutes = Number(form.rangeBeforeMinutes ?? 0);
    payload.rangeAfterMinutes = Number(form.rangeAfterMinutes ?? 0);
  }

  return payload;
}

export function isHttpDownloadUrl(url) {
  return /^https?:\/\//i.test(String(url || '').trim());
}

export function buildLogPullApiDownloadUrl(recordId, source = 'auto') {
  if (!recordId) {
    return '';
  }
  const baseApi = String(
    window.__APP_CONFIG__?.BASE_API || import.meta.env.VITE_APP_BASE_API || ''
  ).replace(/\/$/, '');
  const path = `/ticket/log-pulls/${recordId}/download?source=${encodeURIComponent(source)}`;
  return baseApi ? `${baseApi}${path}` : path;
}

export function formatLogPullParameter(row) {
  const pullMethod = row?.pullMethod || (Number(row?.commandDataType) === 2 ? 'path' : 'time');
  if (pullMethod === 'path') {
    const path = String(row?.path || '').trim();
    return path ? `路径：${path}` : '-';
  }
  const modifyTime = String(row?.modifyTime || '').trim();
  return modifyTime ? `时间：${modifyTime}` : '-';
}

export function resolveLogPullArchiveLink(row, source = 'service') {
  const storagePath = String(row?.storagePath || '').trim();
  if (!storagePath) {
    return { url: '', text: '', needLogin: false };
  }
  if (isHttpDownloadUrl(storagePath)) {
    return { url: storagePath, text: storagePath, needLogin: false };
  }
  return {
    url: buildLogPullApiDownloadUrl(row?.id, source),
    text: storagePath,
    needLogin: true,
  };
}

export function resolveLogPullOriginalLink(row) {
  const commandResultUrl = String(row?.commandResultUrl || '').trim();
  return { url: commandResultUrl, text: commandResultUrl, needLogin: false };
}
