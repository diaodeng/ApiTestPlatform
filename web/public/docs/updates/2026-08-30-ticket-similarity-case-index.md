# 工单相似度案例索引实施记录

- 变更日期：2026-08-30
- 变更范围：工单相似检索、处理案例、详情展示和 AI/RCA 结果沉淀。

## 变更内容

- `EmbeddingRecord` 增加 `embedding_scope`，区分 `symptom`、`case_draft` 和 `case_verified`，旧记录迁移为 `symptom`。
- 新增 `ticket_similarity_profile`、`ticket_similarity_signal`、`ticket_similarity_case` 三张 MySQL 表。
- 表现相似向量默认收敛为标题、描述、稳定摘要、症状和重要关键词，移除工单号、模块、分类、根因、方案、RCA、状态和处理人噪声。
- 初次入库和已有向量刷新时尽量建立环境、版本、错误码、Trace ID 和 Request ID 画像；缺失字段不阻塞主流程。
- 详情相似查询增加精确检索信号候选、分项分数、命中原因、冲突信息和案例状态；向量扫描使用数据库分批读取。
- AI 分析成功和人工 RCA 保存后创建案例草稿；案例状态支持草稿、已验证和驳回，案例向量在业务事务提交后异步生成。
- 已验证案例内容变化时自动回退草稿，避免旧结论继续作为高可信经验。
- 生产链路不依赖 Qdrant；`Embedding` 继续作为生产 Provider，`local_hash` 用于测试，Qdrant 保留开发和未来加速能力。

## 数据迁移

执行 `server/sql/20260830_ticket_similarity_case_index.sql`。脚本只新增字段、索引和表，不迁移或删除 `ticket.extra_data`。已有向量不重新调用外部模型，默认按 `symptom` scope 继续使用。

## 使用说明

详情页相似结果中的“命中”和“冲突”用于解释推荐依据；案例草稿需要人工检查根因、解决方案、证据和验证方式后，才能点击“确认案例”。案例确认不会自动绑定问题实例。
