# 工单详情页翻译内容显示修复

## 日期

2026-08-24

## 问题

工单详情页的翻译区域有时显示的是纯译文，有时显示的是"原文 + 【AI翻译】标记 + 译文"的拼接内容，不一致。

## 根因

1. **后端 `ai_translation` 字段赋值使用了危险的 fallback**：多处代码写成 `extra_data["ai_translation"] = translation_meta.get("translated_text") or translated_description`，当 `translated_text` 为空字符串时，fallback 到了 `translated_description`（拼接文本），导致 `ai_translation` 被污染为拼接内容。

2. **前端 `TicketDetailView.vue` 缺少对 `description` 字段的【AI翻译】分割处理**：`detailOriginalDescription` 直接取 `detail.value.description` 作为 fallback，没有像 `TicketDetailWithList.vue` 那样做 `【AI翻译】` 分割。

## 修复

### 后端

- `server/modules/ticket/service/core/ticket_service.py`：
  - 创建工单的翻译赋值（行 1001）：`extra_data["ai_translation"]` 改为只取 `translation_meta.get("translated_text")` 的纯译文，不再 fallback 到 `translated_description`。
  - 编辑工单的翻译赋值（行 1253）：同上。

- `server/modules/ticket/service/sync/ticket_sync_post_process_service.py`（行 330）：同上，`extra_data["ai_translation"]` 改为只取纯译文。

- `server/modules/ticket/service/sync/ticket_sync_service.py`（行 613）：同上。

### 前端

- `web/src/views/ticket/components/TicketDetailWithList.vue`：`detailAiTranslation` 计算属性增加防御性逻辑，如果值中包含 `【AI翻译】` 标记，则自动截取标记之后的内容作为纯译文。

- `web/src/views/ticket/components/TicketDetailView.vue`：
  - `detailOriginalDescription` 计算属性对齐 `TicketDetailWithList.vue` 的实现，当 `description` 包含 `【AI翻译】` 时做分割处理，只取原文部分。
  - `detailAiTranslation` 计算属性增加与 `TicketDetailWithList.vue` 相同的防御性逻辑。

## 行为变化

- 翻译区域始终只显示纯译文，不再出现拼接内容。
- 翻译异常/跳过（总开关关闭、Provider 未配置、提示词缺失、API 调用失败等）时，`ai_translation` 不会写入，前端不显示翻译区块。
- 描述区域始终只显示原文（含 `【AI翻译】` 分割处理）。

## 验证

- 前端 `npm run dev` 后进入工单详情页，确认：
  - 有翻译结果的工单：翻译区域只显示纯译文，不显示原文和 `【AI翻译】` 标记。
  - 无翻译结果的工单：不显示翻译区域。
  - 描述区域始终只显示原文。