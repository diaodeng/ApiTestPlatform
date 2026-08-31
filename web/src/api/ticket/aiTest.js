import request from '@/utils/request';

// 获取轻量AI测试工作台选项（任务类型、Provider、模型目录、提示词模板）
export function getTicketAiTestOptions() {
  return request({
    url: '/ticket/ai-test/options',
    method: 'get',
  });
}

// 按工单号或标题关键字搜索工单
export function searchTicketAiTestTickets(keyword) {
  return request({
    url: '/ticket/ai-test/tickets',
    method: 'get',
    params: { keyword },
  });
}

// 获取工单测试上下文（标题、描述、原始入参、当前字段）
export function getTicketAiTestContext(ticketNo) {
  return request({
    url: '/ticket/ai-test/context',
    method: 'get',
    params: { ticketNo },
  });
}

// 按模板编码获取提示词内容（供选择模板后回填编辑区）
export function getTicketAiTestPromptContent(templateCode) {
  return request({
    url: '/ticket/ai-test/prompt-content',
    method: 'get',
    params: { templateCode },
  });
}

// 执行一次轻量AI测试
export function runTicketAiTest(data) {
  return request({
    url: '/ticket/ai-test/run',
    method: 'post',
    data,
    timeout: 120000,
  });
}
