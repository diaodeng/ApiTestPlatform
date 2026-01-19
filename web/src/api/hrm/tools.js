import request from '@/utils/request'

// 查询所有agent
export function parseJson(data) {
  return request({
    url: '/hrm/tools/jsonParse',
    method: 'post',
    data: data
  })
}
