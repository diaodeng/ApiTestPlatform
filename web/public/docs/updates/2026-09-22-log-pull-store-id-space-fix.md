# 2026-09-22 日志拉取门店编号空间治理（生产 INC00002013662 排查产物）

## 变更主题

工单来源门店编码（store_code，如 SAP 编号）与日志接口门店机构号（org_no）在 web 弹窗回显与 hints 落库两个环节存在空间混用：回显值可能被跨列匹配改写到错误门店，未匹配的来源编码可能被当 org_no 提交。本次统一为"提交字段只承载 org_no、来源编码只做展示"，并给手输新店 org_no 的合法场景保留二次确认通道。

## 问题现象（INC00002013662）

- 工单来源 `(IT)StoreCode=215087`，自动链路正确映射为 org_no=333（WATERSIDE[333]，外部平台名"雅濤居"），拉取日志本身正确。
- 但弹窗回显打开后，门店值 333 被前端 `syncStoreSelection` 以三字段（storeId/storeCode/sapOrgNo）OR 跨列匹配改写为 550944——惠康门店配置中 org_no=550944 的仓库行（WarehouseLogistics-Chilled）其 `sap_org_no` 恰好也是 333，且选项列表按 `org_name ASC` 排序该行在前，`.find()` 先命中，表单值被静默改写、无任何告警；此时直接提交会把拉取发到错误门店（后端 create 链路无 org_no 校验，拦不住）。

## 根因

1. **前端跨列匹配**：`syncStoreSelection` / `storeHintMessage` 把 org_no 空间的值与 `sap_org_no` 混在一个候选列表里匹配并改写，碰撞时结果由选项排序决定。
2. **hints 空间污染**：`resolve_store_by_external_value` 匹配失败时原样返回外部编码，`refresh_log_pull_hints` 无条件把 `detected.storeId` 写进 `hints.storeId`——未匹配的 store_code 由此进入回显链路；`external_field_mapping.ticketStore`（store_code 空间）还作为 storeId 的最后一级回填兜底。
3. **提交无校验**：web 创建/后台执行/外部提交全链路只校验非空，无法区分"用户手输的新店 org_no"与"系统回填的未匹配 store_code"。

## 修复内容

### 后端

- `detect_fields`（ticket_sync_automation_service.py）新增 `storeMappingMatched` 标记：`storeId` 来自当前源数据的唯一成功映射（org_no 空间）时为 True；匹配失败透传原值时为 False。自动化门禁（`verify_store_by_org_no` 拦截跳过）行为不变。
- `refresh_log_pull_hints`（ticket_sync_payload_service.py）按标记决定写入：
  - 匹配成功 → 正常写入 `hints.storeId`（org_no）；
  - 匹配失败且 storeId 与本次源编码一致（透传特征）→ **不写入，并清除旧 `storeId`**（旧映射已不可信），原始编码仍保留在 `sourceStoreCode` 供展示；
  - 本次未携带门店字段（源编码为空）→ 保留旧值（上次有效参数快照）；
  - 键缺失（旧调用方/手工构造 detected）→ 维持旧写入行为，向后兼容。

### 前端

- `LogPullConfigFields.vue`：
  - `syncStoreSelection` 收窄为 **org_no-only 匹配**（仅 `storeId`/`storeCode` 两列，均为 org_no 空间），不再与 `sapOrgNo` 跨列匹配改写；
  - `storeId` 为空且表单携带 `sourceStoreCode` 时，允许按 `sapOrgNo` **唯一**兜底匹配回填 org_no（空间对应正确），匹配不到保持为空；
  - `storeHintMessage` 重构：携带来源编码时优先展示映射关系——"工单门店编码 xxx → 已匹配门店（org_no=yyy）"（info）/"与当前所选门店不一致，请确认"（警告）/"未匹配到门店，请手动输入正确的 org_no"（警告）；提示类型改为动态（info/warning）；
  - 新增 `store-match-change` 事件向提交方回报匹配状态；
  - 手动切换商家时同步清空 `sourceStoreCode`。
- `useLogViewer.js` / `logPullRecord/index.vue` 回填优先级调整：`storeId` 候选中移除 store_code 空间的 `ticketStore`（`external_field_mapping.ticketStore` 改为进展示位 `sourceStoreCode`）；提交前若门店按 org_no 匹配不到当前商家配置，弹出二次确认"确认按 org_no 直接提交？"——放行手输新店 org_no 的合法场景，同时拦住误填/残留的来源编码。
- `logPull.shared.js`：表单默认值增加 `sourceStoreCode` 展示位；复制参数路径清空该展示位。
- 提交 payload 不包含 `sourceStoreCode`（工单 Tab 显式构造 / 管理页 `delete payload.sourceStoreCode`）。

## 数据库

无结构变更。

## 验证

- 新增 `tests/test_ticket_sync_store_hints_space.py` 5 个用例：匹配成功写入、匹配失败不写并清除旧值、无源编码时保留旧值、缺省键兼容旧行为、detect_fields 透传分支标记输出；连同既有 `test_ticket_sync_log_pull_hints.py`、`test_ticket_summary_log_pull_hints.py`、`test_ticket_notify_service.py` 共 13 个用例全部通过。
- `test_ticket_sync_mapping_boundary.py` 中 12 个用例因测试夹具 SimpleNamespace 缺少 `detected_version_key` 属性失败，为**存量问题**（HEAD 上同样失败），与本次改动无关。
- 改动文件 ruff 全部通过；前端 `npm run build:prod` 构建通过。

## 用户说明同步

- [日志拉取使用说明](../ticket_log_pull.md)：新增"门店编码的两个空间"章节，更新回填规则与提交二次确认说明。
