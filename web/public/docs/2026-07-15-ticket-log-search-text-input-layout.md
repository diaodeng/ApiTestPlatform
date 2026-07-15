# 2026-07-15 工单日志搜索文本输入与详情区配置调整

## 结论

- 工单详情页日志搜索关键字不再使用可创建多选下拉，改为文本框输入。
- 日志详情高亮词不再使用下拉列表，改为详情显示区域顶部的文本框输入。
- 搜索关键字和高亮词都支持英文逗号或换行分隔多个文本。
- 日志详情顶部的高亮摘要过长时单行省略显示，不再撑高或换行挤压“清除高亮”按钮。

## 界面调整

1. 搜索区域保留搜索关键字、匹配模式、文件范围、结果上限、重新拉取/重新下载和异常提取。
2. 上下文行数移动到日志详情显示区域顶部，影响后续点击命中行、上一段和下一段时读取的上下文范围。
3. 高亮文本输入移动到日志详情显示区域顶部，输入内容会归一化为最多 10 个高亮词，每个最多 200 字符。
4. 顶部高亮摘要使用 `text-overflow: ellipsis`，完整内容通过鼠标悬停 `title` 查看。

## `/ticket/logs/prepare` 行为说明

每次打开日志搜索弹窗时，前端会先调用 `/ticket/logs/prepare`。该接口不会执行关键字搜索，主要做日志目录准备：

1. 根据 `ticketId` 和可选 `recordId` 定位日志拉取记录。
2. 如果当前工单/记录已有解压目录且通过资源阈值校验，会直接复用，不重复解压。
3. 如果未准备过，会解析日志拉取记录的本地归档或下载来源，把归档复制到 `server/data/logs/.../source`。
4. 按资源保护配置递归解压到 `server/data/logs/.../extract`，识别可搜索文本文件。
5. 写入 `meta.json`，返回 `prepared/sourcePath/extractPath/fileCount/message` 等准备结果。

## 影响范围

- 前端页面：`web/src/views/ticket/index.vue`
- 前端状态：`web/src/views/ticket/hooks/useLogViewer.js`
- 后端接口契约不变：`/ticket/logs/search` 仍接收归一化后的 `keywords/searchMode`。

## 验证

- `cd web; npm run build:prod`
