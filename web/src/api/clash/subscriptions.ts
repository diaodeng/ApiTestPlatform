import request from '@/utils/request'

export function listSubscriptions() {
  return request.get('/clash-admin/subscriptions')
}

export function createSubscription(data: any) {
  return request.post('/clash-admin/subscriptions', data)
}

export function deleteSubscription(id: string) {
  return request.delete(`/clash-admin/subscriptions/${id}`)
}
