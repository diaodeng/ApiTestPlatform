# 2026-09-23 - POS/SQLite 页面切页保留数据（对齐 mitm 会话化模式）

## 问题

与 mitmproxy 页面同类：切到其他页面再切回来，页面数据丢失。本次排查并一并处理 POS 与 SQLite 两个页面。

## POS 页（pos.js）

### 丢失范围（改造前）

- 扫描出的 POS 列表：切页回来靠 `reload()` 重新拉 `get_bootstrap`，列表能回来但会闪一次空；
- **运行日志区**：切页即清空——最影响使用，POS 启动过程的输出日志（含 `pos_log` 事件推送）切页期间全部丢失；
- 每条 POS 的环境信息（`envState`）：查看环境/本地环境切换后的结果切页即丢，回来全部显示"未获取"；
- 状态文本、过滤关键字、状态区收起/展开状态。

### 改造内容

- 新增模块级 `session`（statusText / logLines / filter / statusExpanded / envState），跨页保留；日志上限 2000 行（超出丢最早）；
- `pos_status` / `pos_log` 改为**模块级常驻订阅**（`bindPersistentBusOnce` 幂等绑定）：切页期间启动/停止日志与状态照常累计，回到页面完整恢复——POS 启动等长流程中切页不再丢日志；
- 渲染引用放模块级 `renderRef`（renderLog / setStatus），页面销毁时置空，常驻回调经可选链调用；
- 进入页面时恢复：日志、状态、过滤、收起状态；环境信息 Map 直接复用，列表重渲染后行内环境行自动回填（`envState` 键为路径，与 DOM 无关）。

### 保留的既有行为

- `reload()` 每次进入页面仍执行：引导数据（配置、启动勾选）保持与后端一致；
- 「停止POS」后状态文本以停止结果为准的语义不变。

## SQLite 页（sqlite.js）

### 丢失范围（改造前）

- 当前分页数据、分页位置：切页回来要重新走 目录→库→表 链路重新查询；
- SQL 执行结果区文本、SQL 编辑器未保存的草稿、底部状态文本；
- 目录/库/表下拉选中值（虽然后端 cfg 记忆了 last_*，但页面不恢复选中值，首次级联加载后停在第一项）。

### 改造内容

- 新增模块级 `session`（cfg / directories / tables / columns / page / total / lastTableData / sqlResultText / statusText / sqlDraft / lastDirPath / lastDbPath / lastTableName）；
- 该页面无事件推送，不需要常驻订阅；init 检测会话中已有数据时**直接从会话重建视图，不发起任何请求**（不重新 get_config / list_tables / fetch_table_page）；
- 首次进入行为不变（get_config → 渲染 → 级联加载）；
- `loadTableData` / `execute_sql` / 扫描等操作同步更新 session；SQL 编辑器增加 `input` 监听保存草稿（切页时输入到一半的 SQL 不丢）。

### 注意点

- 会话恢复路径刻意绕开 `renderDirs→renderDatabases→loadTables` 级联链（否则会触发重新拉取，等于没保留），由 `restoreTables()` 一次性从缓存重建表下拉、过滤列与数据表；
- 切换目录/库/表仍会正常走级联重新查询（用户主动操作）。

## 变更文件

- `client_new/ui_web/static/js/pages/pos.js`（同步至部署目录 `_internal/ui_web_static/js/pages/pos.js`）
- `client_new/ui_web/static/js/pages/sqlite.js`（同步至部署目录 `_internal/ui_web_static/js/pages/sqlite.js`）

## 验证结果

- `node --check` 两文件语法通过；
- stub DOM/后端环境真实导入执行两页面：首次进入 → 推送事件 → 模拟切页 → 二次进入，断言全部通过：
  - POS：常驻订阅只绑一次、切页期间日志仍写入 session、二次进入正常初始化；
  - SQLite：二次进入 `get_config` 与 `fetch_table_page` 调用次数均为 1（未重新请求）；
- 逐项核对了首层执行路径引用的 `let/const` 声明行号均在调用之前（吸取本轮 detailTab TDZ 回归教训）。

## 剩余风险

- SQLite 会话持有最近一次查询结果集（最多一页数据），内存占用可控；
- POS 日志上限 2000 行，超出丢最早记录（与 logs 页 maxLines 策略一致）。
