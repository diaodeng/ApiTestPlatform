import request from '@/utils/request'
import {ElMessage} from "element-plus";

// 查询用例列表
export function listCase(query) {
  return request({
    url: '/hrm/case/list',
    method: 'get',
    params: query
  })
}


// 查询用例详细
export function getCase(caseId) {
  return request({
    url: '/hrm/case/' + caseId,
    method: 'get'
  })
}

// 新增用例
export function addCase(data) {
  return request({
    url: '/hrm/case',
    method: 'post',
    data: data
  })
}

// 复制用例
export function copyCase(data) {
  return request({
    url: '/hrm/case/copy',
    method: 'post',
    data: data
  })
}

// 修改用例状态
export function changeCaseStatus(data) {
  return request({
    url: '/hrm/case/status',
    method: 'post',
    data: data
  })
}

// 修改用例
export function updateCase(data) {
  return request({
    url: '/hrm/case',
    method: 'put',
    data: data
  })
}

// 删除用例
export function delCase(caseId) {
  return request({
    url: '/hrm/case/' + caseId,
    method: 'delete'
  })
}


// debug用例
export function debugCase(data) {
  return request({
    url: '/hrm/runner/debug',
    method: 'POST',
    data: data
  })
}


/*
* 获取可使用的断言方法
* */
export function getComparator(data) {
  return request({
    url: '/hrm/common/comparator',
    method: 'GET',
    params: data
  })
}

export function uploadParamsFileToServer(data, inprocess) {
  return request({
    url: '/hrm/case/params/import',
    method: 'POST',
    data: data,
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      let percent = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        );
        console.log("上传进度:", percent + "%");
        inprocess.value = "上传进度: " + percent + "%";
        // ElMessage.success("上传进度: " + percent + "%");
    }
  })
}

// 查询用例参数列表
export function listCaseParams(query) {
  return request({
    url: '/hrm/case/params/list',
    method: 'post',
    data: query
  })
}

// 删除用例参数
export function delCaseParams(data) {
  return request({
    url: '/hrm/case/params/delete',
    method: 'delete',
    data: data
  })
}
