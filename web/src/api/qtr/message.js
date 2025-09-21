import request from '@/utils/request'

// 查询消息推送配置调度列表
export function listMessage(query) {
    return request({
        url: '/qtr/message/list',
        method: 'get',
        params: query
    });
}

// 查询消息推送配置调度详细
export function getMessage(jobId) {
    return request({
        url: '/qtr/message/' + jobId,
        method: 'get'
    })
}

// 新增消息推送配置调度
export function addMessage(data) {
    return request({
        url: '/qtr/message',
        method: 'post',
        data: data
    })
}

// 修改消息推送配置调度
export function updateMessage(data) {
    return request({
        url: '/qtr/message',
        method: 'put',
        data: data
    })
}

// 删除消息推送配置调度
export function delMessage(data) {
    return request({
        url: '/qtr/message',
        method: 'delete',
        data: data
    })
}

// 任务状态修改
export function changeMessageStatus(jobId, status) {
    const data = {
        jobId,
        status
    }
    return request({
        url: '/qtr/message/changeStatus',
        method: 'put',
        data: data
    })
}


// 消息推送配置导出
export function exportMessage(data) {
    return request({
        url: '/qtr/message/export',
        method: 'post',
        data: data
    })
}