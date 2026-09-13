# 2026-09-14 桌面客户端 mitmproxy 设置弹窗修复（字段显示/代理模式/开关同行/问号提示/详情区样式）

## 背景

用户反馈 mitmproxy 页面与设置弹窗共六点问题：

1. 证书路径、脚本路径输入框为空时一片空白，用户看不到实际生效的默认值；
2. 代理相关字段语义错位——弹窗展示的是"代理客户端"（遗留无用字段，恒为空）与"代理模式值"（实际是拦截的应用进程名），真正起作用的代理模式（local/regular 等下拉）没有入口，用户无法切换；
3. 启用包含规则、启用排除规则、启用流量过滤、启用断点拦截、启用 Mock 等开关集中堆在"开关与模式"区，对应的路径/关键字内容却在另一个输入框区，开关与内容对不上号；
4. 大部分输入框没有格式提示，不知道该填什么；
5. 拦截应用迁移前可选择进程，迁移后只能手动输入；
6. 隐藏详情时右侧留白（列表不扩展）；详情的请求/响应信息没有按旧版样式分区展示。

## 变更内容

### `client_new/ui_web/static/js/pages/mitm.js`（设置弹窗重写）

1. **弹窗分组重排**：改为「基础配置 / Mock 与请求改写 / 过滤与拦截 / 延迟设置」四组（对齐旧 PySide 弹窗结构）。
2. **代理模式修正**：新增「代理模式」下拉框（绑定 `proxy_model`，选项 local/regular/wireguard/socks5/dns）与「拦截应用」输入框（绑定 `proxy_model_value`，仅 local 模式显示，联动显隐）；拦截应用支持手动输入 + 下拉选择——`mitm_api` 新增 `list_processes` 接口（psutil 枚举进程名、大小写不敏感去重排序，语义与旧版 `ProcessSelectorWidget` 一致），前端用 `input + datalist` 实现可输入可选择，首次点击输入框自动加载进程列表，旁有「加载」按钮手动刷新；移除后端已不消费的遗留字段「代理客户端」（`proxy_client` 不在弹窗中编辑、保存时原值保留，运行时不使用该字段）。
3. **证书路径显示默认值**：利用 `get_state` 返回的后端解析结果（`utils/mitmproxy_cert.resolve_mitmproxy_cert_path`），输入框为空时占位提示直接显示实际生效的默认证书路径（如 `留空使用默认证书：C:\Users\xj\.mitmproxy\mitmproxy-ca-cert.cer`）。
4. **脚本路径提示**：占位提示"留空使用客户端内置脚本"，问号说明解释该字段为自定义 mitmproxy 附加脚本（.py）路径。
5. **开关与内容同行**：断点（开关+关键字）、包含规则（开关+路径）、排除规则（开关+路径）、流量过滤（开关+规则）、Mock（开关+服务地址）均改为同一行展示；启动方式的 web 相关复选框在 dump 模式下禁用（对齐旧版联动）。
6. **placeholder 与问号提示**：所有输入框补充格式 placeholder（如附加请求头 `每行一个，格式：Content-Type=application/json`、流量过滤规则的后缀/子串匹配说明）；标签旁新增「?」图标，点击弹出该字段的完整说明（含义、格式、默认值、生效条件）。
7. **补回遗漏字段**：迁移时丢失的「附加 Body」（`add_body`）重新加入 Mock 与请求改写组。
8. 移除旧的 `F()` 通用字段数组机制，改为显式字段构造与保存赋值，避免 dataset/transform 的隐式映射。

### `client_new/ui_web/static/js/pages/mitm.js`（详情区重构 + 布局修复）

1. **隐藏详情列表占满**：原先隐藏详情时仅隐藏列内的文本面板，右侧留白；现改为隐藏整个详情列，列表列 flex 自动占满整行宽度，再次点击恢复分栏。
2. **详情样式对齐旧 PySide 版 `FlowDetailWidget`**：
   - 标签页从「请求/响应」扩为「总览/请求/响应」（默认总览）；
   - 总览：摘要行（时间 | 方法 | 状态 | 耗时 | URL）+ 总览信息键值表（17 项，空值统一显示 `-`）；
   - 请求：请求信息卡（Request Line、URL、Host、Content-Type）+ Form Data / Cookies（空则整卡隐藏）+ Headers + Body；
   - 响应：响应信息卡（Response Line、耗时、Content-Type、大小）+ Headers + Body；
   - Headers/Body 卡片带「复制」按钮，Body 支持「JSON」一键格式化（解析失败提示原因并回显原文），格式状态按请求/响应分别记忆、流量刷新不重置；
   - 详情工具栏新增「复制请求 / 复制响应 / 复制 cURL」，文本组装与 cURL 生成对齐旧版（PowerShell 反引号续行、剔除 Content-Length、无 Body 回退 Form Data）；
   - Body 最长展示 2 万字符（格式化后 4 万），避免超大响应拖垮渲染。

### `client_new/ui_web/api/mitm_api.py`

### `client_new/ui_web/api/mitm_api.py`

- 新增 `list_processes` 接口（psutil 枚举系统进程名，去重排序），供「拦截应用」下拉选择；修复迁移遗留缺陷——`save_config` 调用的 `_is_proxy_active` 方法在迁移时丢失（旧 Qt 版有定义），运行中保存配置必现 `AttributeError`，已按旧版语义补回（`helper_state in {starting, running, stopping}`），恢复"敏感字段变更自动重启、非敏感字段热更新"行为。

### `client_new/ui_web/static/js/core.js`

- 新增可复用 `helpTip(text)` 组件（`window.QTR.helpTip`）：label 旁「?」图标，点击切换显示说明气泡，点击页面其他位置自动收起（全局单监听，避免重复注册）。

### `client_new/ui_web/static/css/app.css`

- 新增 `.help-tip` / `.help-tip-bubble` 样式；气泡以图标左缘对齐向右展开（避免靠近弹窗左边缘时被 `modal-body` 的 overflow 裁剪）。
- 新增 mitm 详情卡片样式：`.detail-body`（纵向滚动容器）、`.detail-card` / `.detail-card-head` / `.detail-card-title`（分区卡片）、`.detail-meta`（键值表）、`.detail-summary`（摘要行）、`pre.detail-body`（等宽文本区，可选中复制）。

### 文档

- `web/public/docs/client/mitm-proxy.md`：配置项说明同步新分组、代理模式/拦截应用命名、证书路径默认值展示、脚本路径条目与问号提示用法；新增「流量详情」章节说明总览/请求/响应三个标签页的内容、复制与 JSON 格式化能力、隐藏详情列表占满行为。

## 验证

- `node --check` core.js、mitm.js 通过；`ast.parse` mitm_api.py 通过；ruff 检查 mitm_api.py 仅存量 I001（HEAD 已存在），零新增。
- `list_processes` 真实运行验证：本机枚举 96 个进程，排序与去重正确（explorer.exe 等在列）。
- `save_config` 打桩四分支验证：运行中+敏感字段（port/proxy_model 变更）→ 标记重启并发送 stop（reason 正确）；运行中+非敏感字段 → 发送 update 热更新；停止状态 → 仅保存不发命令。
- 用带 pywebview 桩的临时页面（返回与 dist 实际配置一致的 JSON）在浏览器中实测：
  - 弹窗 DOM 与截图：分组、字段、placeholder、问号图标齐全；证书路径占位显示默认路径 `C:\Users\xj\.mitmproxy\mitmproxy-ca-cert.cer`；
  - 点击「证书路径」旁问号，气泡完整显示不被裁剪（修复左缘裁剪问题后复验）；
  - 代理模式切 regular → 拦截应用行隐藏，切回 local → 恢复显示；启动方式切 web → 两个 web 复选框启用；
  - 修改端口/断点/请求延迟后点击保存，回传 config 数值转换正确（port=9443、breakpoint_pattern 去首尾空格、request_delay 结构 `{enabled,delay,delay_path}`）、`proxy_client` 原值保留；
  - 下半部分截图确认开关与内容同行布局。
- 「拦截应用」下拉浏览器实测：点击输入框自动加载 8 个桩进程选项、当前值保留；「加载」按钮触发刷新；模式切 regular 整行隐藏（含加载按钮）；改选进程后保存回传 `proxy_model_value` 正确。
- 详情区浏览器实测（桩注入两条流量，含一条断点暂停）：总览信息卡 17 项渲染正确；请求 tab 呈现 请求信息卡/Cookies/Headers/Body（Form Data 空则隐藏）；Body 点「JSON」缩进格式化、按钮切为「文本」，再点切回；断点暂停流量显示「继续放行/编辑并放行」；点「隐藏详情」详情列隐藏、列表列宽与容器总宽一致（1263px 占满），「显示详情」恢复分栏；响应 tab 呈现 响应信息卡/Headers/Body。
- 验证用临时 HTML 与本地静态服务已删除/停止。

## 剩余风险

- 弹窗为纯前端改动，未在 pywebview 真实窗口中肉眼验收（用浏览器内核同源验证）；如 WebView2 版本差异导致样式差异需实机确认。
- 「代理客户端」（`proxy_client`）配置字段本身仍保留在配置模型中（兼容旧配置文件），仅界面不再展示；后端运行时从未消费该字段。
