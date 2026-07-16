# 工单列表根因分类和解决方式筛选修复

## 背景

工单列表中“根因分类”和“解决方式”列展示为统计枚举的中文名称，但部分历史 AI 自动分类数据把中文名称直接写入了 `ticket.root_cause_type` 和 `ticket.solution_type`。列表筛选下拉传递的是枚举编码，导致用户看到列表中有“代码缺陷”“代码修复”等数据，但按相同选项筛选时查不到。

## 本次调整

1. `TicketLightAiService._normalize_structured_classification_result` 归一化结构化分类结果时，`rootCauseType` 和 `solutionType` 改为回填枚举 `value`，后续新数据统一写编码。
2. `TicketService.get_ticket_list_services` 调用 DAO 前会读取当前统计枚举，把根因分类和解决方式筛选值从编码扩展为“编码 + 显示名”。例如 `code_defect` 会扩展为 `code_defect,代码缺陷`，兼容历史中文入库数据。
3. DAO 仍保持只做数据访问和 `IN` 过滤，不直接依赖配置服务。

## 验证

1. 新增 `server/tests/test_ticket_list_stat_filter.py`，覆盖 AI 分类归一化写编码，以及列表筛选参数扩展为编码和中文标签。
2. 当前本地虚拟环境未安装 `pytest`，`uv run python -m pytest tests/test_ticket_list_stat_filter.py` 无法执行。
3. 已用 `uv run python -` 执行等价断言，验证归一化和筛选扩展结果。
4. 已执行 `uv run ruff check modules/ticket/service/ai/ticket_light_ai_service.py modules/ticket/service/core/ticket_service.py tests/test_ticket_list_stat_filter.py`，检查通过。

## 影响范围

只影响工单列表根因分类和解决方式筛选，以及后续 AI 自动分类写入主表的字段值。已有中文标签历史数据无需迁移即可被筛选命中。
