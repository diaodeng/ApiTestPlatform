const TICKET_AI_PREFERENCE_KEY = 'ticket.ai.analysis.preference'

function normalizeText(value) {
  return String(value || '').trim()
}

function normalizePromptCodes(value) {
  if (Array.isArray(value)) {
    return value.map(item => normalizeText(item)).filter(Boolean)
  }
  if (typeof value === 'string') {
    return value.split(',').map(item => item.trim()).filter(Boolean)
  }
  return []
}

function readStoredPreference() {
  try {
    const raw = window.localStorage?.getItem(TICKET_AI_PREFERENCE_KEY)
    return raw ? JSON.parse(raw) || {} : {}
  } catch (error) {
    console.warn('读取工单AI偏好失败', error)
    return {}
  }
}

function writeStoredPreference(preference) {
  try {
    window.localStorage?.setItem(TICKET_AI_PREFERENCE_KEY, JSON.stringify(preference || {}))
  } catch (error) {
    console.warn('保存工单AI偏好失败', error)
  }
}

function hasOwn(source, key) {
  return Object.prototype.hasOwnProperty.call(source || {}, key)
}

function getTicketAutomationLogPullConfig(ticketData = {}) {
  const extraData = ticketData.extraData || ticketData.extra_data || {}
  const automation = extraData.ticketAutomation || extraData.ticket_automation || {}
  return automation.logPullConfig || automation.log_pull_config || {}
}

function resolveConfigPromptCodes(config) {
  return normalizePromptCodes(
    config.promptTemplateCodes ||
      config.prompt_template_codes ||
      config.aiPromptTemplateCodes ||
      config.ai_prompt_template_codes
  )
}

function resolveLatestPromptCodes(detail) {
  return normalizePromptCodes(detail?.latestAiAnalysis?.analysisContext?.selectedPromptTemplateCodes)
}

export function buildTicketAiPreferenceDefaults(detail, fallbackPromptTemplateCodes = []) {
  const preference = readStoredPreference()
  const config = getTicketAutomationLogPullConfig(detail || {})
  const latestAnalysis = detail?.latestAiAnalysis || {}
  const latestContext = latestAnalysis.analysisContext || {}
  const configPromptCodes = resolveConfigPromptCodes(config)
  const latestPromptCodes = resolveLatestPromptCodes(detail)

  const hasManualAgentCode = hasOwn(preference, 'agentCode')
  const hasManualProviderCode = hasOwn(preference, 'aiProviderCode')
  const hasManualPromptTemplateCodes = hasOwn(preference, 'promptTemplateCodes')

  return {
    agentCode: hasManualAgentCode
      ? normalizeText(preference.agentCode)
      : normalizeText(
        config.aiAgentCode ||
          config.ai_agent_code ||
          latestAnalysis.agentCode ||
          latestContext.selectedAgentCode
      ),
    aiProviderCode: hasManualProviderCode
      ? normalizeText(preference.aiProviderCode)
      : normalizeText(
        config.aiProviderCode ||
          config.ai_provider_code ||
          latestAnalysis.aiProviderCode ||
          latestContext.selectedAiProviderCode
      ),
    promptTemplateCodes: hasManualPromptTemplateCodes
      ? normalizePromptCodes(preference.promptTemplateCodes)
      : (
        configPromptCodes.length
          ? configPromptCodes
          : latestPromptCodes.length
            ? latestPromptCodes
            : normalizePromptCodes(fallbackPromptTemplateCodes)
      ),
    hasManualAgentCode,
    hasManualProviderCode,
    hasManualPromptTemplateCodes
  }
}

export function saveTicketAiPreferencePatch(patch = {}) {
  const preference = {
    ...readStoredPreference(),
    ...patch,
    updateTime: new Date().toISOString()
  }
  if (hasOwn(preference, 'agentCode')) {
    preference.agentCode = normalizeText(preference.agentCode)
  }
  if (hasOwn(preference, 'aiProviderCode')) {
    preference.aiProviderCode = normalizeText(preference.aiProviderCode)
  }
  if (hasOwn(preference, 'promptTemplateCodes')) {
    preference.promptTemplateCodes = normalizePromptCodes(preference.promptTemplateCodes)
  }
  writeStoredPreference(preference)
}
