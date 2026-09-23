# 2026-09-23 - mitmproxy 复制 cURL 报错修复与切页保留流量

> **追加修复（同日 14:40）**：切页保留功能的首次实现引入了 `detailTab` TDZ 回归
> （`Cannot access 'detailTab' before initialization`，整页不可用），根因与修复见文末
> 「追加：detailTab TDZ 回归修复」一节。

## 问题一：复制 cURL 无响应

### 现象

详情区点击「复制 cURL」无响应，客户端日志报：

```
前端js_error: Uncaught TypeError: "`\n".join is not a function @ js/pages/mitm.js:288
```

### 根因

`buildCurl()` 是从旧版 PySide 的 `_build_curl`（Python）迁移来的，Python 的 `" `\n".join([...])` 语法被原样照抄成了 JS：`"`\n".join([...])`。JS 字符串没有 `join` 方法，抛 TypeError。

### 修复

改为 JS 数组 join：`[lines[0], ...lines.slice(1).map(...)].join(" `\n")`，拼接结果（PowerShell 反引号续行、行首两格缩进、单引号转义）与旧版逐字节一致，已用 node 断言验证。

## 问题二：切换页面后再切回 mitmproxy，流量数据丢失

### 现象

mitmproxy 页面切到其他页面再切回来，流量列表、选中详情、过滤关键字全部丢失。

### 根因

- `app.js` 的切页机制是销毁页面 DOM 并重新执行 `mitmPage()`，`flows` / `selectedFlow` 等都是页面函数内的局部变量，重建即丢；
- 后端 `mitm_api.py` 对 `flow_new` / `flow_update` 只做转发不缓存，切页期间错过的流量无法补发。

### 修复（对齐 logs 页已有的 session 模式）

- 新增模块级 `session`（flows / selectedId / filter / showDetail / config），跨页面保持；`selectedId` 存 id 而非对象引用，避免 `flow_update` 替换数组项后引用过期；
- `mitm_flow_new` / `mitm_flow_update` 改为**模块级常驻订阅**（`bindPersistentBusOnce` 幂等绑定，整个应用生命周期只绑一次）：切页期间流量照常累计到 `session.flows`，不再有数据空窗；
- 页面渲染函数引用放模块级 `renderRef`：页面挂载时注册、销毁时置空，常驻回调经可选链调用，页面不在时只更新数据不渲染；
- 页面级事件（`mitm_state` / `mitm_cert_status`）保持原样，离开页面即退订（它们只影响当前 DOM）；
- 进入页面时从 session 恢复：流量列表、选中项、过滤关键字、详情显隐；「清空」按钮清 session，设置保存后 `session.config` 同步更新（供常驻订阅读取流量记录上限）。

### 行为变化

- 切页回来：流量列表与详情保留（含切页期间的新流量）、过滤条件保留、详情显隐保留；
- 流量记录上限（设置里的 flow_record_limit）在切页期间同样生效；
- 「清空」仍是彻底清空（session 一并清）。

## 变更文件

- `client_new/ui_web/static/js/pages/mitm.js`（同步至部署目录 `_internal/ui_web_static/js/pages/mitm.js`）

## 验证结果

- `node --check` 语法校验通过；
- node 脚本模拟验证：切页期间流量累计、已有序项更新、超限丢弃最早项、切回后视图恢复、cURL 拼接与旧版一致，全部断言通过；
- 已同步部署目录，diff 一致。

## 剩余风险

- 常驻订阅在应用生命周期内持有 `session.flows`，内存占用受「流量记录上限」约束（默认 500 条），与原行为一致；
- 若后端推送流量体积极大时 UI 渲染频率与原来相同（每条一刷），未做节流，与旧行为一致。

## 追加：detailTab TDZ 回归修复（同日 14:40）

### 现象

部署切页保留版本后，mitmproxy 页面报 `Uncaught ReferenceError: Cannot access 'detailTab' before initialization @ mitm.js:361`，整页无法使用。

### 根因

切页保留改造在页面挂载处（`mount.append` 之后）加了"恢复渲染"调用 `renderFlows(); renderDetail();`，但 `renderDetail` 内部经 `markTab` 读取的 `detailTab`（let）和 `dash`（const 箭头函数）声明在更靠后的位置——`let/const` 无提升，首层执行触发暂时性死区，页面初始化中断。这是第一轮 TDZ 修复（`setupColumnResize`）的同类问题，教训一致：**JS 的 `function` 声明有提升，但 `let/const` 没有；把初始化调用放前面时，调用链里引用的所有 `let/const` 都必须已声明。**

### 修复

- 将 `renderRef` 注册、`bindPersistentBusOnce()`、初始 `renderFlows()`/`renderDetail()` 整体移动到 `detailTab` 声明之后；
- `dash`（const 箭头函数）上移到初始渲染之前（它同样在 `renderDetail` 首层路径上）。

### 验证方式升级

`node --check` 只查语法、查不出 TDZ。本次改用 stub DOM/后端环境**真实导入并执行 `mitmPage` 首层同步代码**+ 模拟流量事件推送，实际跑通无 ReferenceError；并逐项核对了首层执行路径（`setupColumnResize` / `bindPersistentBusOnce` / `renderFlows` / `renderDetail`）引用的全部外部 `let/const` 的声明行号均在调用之前。
