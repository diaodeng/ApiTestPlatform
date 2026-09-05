import request from '@/utils/request'

// 资源采集服务管理 API：推送地址、启停状态、推送间隔等可视化配置
export const listMetricsCollectors = () => request({ url: '/monitor/metrics-collectors', method: 'get' })
export const addMetricsCollector = (data) => request({ url: '/monitor/metrics-collectors', method: 'post', data })
export const updateMetricsCollector = (id, data) => request({ url: `/monitor/metrics-collectors/${id}`, method: 'put', data })
export const changeMetricsCollectorStatus = (id, data) => request({ url: `/monitor/metrics-collectors/${id}/status`, method: 'put', data })
export const delMetricsCollector = (id) => request({ url: `/monitor/metrics-collectors/${id}`, method: 'delete' })
export const getMetricsCollectorRuntime = () => request({ url: '/monitor/metrics-collectors/runtime', method: 'get' })
