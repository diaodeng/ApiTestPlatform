# 2026-07-06 相似工单主动拉取场景与 Embedding 自定义参数

## 背景

相似工单配置中的“启用检索”是全局能力开关：关闭后不执行相似查询，也不会自动刷新向量。自动刷新场景中的开关只控制对应业务入口入库后是否刷新向量。

飞书多维表格主动拉取此前复用 `externalSync` 场景，导致关闭自动刷新场景中的其他开关时，仍可能被“外部同步入库”开关控制并执行向量化。部分 OpenAI 兼容 Embedding 模型也不支持 `dimensions` 参数，默认下发会导致接口报错。

## 本次改动

1. `sceneTriggers` 新增 `bitablePull`，页面展示为“多维主动拉取入库”。
2. `TicketBitablePullService` 主动拉取入库和延后后处理场景从 `external_sync` 改为 `bitable_pull`。
3. `TicketSyncPostProcessService` 将 `bitable_pull` 映射到相似工单场景 `bitablePull`，不再受 `externalSync` 自动刷新开关影响。
4. 旧配置中缺少 `bitablePull` 时会继承 `externalSync` 的值，避免升级后把已关闭的主动拉取向量化重新打开。
5. OpenAI 兼容 Embedding 请求默认只发送 `model` 和 `input`，不再自动把 `embedding.dimension` 写入 `dimensions`。
6. 相似工单配置页新增“自定义请求参数”，保存为 `embedding.requestParams` JSON 对象；需要模型支持维度裁剪时，可手动填写 `{"dimensions": 1024}`。
7. `embedding.dimension` 继续作为返回向量长度校验依据。接口返回长度与配置不一致时，服务会记录错误日志并中断向量化流程，避免把错误维度写入数据库或 Qdrant。

## 当前配置语义

- `enabled`：相似工单检索总开关。关闭后相似查询和自动向量刷新都不执行。
- `sceneTriggers.externalSync`：外部系统调用 `/ticket/sync/external` 入库后的向量刷新开关。
- `sceneTriggers.bitablePull`：飞书多维表格主动拉取入库后的向量刷新开关。
- `sceneTriggers.remotePull`：内网远端拉取入库后的向量刷新开关。
- `embedding.dimension`：期望向量维度，只用于幂等判断、返回维度校验和 Qdrant collection 维度匹配。
- `embedding.requestParams`：透传到 Embedding 请求体的自定义 JSON 对象，适合按模型能力自行添加 `dimensions`、`encoding_format` 等参数。

## 验证

1. `cd server; uv run python -m unittest tests.test_ticket_embedding_service`
2. `cd server; uv run ruff check modules/ticket/service/ai/ticket_embedding_service.py modules/ticket/service/sync/ticket_bitable_pull_service.py modules/ticket/service/sync/ticket_sync_post_process_service.py tests/test_ticket_embedding_service.py`
