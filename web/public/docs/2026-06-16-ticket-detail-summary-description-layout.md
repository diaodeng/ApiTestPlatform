# 工单详情顶部描述布局优化

## 背景

工单详情弹窗顶部使用 `el-descriptions` 展示基础信息。描述字段可能包含大量文本，放在同一个详情表格中会参与表格列宽和行高计算，导致顶部基础信息区域被撑变形。同时灰色标签列在宽度不足时会换行，使原本信息较少的行被抬高。

## 变更

1. 工单详情弹窗顶部基础信息表格不再直接包含“描述”字段，描述改为紧跟表格下方的独立整行区域。
2. 独立描述区域自动展示全部内容，不再限制高度；长描述只影响自身区域，不参与顶部基础信息表格布局计算。
3. 顶部基础信息表格的灰色标签列设置为不换行，避免“当前处理人”“日志拉取状态”等标签换行后撑高短信息行。
4. 根因和解决方案仍保留在顶部表格内作为整行展示，避免改变现有概览信息层级。
5. 详情接口会从 `extra_data.origin_description` 和 `extra_data.ai_translation` 拆分原文与译文；页面在描述下方单独展示译文，避免原文和翻译混在同一段文本中。
6. 描述标签旁新增“翻译”按钮，复用工单轻量翻译配置 `ticket.ai.translate.provider.code` 与 `ticket.ai.translate.prompt.code`。如果未开启翻译、未配置 Provider 或未配置提示词，后端返回明确提示，不写入空译文。

## 涉及文件

- `server/modules/ticket/controller/ticket_controller.py`
- `server/modules/ticket/service/ticket_service.py`
- `web/src/api/ticket/ticket.js`
- `web/src/views/ticket/index.vue`

## 验证

- 已执行 `cd server && uv run python -m py_compile modules\ticket\controller\ticket_controller.py modules\ticket\service\ticket_service.py`。
- 已执行 `cd web && npm run build:prod`，构建通过；仅保留既有 Vite chunk 体积提示。
