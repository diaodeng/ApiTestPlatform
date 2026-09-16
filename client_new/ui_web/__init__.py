"""pywebview 版界面的后端支撑包。

目录职责：
- event_bus：后台线程事件推送到前端（evaluate_js 分发器）。
- dialog_bridge：把原 Qt 弹窗（确认/选择/提示）桥接为前端模态框。
- app：pywebview 窗口装配与启动。
- api：前端 JS 调用的桥接 API（按页面域拆分的子服务 + Bridge 门面）。
- static：前端静态资源（无构建步骤的原生 HTML/CSS/JS）。
"""
