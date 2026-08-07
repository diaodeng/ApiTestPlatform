import request from '@/utils/request';

/** 查询项目版本中心 */
export function listTicketVersions(query) {
  return request({ url: '/ticket/versions/list', method: 'get', params: query });
}

/** 查询项目版本下拉选项 */
export function listTicketVersionOptions(projectId, includeDiscovered = true) {
  return request({
    url: '/ticket/versions/options',
    method: 'get',
    params: { projectId, includeDiscovered },
  });
}

/** 新增项目版本 */
export function addTicketVersion(data) {
  return request({ url: '/ticket/versions', method: 'post', data });
}

/** 更新项目版本 */
export function updateTicketVersion(data) {
  return request({ url: '/ticket/versions', method: 'put', data });
}

/** 查询版本发布历史 */
export function listTicketVersionReleases(versionId) {
  return request({ url: `/ticket/versions/${versionId}/releases`, method: 'get' });
}

/** 新增版本发布记录 */
export function addTicketVersionRelease(data) {
  return request({ url: '/ticket/version-releases', method: 'post', data });
}

/** 更新版本发布记录 */
export function updateTicketVersionRelease(data) {
  return request({ url: '/ticket/version-releases', method: 'put', data });
}
