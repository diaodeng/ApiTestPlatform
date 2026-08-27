# Provider 多模型支持与模型管理

**日期**：2026-08-20

**变更类型**：功能增强

## 变更概述

支持一个 Provider 配置多个可用模型，使用方（工单 AI 分析、同步自动化配置、协同消息等）可按场景选择不同模型，实现"同一 API Key 不同模型"的灵活配置。

## 后端变更

### 新增接口
| 接口 | 方法 | 说明 |
|---|---|---|
| `/system/aiprovider/{provider_id}/model-catalog/all` | GET | 获取全部模型目录（含已禁用） |
| `/system/aiprovider/{provider_id}/model-catalog/refresh` | PUT | 从远端 API 拉取并持久化模型列表 |
| `/system/aiprovider/{provider_id}/model-catalog/items` | POST | 手动添加模型 |
| `/system/aiprovider/{provider_id}/model-catalog/items/{model_id}/toggle` | PUT | 启用/禁用模型 |
| `/system/aiprovider/{provider_id}/model-catalog/items/{model_id}` | DELETE | 删除手动添加的模型 |
| `/system/aiprovider/options/{provider_code}/models` | GET | 按编码获取可用模型下拉选项 |

### 修改文件
- `server/module_admin/entity/vo/ai_provider_vo.py`：新增 `AddProviderModelCatalogItemRequest`、`ToggleProviderModelCatalogItemRequest`、`ProviderModelOptionModel`
- `server/module_admin/dao/ai_provider_model_dao.py`：新增 `list_provider_models_all`、`list_enabled_models_by_provider_code`、`get_provider_model_by_id`、`add_provider_model`、`toggle_provider_model`、`delete_provider_model`
- `server/module_admin/service/ai_provider_model_catalog_service.py`：新增 `list_all_models`、`list_model_options_by_provider_code`、`refresh_and_persist_models`、`add_manual_model`、`toggle_model`、`delete_manual_model`
- `server/module_admin/service/ai_provider_protocol_service.py`：`generate_text()` 新增 `model_name` 可选参数
- `server/module_admin/controller/ai_provider_controller.py`：新增 6 个模型管理接口
- `server/modules/ticket/service/sync/ticket_sync_ai_config_service.py`：各 AI 配置段增加 `modelName` 字段，`resolve_task_settings()` 返回三元组
- `server/modules/ticket/service/ai/ticket_light_ai_service.py`：`_call_model_api()` 新增 `model_name` 参数，所有调用点透传配置中的模型名称

## 前端变更

### 修改文件
- `web/src/api/system/aiprovider.js`：新增 6 个模型管理 API 函数
- `web/src/views/system/aiprovider/index.vue`：Provider 编辑弹窗新增"可用模型"管理表格，支持添加/刷新/启用/禁用/删除模型
- `web/src/views/ticket/syncAutomation/index.vue`：翻译、标题总结、知识提炼、AI 分类、同步提取、汇总通知各 AI 配置段均新增模型选择器
- `web/src/views/ticket/syncAutomation/hooks/useSyncConfig.js`：各 AI 配置段表单和保存逻辑增加 `modelName` 字段
- `web/src/views/ticket/components/TicketDetailWithList.vue`：工单 AI 分析弹窗新增模型选择器
- `web/src/views/ticket/components/detail-tabs/TicketDetailCollabTab.vue`：协同消息表单新增模型选择器

### 权限控制
- 查看可用模型列表：`system:aiprovider:query`
- 从 API 刷新模型列表：`system:aiprovider:edit`
- 管理模型（启用/禁用/添加/删除）：`system:aiprovider:edit`

### 本次问题修复
- Provider 新增/编辑弹窗点击“更新模型”后，预览结果统一返回 `modelId`、`displayName`，默认模型下拉可以正常显示模型标识和展示名称。
- 工单 AI 分析和协同消息弹窗在自动回填 Provider 后会立即加载该 Provider 的启用模型，不再要求先手动切换 Provider。
- 工单分析与协同消息提交时会透传选择的模型；未选择模型时继续使用 Provider 的 `defaultModel`。服务端会拒绝不属于当前 Provider 启用目录的模型。


## 向后兼容
- 所有新增字段均为可选，空值时 fallback 到 Provider 的 `default_model`
- 已有配置项无需迁移，自动使用默认行为
- `resolve_task_settings()` 返回值从二元组变为三元组，调用方已全部更新