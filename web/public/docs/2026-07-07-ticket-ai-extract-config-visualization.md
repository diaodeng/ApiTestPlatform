# 工单同步AI提取配置可视化

## 日期
2026-07-07

## 背景
之前AI提取门店、POS、SCO、日期、版本号等功能已实现，但配置不够可视化：
1. 场景级开关定义了但未实际使用，总开关 `ticket.ai.log_extract.enabled` 控制了所有AI提取逻辑
2. 前端无法看到和配置具体要提取哪些字段
3. 总开关的职责不清晰，应该只控制从日志中提取版本号
4. 提示词配置不够友好，用户没有配置时没有默认提示词可用
5. 之前错误地复用了 `ticket_log_extract_default`（用于日志提取），需要新增专门用于工单同步提取的提示词

## 变更内容

### 后端变更

#### 1. `ticket_sync_config_service.py`
- 新增 `default_ai_sync_extract_config()` 方法，定义AI同步提取的默认配置
- 在 `default_sync_config()` 中添加 `aiSyncExtract` 默认配置
- 在 `normalize_sync_config()` 中添加 `aiSyncExtract` 的规范化逻辑

默认配置结构：
```python
{
    "externalPushEnabled": False,  # 外部推送场景开关
    "remotePullEnabled": False,    # 远端拉取场景开关
    "bitablePullEnabled": False,   # 多维表格拉取场景开关
    "providerCode": "",            # Provider编码
    "promptCode": "ticket_sync_extract_default",  # 提示词编码，默认使用工单同步提取模板
    "extractFields": ["storeName", "posNo", "scoNo", "logDate", "versionKey"],  # 提取字段列表
}
```

#### 2. `ticket_light_ai_service.py`
- 新增 `DEFAULT_SYNC_EXTRACT_PROMPT` 常量，定义工单同步提取的默认提示词
- `extract_ticket_sync_fields()` 新增 `sync_scene` 参数
- 使用 `is_sync_extract_enabled_for_scene()` 替代 `is_log_extract_enabled()` 作为场景级开关
- 从同步配置JSON的 `aiSyncExtract` 中读取 Provider/Prompt 编码（兜底使用旧的 sys_config 键）
- 当用户未配置提示词时，自动使用 `ticket_sync_extract_default` 作为默认提示词
- 根据 `extractFields` 配置过滤实际提取的字段
- 提取结果新增 `store` 和 `versionKey` 字段
- `is_sync_extract_enabled_for_scene()` 改为从同步配置JSON读取场景级开关，不再兜底使用总开关

#### 3. `ticket_sync_post_process_service.py`
- 调用 `extract_ticket_sync_fields()` 时传递 `sync_scene` 参数

#### 4. `ai_prompt_template_service.py`
- 新增 `ticket_sync_extract_default` 模板（工单同步AI提取默认提示词）
- 在 `ensure_default_prompt_templates()` 中，当 `ticket_sync_extract_default` 的 `prompt_content` 为空时，自动使用 `DEFAULT_SYNC_EXTRACT_PROMPT` 补齐
- 恢复 `ticket_log_extract_default` 的原始用途（日志参数提取占位模板）

### 前端变更

#### `syncAutomation/index.vue`
- AI提取卡片增加"提取字段配置"区域，使用 checkbox-group 可视化展示可提取字段：
  - 门店名称 (storeName)
  - POS编号 (posNo)
  - SCO编号 (scoNo)
  - 日志日期 (logDate)
  - 版本号 (versionKey)
- 更新场景开关的描述文案，明确说明"启用AI提取下方勾选的字段"
- 底部说明更新：明确总开关 `ticket.ai.log_extract.enabled` 仅控制从日志中提取版本号

#### `syncAutomation/hooks/useSyncConfig.js`
- `aiSyncExtract` 默认值增加 `extractFields` 数组
- `promptCode` 默认值改为 `ticket_sync_extract_default`
- `applyConfig()` 和 `handleSave()` 中增加 `extractFields` 的读写处理

## 提示词配置说明

### 两个不同的提示词模板

| 模板编码 | 用途 | 使用场景 |
|----------|------|----------|
| `ticket_sync_extract_default` | 从工单信息中提取门店/POS/SCO/日期/版本号 | 工单同步时（外部推送/远端拉取/多维表格拉取） |
| `ticket_log_extract_default` | 从日志文本中提取参数 | 拉取日志后分析日志内容时使用 |

### 配置Key
- **同步配置JSON**: `aiSyncExtract.promptCode`（前端可视化配置）
- **兜底sys_config键**: `ticket.ai.log_extract.prompt.code`

### 默认提示词
- **模板编码**: `ticket_sync_extract_default`
- **模板名称**: 工单同步AI提取默认提示词
- **分类**: common
- **内容**: 系统启动时自动初始化，用户可在"AI提示词管理"中查看和编辑

### 提示词优先级
1. 同步配置JSON中的 `aiSyncExtract.promptCode`
2. sys_config中的 `ticket.ai.log_extract.prompt.code`
3. 默认提示词 `ticket_sync_extract_default`

## 开关职责说明

| 开关 | 位置 | 职责 |
|------|------|------|
| `aiSyncExtract.externalPushEnabled` | 同步配置JSON | 控制外部推送场景是否启用AI提取 |
| `aiSyncExtract.remotePullEnabled` | 同步配置JSON | 控制远端拉取场景是否启用AI提取 |
| `aiSyncExtract.bitablePullEnabled` | 同步配置JSON | 控制多维表格拉取场景是否启用AI提取 |
| `aiSyncExtract.extractFields` | 同步配置JSON | 控制AI提取哪些字段 |
| `aiSyncExtract.promptCode` | 同步配置JSON | 指定使用的提示词模板编码 |
| `ticket.ai.log_extract.enabled` | sys_config | 仅控制从日志文本中提取版本号（正则匹配） |

## 验证
- 后端语法检查通过
- 前端配置界面可正常显示和保存提取字段配置
- 场景级开关独立控制各场景的AI提取
- 总开关不再影响AI提取逻辑，仅控制日志版本号提取
- 用户未配置提示词时自动使用默认提示词

## 风险
- 历史数据中如果 `aiSyncExtract` 为空，会使用默认配置（所有字段都提取、场景开关关闭）
- 如果之前依赖总开关控制AI提取，需要改为使用场景级开关
- 默认提示词会在系统启动时自动初始化到数据库
