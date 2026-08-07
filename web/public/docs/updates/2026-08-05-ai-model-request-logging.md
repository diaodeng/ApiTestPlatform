# 2026-08-05 AI 模型请求日志增强

## 变更概述
在 AiProviderProtocolService._request() 公共网关中增加请求前/请求后日志，覆盖所有 AI 模型 HTTP 调用场景。

## 改动文件
- server/module_admin/service/ai_provider_protocol_service.py

## 改动内容
1. 新增导入：import json、from utils.log_util import logger
2. 新增常量：_API_KEY_MASK_MIN_LEN = 8（密钥脱敏长度阈值）
3. 新增辅助方法：
   - _mask_headers()：对 Authorization / api-key / x-api-key 等敏感头进行脱敏（保留首4+末4字符）
   - _truncate_text()：截断文本到 100 字符，超出部分标注总长度
   - _format_request_body()：格式化 JSON 请求体并截断
4. 修改 _request() 方法：
   - 请求前：logger.info 记录 method / url / timeout / headers（脱敏）/ body（截断<=100字符）
   - 请求成功：logger.info 记录 method / url / status_code / response_size
   - HTTP错误：logger.error 记录 method / url / status_code / response_body（截断前200字符）
   - 超时：logger.error 记录 method / url / timeout / 原因
   - 其他异常：logger.error 记录 method / url / 异常类型 / 原因

## 覆盖场景
由于所有 AI 模型 HTTP 调用都经过 _request() 这一个公共网关，本次改动覆盖以下全部场景：
- Provider 模型目录探测（discover_models）
- Provider 连接测试（test_connection）
- 工单轻量 AI（摘要/标题/提取/分类/翻译）
- 工单话题分类（TicketTopicStatsService）
- 工单同步通知摘要（TicketSyncNotifyService）

## 日志示例（脱敏后）
AI model request: method=POST url=https://api.openai.com/v1/chat/completions timeout=30s headers=...Authorization: sk-p***4gAb... body=...(215chars)
AI model success: method=POST url=https://api.openai.com/v1/chat/completions status=200 size=1247bytes
