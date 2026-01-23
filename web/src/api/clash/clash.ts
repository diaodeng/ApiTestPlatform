import request from '@/utils/request'

export function listClashServices() {
  return request.get('/clash-admin/clash-services')
}

export function bindSubscription(serviceId: string, subId: string) {
  return request.post(
    `/clash-admin/clash-services/${serviceId}/bind-subscription`,
    { sub_id: subId }
  )
}
