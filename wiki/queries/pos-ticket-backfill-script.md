---
title: POS 历史工单分类补录脚本
type: query
created: 2026-08-26
updated: 2026-08-26
---

# POS 历史工单分类补录脚本

- 脚本位置：`server/scripts/backfill_pos_ticket_issue_classification.py`
- 目标：对 `.env.prod` 中 POS 相关、状态达到“5. 产研处理完毕”及之后的历史工单做一次性分类补录。
- 范围：补问题大类、补细分问题、补 `ticket.sync.automation.statClassification.problemPatterns` 缺失枚举、按白名单问题桶生成或复用 `ticket_issue`。
- 安全策略：
  - 默认走 `preview`；
  - 已绑定 `issue_id` 的工单默认不重复处理；
  - `problem_pattern_verified=true` 的工单不覆盖人工确认细分问题；
  - 非问题类只统计，不自动建 issue；
  - `apply` 会落本地 rollback 工件。
- 命令：
  - `uv run python scripts/backfill_pos_ticket_issue_classification.py preview`
  - `uv run python scripts/backfill_pos_ticket_issue_classification.py apply --issue-confirmed`
  - `uv run python scripts/backfill_pos_ticket_issue_classification.py rollback --artifact <rollback.json>`

## 2026-08-26 二次收紧口径

- 优惠券：只有 `coupon / 优惠券 / yuu coupon / food coupon / DCR` 且上下文像“兑换失败 / 未同步 / 不可使用”时才归到 `promo_coupon_not_sync`。
- 礼券：`vms_declaration_permission` 只保留 `VMS + declaration/permission` 这类“礼券申报/账号权限”问题，普通礼券支付失败回落到其他细分问题，不再因为评论里出现 `VMS callback` 就直接命中。
- 销售回传：`ILS / S21 / V21 / DATA8 / TLOG` 改为精确词边界匹配，避免 `details -> ils` 的子串误判；同时保留 `sales file / redemption file / daily redemption status file / 销售回传` 这类直接语义。
- 报表缺失：`report` 改为精确词命中，避免 `reported -> report` 误判，并排除 `HKVMS / GV discrepancy / transaction id / flat key` 等明显非报表缺失场景。
- 最新 preview 文件：`server/scripts/output/pos_ticket_backfill/20260826_145048_preview_summary.json`
