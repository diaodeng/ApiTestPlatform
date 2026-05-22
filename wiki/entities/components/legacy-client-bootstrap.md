---
title: 旧版客户端启动壳
type: entity
entity_category: component
source_type: code
canonical: true
knowledge_state: stable
confidence: high
freshness: 2026-05-20
created: 2026-05-20
updated: 2026-05-20
related_files:
  - client/src/main.py
  - client/src/navigationMenu.py
  - client/src/contents.py
---

# 旧版客户端启动壳

旧版客户端启动壳负责 Flet 页面启动、导航布局、状态栏刷新和异常展示，是旧版桌面入口的 UI 组装层。

```mermaid
graph TD
  A[main.py 启动] --> B[创建 Flet 页面]
  B --> C[窗口关闭拦截]
  B --> D[导航菜单]
  D --> E[内容工厂]
  E --> F[功能页面懒加载]
  F --> G[本地工具与服务]
```

## 输入输出

| 输入 | 输出 |
|---|---|
| Flet `Page`、配置文件、运行状态 | 可交互桌面窗口 |
| 导航索引 | 对应功能页实例 |

## 关键职责

- 拦截关闭事件并弹出确认对话框。
- 通过 `NavigationMenu` 切换内容区域。
- 维护底部系统信息与异常对话框。

## 参见

- [旧版 Flet 客户端](../services/legacy-flet-client.md)
- [双客户端架构](../../concepts/desktop-client-architecture.md)

## 被引用

- [项目总览](../../overview.md)
- [旧版 Flet 客户端](../services/legacy-flet-client.md)
