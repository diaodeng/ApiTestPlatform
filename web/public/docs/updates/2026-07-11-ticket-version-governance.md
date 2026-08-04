# 2026-07-11 工单版本治理批量维护与版本统计

## 背景

前序计划中第一、二阶段以及业务周快照已经完成，本次继续处理剩余的版本治理能力。现有工单主表已经包含 `affected_version`、`planned_fix_version`、`fixed_version`、`released_version`、`released_at`、`verified_at`，因此本轮不新增“已发版”流程状态，也不新增版本维度快照表。

## 本次实现

1. 新增后端版本治理服务 `TicketReleaseService`，职责限定为版本字段批量维护和版本统计聚合。
2. 新增接口：
   - `POST /ticket/release/batch`
   - `GET /ticket/release/statistics`
3. 工单列表增加多选列和“版本批量维护”按钮，支持批量设置：
   - 计划修复版本
   - 实际修复版本
   - 实际发版版本
   - 发版时间
   - 验证时间
   - 标记发版完成
   - 标记验证完成
4. 批量标记发版完成时写入 `TicketEventType.DEPLOYED` 事件；批量标记验证完成时写入 `TicketEventType.VERIFIED` 事件。
5. 工单列表增加“版本统计”弹窗，按当前筛选条件实时统计：
   - 发生版本：工单数、真实问题数、Issue 数、未处理数、未关闭数、Top 模块、Top 工单类型、Top 根因。
   - 修复/发版版本：工单数、Issue 数、已发版数、已验证数、未验证数、关闭结果、解决方式、细分问题。

## 口径说明

- `affected_version` 用于分析“哪个版本问题多”。
- `planned_fix_version` 用于排期治理。
- `fixed_version` 和 `released_version` 用于分析“哪个版本解决了什么问题”。
- `released_at` 表示实际发版完成时间。
- `verified_at` 表示验证完成时间。
- 版本统计当前读取 `ticket` 当前态实时聚合，历史工单后续被修改后，统计结果会跟随变化。

## 未实现项

版本维度快照表本轮未实现。若版本统计需要进入正式周报口径，建议后续新增 `ticket_version_statistics_daily`，按自然日冻结发生版本和修复/发版版本维度，避免实时字段变化影响历史报表。

## 验证记录

执行日期：2026-07-11。

1. `cd server && uv run ruff check modules/ticket tests/test_ticket_release_service.py server.py`：通过。
2. `cd server && uv run --with pytest python -m pytest tests/test_ticket_release_service.py`：2 passed。
3. `cd web && npm run build:prod`：通过；仍存在项目既有 Vite 大包、`config.js` 和 `eval` 警告。
