# 2026-09-07 日志版本号提取正则收紧并支持可视化配置

## 变更背景

日志拉取链路原先使用一条宽松的硬编码正则从日志中提取版本号（`(?:版本号|版本|version|...)\s*[:：=]\s*(...)`），且"全文首个命中即返回"。实际 POS 日志中存在多类带 `version` 字样的行，导致误提取：

- 正确版本行：`ms_h:1, ms_l:1, ls_h:6, ls_l:8, version:1.1.6.8`（POS 应用版本）
- 误报行 1：`从主进程环境参数获取到launcher_version:1.0.6.8`（启动器版本，正则无左边界，`launcher_version` 中的 `version` 子串命中）
- 误报行 2：`GL: OpenGL parsed version: 4, 6`（显卡解析版本，单数字片段也命中）

当误报行在日志中先出现时，工单会被错误回填 `1.0.6.8` 等非应用版本。

## 变更内容

### 1. 版本提取正则收敛为可配置

- 新增 `server/modules/ticket/util/ticket_log_version_extract_util.py`，集中定义：
  - `DEFAULT_LOG_VERSION_PATTERNS`：日志链路默认正则，锚定 `ms_h/ms_l/ls_h/ls_l` 特征行，只提取 `x.y.z` 起步（2~3 段小数）的版本号；
  - `DEFAULT_TEXT_VERSION_PATTERNS`：工单标题/描述文本兜底正则，`version` 前不允许字母/下划线（排除 `launcher_version` 等带前缀字段），版本形态同样要求 `x.y.z` 起步；
  - `parse_log_version_patterns`：解析配置中的正则列表（过滤非法/空/重复，上限 20 条）；
  - `extract_version_key_by_patterns`：按正则列表提取版本号，取第一个命中且归一化有效的值。
- 原 3 处重复定义的 `VERSION_PATTERN` 全部删除，改为调用 util。

### 2. 正则改为可视化配置

- 配置落点：工单同步自动化页面 →「来源与拉取」tab →「存储与资源限制」卡片 →「下载完成后处理」区块下方新增「版本提取正则」JSON 数组编辑框，随「保存存储与资源限制」一起保存。
- 后端存储在日志拉取存储配置行（`versionExtractPatterns` 字段），随 `TicketLogPullStorageConfigModel` / `TicketLogPullPostProcessConfigModel` 读写；归一化时空值或全部非法自动回退默认正则。
- 生效链路：
  - 日志拉取成功后的正文版本回填（`ensure_ticket_version_id_from_log`，自动 AI 前置步骤）；
  - 下载完成后处理提取（`postDownloadVersionExtractEnabled` 开启时）。
- 工单标题/描述文本提取（`TicketLightAiService.extract_version_key_from_text`）使用 util 内置的文本兜底正则，不走该配置（该链路不接触日志文件）。

### 3. 行为变化

| 场景 | 旧行为 | 新行为 |
|------|--------|--------|
| `ms_h:...version:1.1.6.8` 行 | 提取 `1.1.6.8` | 提取 `1.1.6.8`（不变） |
| `launcher_version:1.0.6.8` 行 | 误提取 `1.0.6.8` | 不提取 |
| `OpenGL parsed version: 4, 6` 行 | 误提取 `4` | 不提取 |
| 普通文本 `版本号: 1.2.3.4` / `app version: 2.3.4.5` | 提取 | 仍提取（文本兜底正则） |

## 配置示例

```json
["ms_h\\s*:\\s*\\d+\\s*,\\s*ms_l\\s*:\\s*\\d+\\s*,\\s*ls_h\\s*:\\s*\\d+\\s*,\\s*ls_l\\s*:\\s*\\d+\\s*,\\s*version\\s*[:=]\\s*(\\d+(?:\\.\\d+){2,3})"]
```

清空数组 `[]` 或配置全部非法时自动回退到上述内置默认正则。

## 涉及文件

- `server/modules/ticket/util/ticket_log_version_extract_util.py`（新增）
- `server/modules/ticket/service/log_pull/ticket_log_pull_service.py`
- `server/modules/ticket/service/log_pull/ticket_log_post_process_service.py`
- `server/modules/ticket/service/ai/ticket_light_ai_service.py`
- `server/modules/ticket/entity/vo/ticket_log_pull_vo.py`
- `server/tests/test_ticket_log_version_extract.py`（新增）
- `server/tests/test_ticket_version_key_normalization.py`（适配新正则）
- `web/src/views/ticket/syncAutomation/index.vue`
- `web/src/views/ticket/syncAutomation/hooks/useLogPullStorageConfig.js`
- `web/public/docs/ticket_log_pull.md`
