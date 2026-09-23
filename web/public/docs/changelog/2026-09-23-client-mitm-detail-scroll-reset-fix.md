# 2026-09-23 - mitmproxy 详情区滚动位置被新流量重置修复

## 问题

mitmproxy 页面选中一条抓包记录后，在右侧详情区滚动查看响应内容时，只要有其他抓包数据进来（`flow_update` 事件），详情区就会被刷新，滚动条自动回到顶部。数据内容没变，但阅读位置丢失，抓包活跃时几乎无法阅读长响应。

## 根因

1. **后端每个流量阶段都推事件**：`client_new/services/mitmproxy_service/mock_handle.py` 的 `request` / `response` / `error` 各阶段都会 `_emit_flow("update", ...)`，mock 探测、断点、延迟还会产生多次 update。抓包活跃时 `mitm_flow_update` 事件非常频繁，且大部分是**其他流量**的更新。
2. **前端常驻订阅无条件刷新详情**：`client_new/ui_web/static/js/pages/mitm.js` 的 `bindPersistentBusOnce` 中，`mitm_flow_update` 处理器在更新 `session.flows` 后同时调用 `renderFlows()` 和 `renderDetail()`，未判断被更新流量是否为当前选中项。
3. **renderDetail 整体重建 DOM**：先 `clear(detailBody)` 再全部重建。`.detail-body` 是 `overflow:auto` 的滚动容器（`app.css` 的 `.detail-body`），子元素整体替换后 `scrollTop` 必然归零。

（流量列表同样全量重建，但滚动容器是外层 `.table-wrap`，tbody 子元素替换不重置其滚动，所以列表没有此现象。）

## 修复（`client_new/ui_web/static/js/pages/mitm.js`）

两层修复：

1. **详情刷新条件收紧**：`mitm_flow_update` 订阅中，`renderDetail()` 仅在 `p.item.id === session.selectedId` 时调用。其他流量的更新只刷列表；选中流量自身的更新（如请求刚拿到响应、断点状态变化）仍会实时刷新详情。
2. **滚动位置保持**：`renderDetail()` 重绘前记录 `detailBody.scrollTop`，重绘后还原。并引入 `lastDetailKey`（`"流量id|tab"`）：仅当同一条流量在同一标签页下重绘时才恢复滚动位置；切换选中行或切换总览/请求/响应标签页时内容全新，仍回到顶部。

## 同步

- `dist_dev/QTRClientNew_portable/_internal/ui_web_static/js/pages/mitm.js` 已同步（本地打包客户端直接从该目录加载前端）。

## 验证

- `node --check` 语法通过。
- stub 环境真实执行（模拟 `mitm_flow_update` 非选中流量 / 选中流量、tab 切换、选中行切换），断言详情刷新次数与滚动恢复符合预期。
