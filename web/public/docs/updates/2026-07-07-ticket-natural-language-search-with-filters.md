# 2026-07-07 工单自然语言搜索支持过滤条件

## 问题
工单列表的自然语言搜索接口 `/ticket/search/natural-language` 只接受 `keyword` 和 `limit` 参数，会忽略其他过滤条件（如状态、项目、模块、优先级等）。

## 解决方案
修改自然语言搜索接口，支持与其他过滤条件结合使用：
1. 先执行自然语言搜索，得到工单ID和相似度分数
2. 用这些工单ID作为过滤条件，调用普通列表查询
3. 返回结果时保留相似度分数

## 改动文件

### 1. `server/modules/ticket/controller/ticket_crud_controller.py`
- 修改 `search_ticket_natural_language` 接口，接受 `TicketQueryModel` 作为查询参数
- 先调用 `TicketEmbeddingService.search_tickets` 得到工单ID和分数
- 用这些ID调用 `TicketService.get_ticket_list_services` 查询工单列表
- 为结果添加 `similarityScore` 字段

### 2. `server/modules/ticket/entity/vo/ticket_vo.py`
- 在 `TicketQueryModel` 中添加 `ticket_ids` 字段，用于自然语言搜索后的ID过滤

### 3. `server/modules/ticket/dao/ticket_dao.py`
- 在 `get_ticket_list` 方法中解析 `ticket_ids` 参数
- 添加 `Ticket.ticket_id.in_(ticket_ids)` 过滤条件

## 使用方式
```
GET /ticket/search/natural-language?keyword=POS日结失败&status=processing_two&project_id=123&limit=20
```

返回结果包含：
- 所有普通列表字段（支持分页）
- 每条记录额外包含 `similarityScore` 相似度分数

## 验证
- 三个文件编译通过
- 需要重启后端服务并测试自然语言搜索接口
