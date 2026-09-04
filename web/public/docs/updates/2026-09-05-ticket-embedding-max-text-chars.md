# 工单向量化文本超长截断与相似检索文本同构修复

**日期**：2026-09-05

**变更类型**：缺陷修复 + 功能增强

## 背景与问题

生产环境工单 `INC00001924237`（MN/3547）同步后自动化执行失败，通知原因：

```
外部Embedding生成失败，严格模式不回退本地哈希: provider=openai_compatible,
error=Embedding请求失败: status=400, detail={"code":20015,"message":"The parameter is invalid. Please check again."}
```

根因分析结论：

1. 同步后自动化链路的相似工单检索复用了 `collect_text()` 构建检索文本，该方法为字段识别设计，会把 `extra_data.raw_payload`（外部系统原始报文）整体 JSON 序列化拼入文本；
2. 该工单 raw_payload 序列化后 17,373 字符，拼接后检索文本达 25,052 字符，超过 SiliconFlow `BAAI/bge-m3` 模型 8192 token 输入上限（实测英文约 16,300 字符即触发），上游返回 400/20015；
3. 严格模式下外部 Embedding 失败不降级，整个同步后自动化被判定失败并发送【失败】通知。

生产库超长工单分布：description > 8000 字符 45 单、> 16000 字符 14 单，属常态风险而非孤例。

## 修复方案

### 1. 相似检索文本与入库向量同构（根因）

`ticket_sync_automation_service.run_sync_automation` 中相似检索文本从 `collect_text(ticket)` 切换为 `TicketEmbeddingService.build_ticket_text(ticket, config, scope=symptom)`，与库内向量的字段构成完全对齐：

- 工单号、raw_payload JSON、root_cause、solution 退出查询向量，与文档设计对齐；
- 修复了查询侧含 raw_payload、入库侧不含的向量分布不一致缺陷，相似度质量预期提升；
- 该工单检索文本从 25,052 字符降至 7,594 字符，实测调用成功（200）；
- 历史入库向量无需重建（入库侧文本未变，内容哈希不变）。

`detect_fields` 的 `collect_text` 用法保持不变（字段识别需要全文正则）。

### 2. Embedding 配置新增 maxTextChars 文本上限（兜底防线）

`TicketEmbeddingService`：

- 配置新增 `embedding.maxTextChars`（默认 12000，0=不限制，读取/保存两侧均做 0~100000 夹逼规范化）；
- `_embed_text_openai_compatible` 请求前按字符数截断 input，并记录 warning 日志（originalChars/maxTextChars）；
- 12000 字符以 bge-m3 8192 token 为基准留中英混合安全余量；更换模型时按其上下文长度调整；
- 截断只影响送入外部接口的内容，内容哈希基于完整文本计算，结果可复现。

`build_ticket_text` 构建完成后按同一预算做字段级裁剪（`_shrink_text_within_budget`）：

- 整体超预算时压缩超过均摊长度的长行（描述类正文），保留行首（邮件工单关键信息集中头部）；
- 标题、AI 摘要等短字段天然完整保留；
- 行级压缩后仍超预算时从尾部整体截断兜底；
- 未超预算的文本原样返回，不改写。

### 3. 前端配置页治理

`similarityConfig/index.vue`：

- 向量化字段选项从 14 项收敛为后端实际生效的 5 项：标题、描述、AI摘要、RCA问题现象、重要关键词（删除工单号、原始描述、最终根因、解决方案、RCA结构化内容、模块、分类、工单类型、状态、处理人等静默无效选项）；
- 默认 fields 对齐后端白名单 `['title', 'description', 'aiSummary', 'symptom', 'importantKeywords']`；
- Embedding 服务卡片新增"文本上限(字符)"输入（0~100000，步进 1000），带说明提示，payload 透传 `maxTextChars`。

## 修改文件

- `server/modules/ticket/service/ai/ticket_embedding_service.py`：新增 `DEFAULT_MAX_TEXT_CHARS`、`maxTextChars` 配置规范化（读取+保存）、`_embed_text_openai_compatible` 请求前截断、`_resolve_max_text_chars`、`_shrink_text_within_budget`，`build_ticket_text` 接入预算裁剪
- `server/modules/ticket/service/sync/ticket_sync_automation_service.py`：相似检索文本切换到 `build_ticket_text`
- `web/src/views/ticket/similarityConfig/index.vue`：字段选项收敛、默认值对齐、文本上限配置项
- `server/tests/test_ticket_embedding_service.py`：新增 5 个测试用例
- `web/public/docs/ticket_similarity.md`：用户说明同步更新

## 验证结果

- `uv run pytest tests/test_ticket_embedding_service.py`：29 passed
- `uv run ruff check`（三个改动 py 文件）：All checks passed
- 端到端验证：用 INC00001924237 生产库真实数据走新 `build_ticket_text`（7,594 字符）实际调用 SiliconFlow 接口返回 200

## 遗留事项

- 生产配置 `fields` 中残留的旧 schema 项（rootCause/solution/rca/moduleName/categoryName/tags）由后端静默忽略，不影响功能；下一次在配置页保存配置时会自动清理为白名单值。
- `sys_ai_provider_model.capability_overrides` 目前是预留字段（全库无读取逻辑）。后续若在 Provider 模型管理中实装"上下文长度"属性，可让 `maxTextChars` 默认取自模型上下文长度、当前配置作为覆盖值，避免新增模型时重复手工配置。

## 后续验证建议

- 生产部署后观察下一次外部同步工单的自动化通知，确认不再出现 20015；
- 在配置页保存一次相似度配置，验证字段列表自动收敛为 5 项白名单；
- 可对历史超长工单（description > 12000 字符的 30 单）执行一次手动向量重建，验证截断链路与幂等复用。
