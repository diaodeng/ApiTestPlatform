# 2026-09-23 - mitmproxy 页面初始化 ReferenceError 修复

## 问题现象

客户端（QTRClient_webview）mitmproxy 页面进入后控制台报错：

```
Uncaught ReferenceError: Cannot access 'RESIZE_COL_KEYS' before initialization @ js/pages/mitm.js:103
```

页面点击任何按钮（启动/停止/设置等）均无响应。

## 根因

`mitm.js` 中 `setupColumnResize()` 在第 77 行被调用，而其内部引用的常量 `RESIZE_COL_KEYS`、`COL_WIDTH_STORE_KEY`、`colIndex` 在第 81 行之后才用 `const` 声明。`const` 存在暂时性死区（TDZ），函数执行时访问未初始化的 `const` 抛出 ReferenceError，`mitmPage()` 初始化流程中断，后续所有按钮事件绑定未执行，导致整页按钮失效。

## 修复方式

调整 `ui_web/static/js/pages/mitm.js` 中语句顺序：将 `setupColumnResize()` 的调用移动到 `RESIZE_COL_KEYS` 等常量声明之后，并补充注释说明调用顺序约束。未改动任何业务逻辑。

## 变更文件

- `client_new/ui_web/static/js/pages/mitm.js`

## 同步说明

已将修复后的文件同步到部署目录 `E:\xj\dmall\POS_auto_test\QTRClient_webview\_internal\ui_web_static\js\pages\mitm.js`，重启客户端后生效。

## 验证结果

- `node --check` 语法校验通过；
- 部署副本与源码 diff 仅含本次修复内容。

## 剩余风险

无。文件内其余 `function` 声明均有提升，无同类 TDZ 问题。
