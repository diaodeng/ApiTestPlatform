---
title: Mock响应头透传修复
---

# Mock 响应头透传修复（2026-09-23）

## 变更概述

修复桌面客户端（client_new）mitmproxy 抓包代理在 Mock 命中后重建响应时**丢失响应头**的问题：旧逻辑只保留 `Content-Type` 一个头，Mock 服务端返回的命中标记头 `mockId`（`规则id_响应id`）与用户在 Mock 响应头模板中配置的全部自定义头（业务 token 头、多条 `Set-Cookie` 等）都无法到达被测应用，导致"同一条 Mock 规则直连能用、走客户端代理就异常"且排障时无法从应用侧确认命中规则。

## 修复内容

- 修改文件：`client_new/services/mitmproxy_service/mock_handle.py`（`request` 方法中 Mock 命中分支）。
- 修复前：`Response.make(状态码, body, {"Content-Type": ...})`，其余响应头全部丢弃。
- 修复后：按 `multi_items()` 逐条透传 Mock 响应的全部头（保留重复头，多条 `Set-Cookie` 不合并），仅剔除传输控制类头：
  - `Content-Length`：由 mitmproxy 按实际 body 自动重算；
  - `Content-Encoding`：httpx 探测时已自动解压响应体，保留压缩声明会与应用侧解压冲突（这也是旧实现即使想透传也会踩的坑）；
  - `Transfer-Encoding` / `Connection` / `Keep-Alive`：逐跳头，仅对 Mock 服务器到代理这一跳有意义。
- 头键值显式按 utf-8（surrogateescape）编码为 bytes：mitmproxy `Response.make` 的元组列表入参不做 str 自动转换，直接传 str 会抛 `TypeError: Header fields must be bytes.`。
- Mock 服务端（`server/module_hrm`）无任何改动。

## 行为变化

| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| Mock 命中标记头 `mockId` | 走代理时应用看不到 | 应用响应头可见，可拆出 `规则id_响应id` |
| 响应头模板配置的自定义头 | 走代理时全部丢失 | 与直连 Mock 服务器一致 |
| 多条 `Set-Cookie` | 丢失 | 逐条保留 |
| Mock 未命中（505 放行）、探测超时放行、断点暂停探测 | 不受影响 | 不受影响 |

## 验证

- 语法与导入检查通过；`uvx ruff check` 对比修改前后均为存量 24 条告警，无新增。
- 构造带 `mockId`、自定义头、两条 `Set-Cookie`、`Content-Encoding: gzip`、旧 `Content-Length`、`Connection` 的模拟 Mock 响应，走真实 httpx 解压 + mitmproxy `Response.make` 链路断言：`mockId`/自定义头/重复 `Set-Cookie` 保留，黑名单头剔除，`Content-Length` 重算为实际长度，body 明文一致。

## 关联文档

- 用户说明：[抓包与 Mock 使用说明](../client/mitm-proxy.md)（"Mock 与请求改写"章节新增"Mock 响应头透传"说明）
