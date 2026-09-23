# 2026-09-23 - 客户端 POS 启动链路修复与配置目录锚定

## 变更背景

对 client_new 的 POS 页面启动链路做了整体排查，修复了 11 项问题（4 高、5 中、3 低中分级），涉及：启动确认逻辑的真实生效、配置文件位置的确定性、无配置/坏配置场景的用户提示。

## 变更内容

### 1. 配置与日志目录固定到应用根目录（不再随启动方式漂移）

此前所有配置文件（`storage/data/*.json`）、日志（`logs/`）都按进程工作目录（cwd）相对路径读写。双击 exe 时 cwd 恰好是 exe 目录所以"碰巧正常"，但快捷方式起始位置不对、脚本从其他目录启动、计划任务启动时，配置会**静默生成到错误位置**，表现为配置"全部丢失"、日志找不到。

现在统一锚定：

- 打包态：exe 所在目录下的 `storage/data`、`logs`；
- 源码态：`client_new` 目录下（与原行为一致，开发无感）。

覆盖范围：`do/config.py` 全部 10 个配置类、`utils/logger.py`（含 control.log/fatal_error.log）、`ui_web/api/pos_api.py` 的切换表单状态文件、`server/agent_server.py` 的断连补交清单文件。插件、mitm helper 链路此前已按 exe 目录处理，本次保持一致。

**迁移说明**：一直双击 exe 启动的用户无任何变化；曾从其他目录启动过的用户，旧配置散落在当时的 cwd 下，升级后首次启动会在 exe 目录生成全新配置（host、扫描历史等需重新配置或用"同步配置"拉取），不做自动迁移。

### 2. "切换后启动"选项真正生效（原为死代码）

本地与服务端配置不一致的弹窗有三个选项：取消/确定/切换后启动。此前选"切换后启动"**什么都不会发生**（内部标志 `need_switch` 无任何消费点），直接原样启动。现在该选项会真正调用在线切换接口，切换成功后启动。

### 3. 设置保存后服务地址立即生效

`utils/pos_network.py` 在模块导入时一次性缓存服务地址，此前在设置弹窗保存 POS 配置后**不刷新**，必须重启应用才能生效（"同步配置"路径会刷新，行为不一致）。现在保存成功后立即刷新，无需重启。

### 4. 服务地址未配置时的明确提示

`config_pos.json` 不存在时服务地址默认为空，此时远程操作（获取服务端配置、在线切换、退出账号等）会因 URL 无效抛底层异常并被吞掉，用户只能看到笼统的"获取失败"。现在所有远程请求前校验地址，未配置时明确提示"XX服务地址未配置，请在 POS 设置中填写服务地址或使用同步配置"。

### 5. 启动前置检查规则调整

- **缺 pos.ini 阻断**：POS 目录缺 `pos.ini`（或未配置 `pos_env` 键）时，环境完全未知（此前会兜底请求 test 地址），现在启动前明确报错阻断，且不再先杀运行中的 POS 进程。
- **缺 pos_params 仍可启动（产品约束）**：缺本地业务参数（pos_params 文件）不阻断启动，维持原有确认弹窗（确认后直接启动）。勾选了"切换云端POS"或"退出登录"时，因这两个动作需要本地参数才能执行，会弹确认框说明"跳过该动作并继续启动"，用户确认后跳过动作继续，取消则中止本次启动。
- **取消启动的补充提示**：启动检查阶段会先停止运行中的 CPOS 进程（既有行为），用户随后在确认弹窗取消启动时，现在会提示"启动已取消（注意：已提前停止运行中的POS进程）"。

### 6. 配置文件损坏时明确报错（不再静默重置）

此前配置 JSON 损坏时多数读取点会静默回退默认值——最危险的是 `config_pos.json` 损坏会**悄悄清空服务地址和商家配置**。现在的语义：

- 文件不存在：用默认值（首次运行正常路径，不变）；
- 文件存在但损坏：抛"配置文件异常:<路径>: <原因>"，相关功能明确报错直到用户修复或删除文件。

特殊点位：`config_pos.json` 损坏不影响应用启动（服务地址降级为空并记 critical 日志，POS 页会提示配置异常）；主题配置损坏降级为 auto 并提示，不影响应用初始化。

### 7. 启动失败报错信息修正

- 启动前自动动作失败（替换证书/覆盖驱动等）从笼统的"启动异常"改为透传具体原因（如"mitmproxy-ca-cert.pem 不存在"、"支付mock驱动不存在:<实际路径>"）。
- 支付 mock 驱动源目录取值修正：优先用 POS 配置里的 `payment_mock_driver_path`，未配置时回退应用根目录下的 `drive`（此前按 cwd 相对路径查找，cwd 漂移时找不到）。

### 8. POS 设置补回迁移丢失的配置项，并修复备份驱动目录失效

- 设置弹窗补回 pywebview 迁移时丢失的两个配置项（旧版 Flet 有、新版缺失）：**支付MOCK驱动目录**（`payment_mock_driver_path`）与**支付驱动备份目录**（`payment_driver_back_up_path`），归入"驱动目录"区块。
- 修复重构引入的字段名笔误：`backup_payment_driver` 引用了模型上不存在的 `payment_mock_driver_backup_dir`，导致配置的备份目录从未生效（始终回退 POS 目录 drive_backup）；现已对齐旧版语义，改为读取 `payment_driver_back_up_path`，且"目录不存在才回退"。

### 9. 支付 mock 包双目录覆盖语义（drive + mock）

覆盖驱动的语义重新定义，此前只支持单 drive 目录：

- 配置项现在填 **mock 包根目录**，包内放两个子目录：`drive/` 复制到 POS 目录下的 `drive/`，`mock/` 复制到 **POS 安装根目录**；两者都是同名覆盖、原有其他文件保留；
- 默认包目录从应用根目录 `drive` 改为 **`payment_mock`**（避免与 POS 的 drive 目录名混淆）；不做旧单目录语义兼容，包内缺少 drive 和 mock 子目录时明确报错；
- 备份/恢复只覆盖 `drive` 内文件，mock 写入根目录的文件不参与备份回滚。

### 10. 修复启动确认弹窗无法应答导致的启动卡死（重要）

**现象**：启动 POS 时弹出确认框（如"本地和服务端配置不一致，继续启动？"），点击任意选项后页面不再有反应、POS 不启动，约 5 分钟后日志出现"弹窗等待超时，按取消处理"。

**根因**：`PosApi` 自建了一个 `WebDialogService` 实例，而前端弹窗应答（`resolve_dialog`）只会送达 `Bridge` 持有的那个实例——POS 启动引擎的等待挂在另一份 pending 表上，永远收不到应答，只能等 300 秒超时按取消处理。该问题影响新版 UI 中 POS 启动链路的**所有**确认框。

**修复**：`Bridge` 创建全局唯一 `WebDialogService` 并下发给 `PosApi`/`AppApi` 共享，确认框应答可正常跨线程送达引擎。

**顺带清理**：移除规则链中与引擎阶段重复的两条规则（`NoRemoteRule`、`MismatchRule`），消除"同一条件弹两次确认框"的问题——配置不一致时此前会连续弹两个几乎一样的三选项框，第二个叠在第一个之下无法操作，正是本次现象的放大器。规则链清空后所有确认逻辑收敛在引擎阶段一处，且引擎的一致性比对（6 字段）强于被移除的规则（3 字段），无覆盖遗漏。

## 变更文件

- `client_new/do/config.py`：配置路径锚定、统一读取助手（缺失默认/损坏抛异常）、覆盖驱动目录取值
- `client_new/utils/logger.py`、`client_new/main.py`：日志目录锚定
- `client_new/ui_web/api/pos_api.py`：切换状态文件路径、保存配置刷新 host、启动取消提示、引导数据异常兜底
- `client_new/ui_web/api/app_api.py`：主题配置损坏降级
- `client_new/server/agent_server.py`：补交清单路径锚定
- `client_new/server/config.py`：清理无引用的死属性
- `client_new/utils/pos_network.py`：空地址校验、config_pos 损坏降级
- `client_new/services/pos/pos_start_engine.py`：pos.ini 硬校验、杀进程标志、依赖动作检查
- `client_new/services/pos/pos_start_service.py`：need_switch 生效、异常分层、移除 UatNoLocalRule
- `client_new/services/pos/context.py`：新增 killed_running/skip_dependent_actions 标志
- `client_new/services/pos/rules/local_env_rule.py`：改为校验 pos.ini
- `client_new/services/pos/rules/uat_rule.py`：删除（与引擎确认弹窗重复）
- `client_new/services/pos_service.py`：不再吞掉启动检查业务异常
- `client_new/ui_web/api/bridge.py`、`client_new/ui_web/api/pos_api.py`：弹窗桥收敛为全局唯一实例（修复启动确认无法应答）
- `client_new/services/pos/rules/`：删除 remote_rule.py、mismatch_rule.py、uat_rule.py（与引擎阶段重复）
- `client_new/common/excptions.py`：新增 PosStartException/ConfigFileException
- `client_new/ui_web/static/js/pages/pos.js`：引导失败 toast 提示、设置弹窗补回驱动目录配置项
