# 2026-07-07 工单自然语言搜索排序修复

## 问题
自然语言搜索时，结果按提交时间排序而非按相似度排序，因为前端会传递 `sortField=submitTime` 参数。

## 解决方案
自然语言搜索默认按相似度由高到低排序，忽略其他排序字段。

## 改动文件

### 1. `server/modules/ticket/controller/ticket_crud_controller.py`
- 自然语言搜索接口中清除 `sort_field` 和 `sort_order`
- 设置 `is_page = False` 获取全部结果
- 返回前按 `similarityScore` 降序排序

### 2. `web/src/views/ticket/hooks/useTicketList.js`
- `handleNaturalSearch` 中删除 `sortField` 和 `sortOrder` 参数

## 排序逻辑
1. 后端执行向量搜索，得到工单ID和相似度分数
2. 用工单ID过滤条件查询工单详情
3. 为每条记录添加 `similarityScore` 字段
4. 按 `similarityScore` 降序排序后返回

## 验证
- 后端语法检查通过
- 需要重启后端服务并测试自然语言搜索
