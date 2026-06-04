function hasText(value) {
  return String(value ?? '').trim() !== ''
}

function parseDateTime(value) {
  return hasText(value) ? new Date(value) : null
}

export function getOptionalLogPullTimeRangeError(form) {
  const hasBegin = hasText(form?.logBeginTime)
  const hasEnd = hasText(form?.logEndTime)
  const hasPoint = hasText(form?.logPointTime)

  if (hasBegin || hasEnd) {
    if (!hasBegin || !hasEnd) {
      return '开始时间和结束时间需要同时填写'
    }
    const begin = parseDateTime(form.logBeginTime)
    const end = parseDateTime(form.logEndTime)
    if (begin && end && begin > end) {
      return '开始时间不能晚于结束时间'
    }
    return ''
  }

  if (hasPoint) {
    const beforeMinutes = Number(form?.rangeBeforeMinutes ?? 0)
    const afterMinutes = Number(form?.rangeAfterMinutes ?? 0)
    if (beforeMinutes < 0 || afterMinutes < 0) {
      return '时间点前后范围不能为负数'
    }
    if (!beforeMinutes && !afterMinutes) {
      return '时间点前后范围至少需要一侧大于 0'
    }
  }

  return ''
}

export function buildOptionalLogPullTimeRangePayload(form) {
  const payload = {}
  const hasBegin = hasText(form?.logBeginTime)
  const hasEnd = hasText(form?.logEndTime)
  const hasPoint = hasText(form?.logPointTime)

  if (hasBegin || hasEnd) {
    payload.timeRangeMode = 'between'
    payload.logBeginTime = form.logBeginTime
    payload.logEndTime = form.logEndTime
    return payload
  }

  if (hasPoint) {
    payload.timeRangeMode = 'point'
    payload.logPointTime = form.logPointTime
    payload.rangeBeforeMinutes = Number(form.rangeBeforeMinutes ?? 0)
    payload.rangeAfterMinutes = Number(form.rangeAfterMinutes ?? 0)
  }

  return payload
}
