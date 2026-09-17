import request from '@/utils/request'

// 大数据查询：数据源下拉
export function listUnidataSources() {
  return request({ url: '/unidata/sources', method: 'get' })
}

// 大数据查询：权限驱动的库清单
export function listUnidataDatabases(sourceCode) {
  return request({ url: `/unidata/sources/${sourceCode}/databases`, method: 'get' })
}

// 大数据查询：动态探测数据源可用的查询引擎
export function listUnidataEngines(sourceCode, refresh) {
  return request({ url: `/unidata/sources/${sourceCode}/engines`, method: 'get', params: { refresh } })
}

// 大数据查询：库下表清单（分页 + 关键字过滤）
export function listUnidataTables(sourceCode, query) {
  return request({ url: `/unidata/sources/${sourceCode}/tables`, method: 'get', params: query })
}

// 大数据查询：表字段清单（字段名/类型/备注）
export function listUnidataColumns(sourceCode, tableFullName) {
  return request({ url: `/unidata/sources/${sourceCode}/table-columns`, method: 'get', params: { tableFullName } })
}

// 大数据查询：只读 SQL 执行
export function executeUnidataQuery(sourceCode, data) {
  return request({ url: `/unidata/sources/${sourceCode}/query`, method: 'post', data })
}
