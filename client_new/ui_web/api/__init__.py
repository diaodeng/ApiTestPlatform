"""前端桥接 API 包：各页面域的子 API + Bridge 门面。

pywebview 只在 js_api 上挂一个 Bridge 对象，Bridge 内部聚合各子 API。
子 API 之间不互相依赖，统一通过 event_bus 推送事件、返回 dict 作为调用结果。
"""
