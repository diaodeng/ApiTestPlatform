import request from '@/utils/request'

// 查询推送配置列表
export function listPushConfig(query) {
    return request({
        url: '/hrm/pushManager/list',
        method: 'get',
        params: query
    });
}

/*
* 查询所有推送配置
* */
export function allPushConfig(query) {
    return request({
        url: '/hrm/pushManager/all',
        method: 'get',
        params: query
    });
}

// 查询推送配置详细
export function getPushConfig(envId) {
    return request({
        url: '/hrm/pushManager/' + envId,
        method: 'get'
    });
}

// 新增推送配置
export function addPushConfig(data) {
    return request({
        url: '/hrm/pushManager',
        method: 'post',
        data: data
    });
}

// 新增推送配置
export function copyPushConfig(data) {
    return request({
        url: '/hrm/pushManager/copy',
        method: 'post',
        data: data
    });
}

// 修改推送配置
export function updatePushConfig(data) {
    return request({
        url: '/hrm/pushManager',
        method: 'put',
        data: data
    });
}

// 删除推送配置
export function delPushConfig(data) {
    return request({
        url: '/hrm/pushManager',
        method: 'delete',
        data: data
    })
}