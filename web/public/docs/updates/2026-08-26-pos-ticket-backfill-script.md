# 2026-08-26 POS 历史工单分类补录脚本

- 新增 `server/scripts/backfill_pos_ticket_issue_classification.py`，用于一次性治理 `.env.prod` 中 POS 相关、状态达到“5. 产研处理完毕”及之后的历史工单。
- 脚本支持 `preview / apply / rollback` 三种模式，默认先导出预览统计、细分问题候选和 issue 归并候选，不直接改库。
- 细分问题枚举会基于 `ticket.sync.automation` 配置自动补齐缺失的 `problemPatterns`，避免只写工单字段但前端没有选项。
- issue 只对白名单中的高置信问题桶自动创建或复用，像 `sco_account_freeze`、`new_store_setup` 这类非问题类仍会统计，但不会自动建 issue。
- `apply` 会额外生成本地回滚工件 JSON，后续可以用 `rollback --artifact <文件>` 回退本次补录。
- 2026-08-26 14:50 进一步收紧了 POS 细分问题识别口径：`coupon / DCR` 优先归“优惠券”，`VMS` 仅在“礼券申报/权限”上下文命中，`ILS / S21 / V21 / DATA8 / TLOG` 相关统一按“销售回传/补数”识别。
- 新增英文/数字关键词边界匹配，避免把 `details` 误判成 `ILS`、把 `reported` 误判成 `report` 这类子串误命中。
- 最新 preview（2026-08-26 14:50）范围 1526 单，计划补细分问题 757 单，issue 归并候选 85 单；其中优惠券 17、礼券申报 6、销售回传 77、报表缺失 9。
